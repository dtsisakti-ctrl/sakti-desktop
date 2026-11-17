"""Cryptographic primitives for the ExamGuard protocol (PRD §16.2, §17.2, §18, §19).

Signed envelope: {"kid", "body", "sig"}; the signature covers the exact UTF-8 bytes of ``body``
(a JSON string), so no JSON canonicalization is needed across languages.
"""
import base64
import hashlib
import json
import os
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def b64u(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def unb64u(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dumps(obj: Any) -> str:
    """Compact JSON used for every signed body (datetimes must already be strings)."""
    return json.dumps(obj, separators=(",", ":"), ensure_ascii=False, sort_keys=True)


# ------------------------------------------------------------------ Ed25519
def new_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.generate()


def public_raw(key: Ed25519PrivateKey | Ed25519PublicKey) -> str:
    pub = key.public_key() if isinstance(key, Ed25519PrivateKey) else key
    return b64u(pub.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw))


def load_public(raw_b64u: str) -> Ed25519PublicKey:
    data = unb64u(raw_b64u)
    if len(data) != 32:
        raise ValueError("Ed25519 public key must be 32 bytes")
    return Ed25519PublicKey.from_public_bytes(data)


def private_raw(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw,
                             serialization.NoEncryption())


def load_private_raw(data: bytes) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(data)


def private_pem(key: Ed25519PrivateKey) -> bytes:
    return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())


def load_private_pem(pem: bytes) -> Ed25519PrivateKey:
    key = serialization.load_pem_private_key(pem, password=None)
    if not isinstance(key, Ed25519PrivateKey):
        raise ValueError("not an Ed25519 private key")
    return key


def sign(key: Ed25519PrivateKey, data: bytes) -> str:
    return b64u(key.sign(data))


def verify(pub: Ed25519PublicKey | str, data: bytes, sig: str) -> bool:
    try:
        (load_public(pub) if isinstance(pub, str) else pub).verify(unb64u(sig), data)
        return True
    except (InvalidSignature, ValueError):
        return False


# ------------------------------------------------------------------ envelope
def envelope(kid: str, key: Ed25519PrivateKey, body: dict[str, Any]) -> dict[str, str]:
    text = dumps(body)
    return {"kid": kid, "body": text, "sig": sign(key, text.encode())}


def open_envelope(env: dict[str, str], pub: Ed25519PublicKey | str) -> dict[str, Any] | None:
    """Return the parsed body if the signature is valid, else None."""
    if not verify(pub, env["body"].encode(), env["sig"]):
        return None
    return json.loads(env["body"])


# ------------------------------------------------------------------ JWT (EdDSA)
def jwt_encode(kid: str, key: Ed25519PrivateKey, claims: dict[str, Any]) -> str:
    header = b64u(dumps({"alg": "EdDSA", "typ": "JWT", "kid": kid}).encode())
    payload = b64u(dumps(claims).encode())
    signing_input = f"{header}.{payload}".encode()
    return f"{header}.{payload}.{sign(key, signing_input)}"


def jwt_decode(token: str, resolve_key) -> dict[str, Any] | None:
    """Verify an EdDSA JWT. ``resolve_key(kid) -> public key | None``. Expiry is the caller's job."""
    try:
        h, p, s = token.split(".")
        header = json.loads(unb64u(h))
        if header.get("alg") != "EdDSA":
            return None
        pub = resolve_key(header.get("kid"))
        if pub is None or not verify(pub, f"{h}.{p}".encode(), s):
            return None
        return json.loads(unb64u(p))
    except (ValueError, KeyError):
        return None


# ------------------------------------------------------------------ at-rest encryption of server keys
def seal(kek: bytes, plaintext: bytes, aad: bytes) -> str:
    nonce = os.urandom(12)
    return b64u(nonce + AESGCM(kek).encrypt(nonce, plaintext, aad))


def unseal(kek: bytes, sealed: str, aad: bytes) -> bytes:
    data = unb64u(sealed)
    return AESGCM(kek).decrypt(data[:12], data[12:], aad)
