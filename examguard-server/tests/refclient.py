"""Reference ExamGuard client for tests: the protocol exactly as the Rust client must speak it.

    sig = Ed25519(METHOD \\n PATH[?QUERY] \\n ts \\n sha256_hex(body))
    Authorization: EG-Sig sid=<device_session_id>, ts=<unix_ms>, sig=<base64url>
"""
import json
import uuid
from typing import Any

from examguard import clock, crypto


class RefClient:
    def __init__(self, http, root_public: str):
        self.http = http
        self.root_public = root_public
        self.key = crypto.new_private_key()
        self.sid: str | None = None
        self.attempt_id: str | None = None
        self.seq = 0
        self.event_seq = 0
        self.config: dict[str, Any] | None = None
        self._keys: dict[str, dict] | None = None

    # --- trust
    def key_set(self) -> dict[str, dict]:
        env = self.http.get("/.well-known/examguard-keys.json").json()
        body = crypto.open_envelope(env, self.root_public)
        assert body is not None, "key set not signed by the root key"
        self._keys = {k["kid"]: k for k in body["keys"]}
        return self._keys

    def open(self, env: dict[str, str], use: str) -> dict[str, Any]:
        """Client rule §17.3: known kid, not revoked, matching use, valid signature."""
        keys = self._keys or self.key_set()
        k = keys.get(env["kid"])
        assert k is not None and k["status"] != "revoked" and k["use"] == use, f"untrusted kid {env['kid']}"
        body = crypto.open_envelope(env, k["x"])
        assert body is not None, "bad signature"
        return body

    # --- launch
    def launch(self, token: str) -> dict[str, Any]:
        r = self.http.post("/client/v1/launch", json={"launch_token": token})
        assert r.status_code == 200, r.text
        self.config = self.open(r.json()["config"], "config")
        self.attempt_id = self.config["attempt_id"]
        return self.config

    def register(self, token: str, version: str = "0.2.0"):
        r = self.http.post("/client/v1/device-sessions", json={
            "launch_token": token, "public_key": crypto.public_raw(self.key), "client_version": version,
            "os_info": {"os": "test"}, "preflight": {"camera": True}})
        if r.status_code == 201:
            self.sid = str(r.json()["device_session_id"])
        return r

    # --- signed requests
    def auth(self, method: str, path: str, body: bytes = b"", ts: int | None = None) -> str:
        ts = ts if ts is not None else int(clock.now().timestamp() * 1000)
        sig = crypto.sign(self.key, f"{method}\n{path}\n{ts}\n{crypto.sha256_hex(body)}".encode())
        return f"EG-Sig sid={self.sid}, ts={ts}, sig={sig}"

    def call(self, method: str, suffix: str, payload: Any = None, **kw):
        path = f"/client/v1/attempts/{self.attempt_id}{suffix}"
        body = b"" if payload is None else json.dumps(payload).encode()
        headers = {"Authorization": self.auth(method, path, body, **kw)}
        if payload is not None:
            headers["Content-Type"] = "application/json"
        return self.http.request(method, path, content=body, headers=headers)

    def state(self) -> dict[str, Any]:
        r = self.call("GET", "/state")
        assert r.status_code == 200, r.text
        return self.open(r.json(), "state")

    def start(self):
        return self.call("POST", "/start")

    def heartbeat(self, **kw):
        self.seq += 1
        return self.call("POST", "/heartbeat", {"seq": self.seq, **kw})

    def event(self, type_: str, phase: str = "INSTANT", **kw) -> dict[str, Any]:
        self.event_seq += 1
        now = clock.now().isoformat()
        return {"event_id": str(uuid.uuid4()), "seq": self.event_seq, "type": type_, "phase": phase,
                "started_at": kw.pop("started_at", now), **kw}

    # --- websocket
    def ws_url(self, ts: int | None = None) -> str:
        ts = ts if ts is not None else int(clock.now().timestamp() * 1000)
        sig = crypto.sign(self.key, f"GET\n/client/v1/ws\n{ts}\n{crypto.sha256_hex(b'')}".encode())
        return f"/client/v1/ws?sid={self.sid}&ts={ts}&sig={sig}"

    def ws_heartbeat(self, last_state_version: int | None = None) -> dict[str, Any]:
        self.seq += 1
        body = crypto.dumps({"device_session_id": self.sid, "seq": self.seq, "ts": int(clock.now().timestamp() * 1000),
                             "last_state_version": last_state_version, "health": {"lockdown_ok": True}})
        return {"type": "HEARTBEAT", "body": body, "sig": crypto.sign(self.key, body.encode())}
