"""ExamGuard Client API (PRD §12, §16.2, §17, §18) and the public key set (§19).

HTTPS requests after device registration carry
    Authorization: EG-Sig sid=<device_session_id>, ts=<unix_ms>, sig=<base64url>
    sig = Ed25519(METHOD \\n PATH[?QUERY] \\n ts \\n sha256_hex(body))
The WebSocket authenticates the same way with query parameters (sid, ts, sig) over
"GET\\n/client/v1/ws\\n<ts>\\n<sha256_hex of empty body>".
"""
import asyncio
import json
from typing import Annotated, Any
from uuid import UUID

import anyio
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from starlette.concurrency import run_in_threadpool

from .. import clock, crypto, keys
from ..config import get_settings
from ..db import set_context, transaction
from ..errors import AppError
from ..models import Attempt, DeviceSession
from ..schemas import (AckIn, ClientEventsIn, ClientHeartbeatIn, DeviceSessionIn, IdentityPhotosIn, LaunchIn)
from ..services import client_flow, proctoring, protocol
from .deps import DB

router = APIRouter(prefix="/client/v1", tags=["client protocol"])
well_known = APIRouter(tags=["client protocol"])


# ------------------------------------------------------------------ signed request plumbing
class Signed:
    def __init__(self, method: str, path: str, header: str | None, body: bytes):
        self.method, self.path, self.header, self.body = method, path, header, body


async def signed_request(request: Request) -> Signed:
    path = request.url.path + (f"?{request.url.query}" if request.url.query else "")
    return Signed(request.method, path, request.headers.get("authorization"), await request.body())


SignedReq = Annotated[Signed, Depends(signed_request)]


def _device(db, req: Signed, attempt_id: UUID, *, allow_revoked: bool = False, touch: bool = True) -> DeviceSession:
    set_context(db, "system")
    p = protocol.parse_authorization(req.header)
    ds = protocol.authenticate(db, sid=p["sid"], ts=p["ts"], sig=p["sig"], method=req.method, path=req.path,
                               body=req.body, attempt_id=attempt_id, allow_revoked=allow_revoked)
    if touch and ds.status == "ACTIVE":
        client_flow.touch(db, ds.id)   # a signed request is proof of life (resumes after a closed connection)
    return ds


def _state(db, ds: DeviceSession) -> dict[str, str]:
    return protocol.signed_state(db, db.get(Attempt, ds.attempt_id), ds)


# ------------------------------------------------------------------ key set
@well_known.get("/.well-known/examguard-keys.json")
def key_set(db: DB):
    env = keys.current_key_set(db)
    if env is None:
        raise AppError(503, "NO_KEY_SET", "no key set published yet; run `examguard keys rotate`")
    return JSONResponse(env, headers={"Cache-Control": "public, max-age=300"})


# ------------------------------------------------------------------ launch & registration
@router.post("/launch")
def launch(db: DB, body: LaunchIn):
    """Exchange a launch token for the Signed Exam Config (does not consume the token)."""
    set_context(db, "system")
    return {"config": protocol.exam_config(db, body.launch_token)}


@router.post("/device-sessions", status_code=201)
def register_device_session(db: DB, body: DeviceSessionIn):
    """Bind the client's Ed25519 public key to the attempt (consumes the launch token)."""
    set_context(db, "system")
    return protocol.register(db, body.launch_token, body.public_key, body.client_version,
                             body.os_info, body.preflight)


# ------------------------------------------------------------------ signed endpoints
@router.get("/attempts/{attempt_id}/state")
def full_state(db: DB, req: SignedReq, attempt_id: UUID):
    return _state(db, _device(db, req, attempt_id))


@router.post("/attempts/{attempt_id}/start")
def start(db: DB, req: SignedReq, attempt_id: UUID):
    ds = _device(db, req, attempt_id)
    client_flow.start(db, attempt_id, ds.id)
    return _state(db, ds)


