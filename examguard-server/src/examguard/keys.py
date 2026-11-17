"""Server signing keys and the root-signed key set (PRD §19).

Root trust key: kept OFFLINE by the Platform Admin (a PEM file used only by the CLI). Its public
key is embedded in the client binary; the client trusts a server kid only after verifying the key
set with it. The server never holds the root private key.

Server key: one Ed25519 key pair (MVP) published under one kid per use — "<base>.command",
"<base>.state", "<base>.config", "<base>.token" — so splitting keys later does not change the
protocol. The private key is stored encrypted with the key-encryption key (production: KMS/HSM).
"""
import json
import os
from datetime import datetime, timedelta
from functools import lru_cache
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from sqlalchemy import select
from sqlalchemy.orm import Session

from . import clock, crypto
from .config import get_settings
from .errors import AppError
from .models import KeySet, ServerKey

USES = ("command", "state", "config", "token")


def root_kid(root_public: str) -> str:
    return "root-" + crypto.sha256_hex(crypto.unb64u(root_public))[:16]


# ------------------------------------------------------------------ server keys
def create_server_key(db: Session, *, valid_days: int = 90, uses: tuple[str, ...] = USES) -> ServerKey:
    now = clock.now()
    key = crypto.new_private_key()
    base = f"srv-{now:%Y%m%d}-{crypto.b64u(os.urandom(4))}"
    row = ServerKey(kid_base=base, uses=list(uses), public_key=crypto.public_raw(key),
                    private_key_enc=crypto.seal(get_settings().kek, crypto.private_raw(key), base.encode()),
                    status="ACTIVE", not_before=now, not_after=now + timedelta(days=valid_days))
    db.add(row)
    db.flush()
    return row


def set_status(db: Session, kid_base: str, status: str) -> ServerKey:
    row = db.get(ServerKey, kid_base)
    if row is None:
        raise AppError(404, "NOT_FOUND", f"server key {kid_base} not found")
    row.status = status
    return row


@lru_cache(maxsize=16)
def _decrypt(kid_base: str, sealed: str) -> Ed25519PrivateKey:
    return crypto.load_private_raw(crypto.unseal(get_settings().kek, sealed, kid_base.encode()))


def signer(db: Session, use: str) -> tuple[str, Ed25519PrivateKey]:
    """Newest ACTIVE key valid now for ``use`` → (kid, private key)."""
    now = clock.now()
    row = db.scalars(select(ServerKey).where(
        ServerKey.status == "ACTIVE", ServerKey.uses.any(use),
        ServerKey.not_before <= now, ServerKey.not_after > now).order_by(ServerKey.not_before.desc())).first()
    if row is None:
        raise AppError(503, "NO_SIGNING_KEY", f"no active server key for use={use}; run `examguard keys rotate`")
    return f"{row.kid_base}.{use}", _decrypt(row.kid_base, row.private_key_enc)


def public_key(db: Session, kid: str, use: str | None = None) -> Ed25519PublicKey | None:
    """Resolve a published kid to its public key if it is not revoked (for server-side verification)."""
    base, _, kid_use = (kid or "").rpartition(".")
    if not base or (use and kid_use != use):
        return None
    row = db.get(ServerKey, base)
    if row is None or row.status == "REVOKED" or kid_use not in row.uses:
        return None
    return crypto.load_public(row.public_key)


# ------------------------------------------------------------------ key set
def key_set_body(db: Session) -> dict[str, Any]:
    now = clock.now()
    rows = db.scalars(select(ServerKey).where(ServerKey.not_after > now - timedelta(days=1))
                      .order_by(ServerKey.not_before)).all()
    keys = []
    for r in rows:
        for use in r.uses:
            keys.append({"kid": f"{r.kid_base}.{use}", "use": use, "alg": "EdDSA", "crv": "Ed25519",
                         "x": r.public_key, "not_before": _iso(r.not_before), "not_after": _iso(r.not_after),
                         "status": {"ACTIVE": "active", "RETIRED": "retired", "REVOKED": "revoked"}[r.status]})
    return {"v": 1, "issuer": get_settings().public_base_url, "issued_at": _iso(now), "keys": keys}


def sign_key_set(body: dict[str, Any], root_key: Ed25519PrivateKey) -> dict[str, str]:
    return crypto.envelope(root_kid(crypto.public_raw(root_key)), root_key, body)


def store_key_set(db: Session, env: dict[str, str]) -> KeySet:
    root_pub = get_settings().root_public_key
    if root_pub and crypto.open_envelope(env, root_pub) is None:
        raise AppError(422, "INVALID_KEY_SET", "key set signature does not verify with EXAMGUARD_ROOT_PUBLIC_KEY")
    body = json.loads(env["body"])
    row = KeySet(envelope=crypto.dumps(env), issued_at=datetime.fromisoformat(body["issued_at"]))
    db.add(row)
    db.flush()
    return row


def current_key_set(db: Session) -> dict[str, str] | None:
    row = db.scalars(select(KeySet).order_by(KeySet.id.desc())).first()
    return json.loads(row.envelope) if row else None


def publish(db: Session, root_key: Ed25519PrivateKey) -> dict[str, str]:
    env = sign_key_set(key_set_body(db), root_key)
    store_key_set(db, env)
    return env


def _iso(dt: datetime) -> str:
    return dt.isoformat().replace("+00:00", "Z")