@router.post("/attempts/{attempt_id}/identity")
def identity(db: DB, req: SignedReq, attempt_id: UUID, body: IdentityPhotosIn):
    """Selfie + ID card (base64). Stored encrypted; the attempt enters the Check-in Queue."""
    ds = _device(db, req, attempt_id)
    proctoring.submit_photos(db, ds, body.selfie, body.id_card, body.content_type)
    return _state(db, ds)


@router.post("/attempts/{attempt_id}/finish")
def finish(db: DB, req: SignedReq, attempt_id: UUID):
    """Level 0 'Selesai Ujian'. Level 2 exams finish through the Integration API (Phase 1c-2)."""
    ds = _device(db, req, attempt_id)
    if ds.status != "ACTIVE":
        raise AppError(409, "DEVICE_NOT_ACTIVE", "only the active device can finish the exam")
    client_flow.submit(db, attempt_id, source="MANUAL_FINISH")
    return _state(db, ds)


@router.post("/attempts/{attempt_id}/heartbeat")
def heartbeat(db: DB, req: SignedReq, attempt_id: UUID, body: ClientHeartbeatIn):
    """HTTPS fallback for the WSS heartbeat (§17.6)."""
    ds = _device(db, req, attempt_id, touch=False)
    return protocol.heartbeat(db, ds, body.seq, body.last_state_version, body.health, body.recovery_cause)


@router.post("/attempts/{attempt_id}/events")
def upload_events(db: DB, req: SignedReq, attempt_id: UUID, body: ClientEventsIn):
    # A revoked device may still flush its queue: the events are evidence (§20, §22).
    ds = _device(db, req, attempt_id, allow_revoked=True)
    return protocol.ingest_events(db, ds, [e.model_dump() for e in body.events])


@router.get("/attempts/{attempt_id}/commands")
def pending_commands(db: DB, req: SignedReq, attempt_id: UUID):
    """HTTPS fallback for WSS command push."""
    ds = _device(db, req, attempt_id)
    return {"commands": protocol.deliverable_commands(db, ds)}


@router.post("/attempts/{attempt_id}/commands/{command_id}/ack")
def ack_command(db: DB, req: SignedReq, attempt_id: UUID, command_id: UUID, body: AckIn):
    ds = _device(db, req, attempt_id)
    return protocol.ack(db, ds, command_id, body.result, body.reason)


@router.post("/attempts/{attempt_id}/attestation")
def attestation(db: DB, req: SignedReq, attempt_id: UUID):
    return protocol.attestation(db, _device(db, req, attempt_id))


# ------------------------------------------------------------------ WebSocket (§17.1, §17.5, §17.6)
def _ws_auth(sid: str, ts: str, sig: str) -> tuple[UUID, int]:
    with transaction("system") as db:
        ds = protocol.authenticate(db, sid=sid, ts=ts, sig=sig, method="GET", path="/client/v1/ws", body=b"")
        return ds.id, ds.last_heartbeat_seq


def _ws_closed(ds_id: UUID, seq_seen: int) -> None:
    with transaction("system") as db:
        client_flow.connection_closed(db, ds_id, seq_seen)


def _ws_poll(ds_id: UUID, last_version: int) -> tuple[list[dict[str, Any]], int, bool]:
    """Messages to push: signed commands, and signed state when state_version moved."""
    with transaction("system") as db:
        ds = db.get(DeviceSession, ds_id)
        if ds.status == "REVOKED":
            return [{"type": "REVOKED", "reason": ds.revoke_reason}], last_version, True
        out = [{"type": "COMMAND", "envelope": env} for env in protocol.deliverable_commands(db, ds)]
        attempt = db.get(Attempt, ds.attempt_id)
        if attempt.state_version != last_version:
            out.append({"type": "STATE", "envelope": protocol.signed_state(db, attempt, ds)})
            last_version = attempt.state_version
        return out, last_version, False


def _ws_message(ds_id: UUID, msg: dict[str, Any]) -> dict[str, Any] | None:
    with transaction("system") as db:
        ds = db.get(DeviceSession, ds_id)
        kind = msg.get("type")
        if kind == "HEARTBEAT":
            # Heartbeats are signed with the device key over the exact body string (§17.6).
            if not isinstance(msg.get("body"), str) or not crypto.verify(ds.public_key, msg["body"].encode(),
                                                                         msg.get("sig", "")):
                return {"type": "ERROR", "code": "INVALID_SIGNATURE"}
            body = json.loads(msg["body"])
            if body.get("device_session_id") != str(ds.id):
                return {"type": "ERROR", "code": "WRONG_SESSION"}
            skew = abs(clock.now().timestamp() * 1000 - int(body.get("ts", 0))) / 1000
            if skew > get_settings().request_clock_skew_seconds:
                return {"type": "ERROR", "code": "CLOCK_SKEW"}
            r = protocol.heartbeat(db, ds, int(body["seq"]), body.get("last_state_version"),
                                   body.get("health") or {}, body.get("recovery_cause"))
            return {"type": "HEARTBEAT_ACK", "_seq": int(body["seq"]), **r}
        if kind == "ACK":
            if msg.get("result") not in ("APPLIED", "STALE", "REJECTED"):
                return {"type": "ERROR", "code": "INVALID_ACK"}
            r = protocol.ack(db, ds, UUID(msg["command_id"]), msg["result"], msg.get("reason"))
            return {"type": "ACK_OK", "command_id": str(r["command_id"]), "delivery_status": r["delivery_status"]}
        if kind == "SYNC":
            return {"type": "STATE", "envelope": protocol.signed_state(db, db.get(Attempt, ds.attempt_id), ds)}
        return {"type": "ERROR", "code": "UNKNOWN_MESSAGE"}


class _Conn:
    """One open WebSocket: the newest heartbeat seq it carried (see client_flow.connection_closed)."""
    def __init__(self, ds_id: UUID, seq: int):
        self.ds_id, self.seq, self.server_closed = ds_id, seq, False


@router.websocket("/ws")
async def ws(websocket: WebSocket, sid: str = "", ts: str = "", sig: str = ""):
    try:
        ds_id, seq = await run_in_threadpool(_ws_auth, sid, ts, sig)
    except AppError as e:
        await websocket.close(code=4401, reason=e.code)
        return
    await websocket.accept()
    conn = _Conn(ds_id, seq)
    try:
        await _ws_loop(websocket, conn)
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    # (A cancelled task, e.g. server shutdown, is not the client going away: it propagates and records nothing.)
    if not conn.server_closed:
        # The client went away (crash, app closed, machine off, TCP connection dropped): the register shows
        # Terputus at once instead of after missed heartbeats (PRD v0.3.5 §17.6).
        with anyio.CancelScope(shield=True):
            await run_in_threadpool(_ws_closed, conn.ds_id, conn.seq)


async def _ws_loop(websocket: WebSocket, conn: _Conn) -> None:
    last_version = -1
    poll = get_settings().ws_poll_seconds
    while True:
        messages, last_version, closing = await run_in_threadpool(_ws_poll, conn.ds_id, last_version)
        for m in messages:
            await websocket.send_json(m)
        if closing:
            conn.server_closed = True
            await websocket.close(code=4403)
            return
        try:
            raw = await asyncio.wait_for(websocket.receive_text(), timeout=poll)
        except asyncio.TimeoutError:
            continue
        try:
            msg = json.loads(raw)
            reply = await run_in_threadpool(_ws_message, conn.ds_id, msg)
        except AppError as e:
            reply = {"type": "ERROR", "code": e.code, "message": e.message}
        except (ValueError, KeyError, TypeError):
            reply = {"type": "ERROR", "code": "BAD_MESSAGE"}
        if reply:
            seq = reply.pop("_seq", None)
            if seq is not None and not reply.get("stale"):
                conn.seq = max(conn.seq, seq)
            await websocket.send_json(reply)
