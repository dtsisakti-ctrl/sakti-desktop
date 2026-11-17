"""Encrypted blob storage for sensitive files (identity photos, PRD §12.5, §24).

Blobs are sealed with AES-256-GCM before they touch the disk; the storage key is bound as
associated data, so a blob copied to another key does not decrypt. ``LocalEncryptedStorage`` is the
MVP backend; an S3-compatible backend only has to implement put/get/delete with the same contract.
"""
import hashlib
import os
from pathlib import Path
from typing import Protocol

from . import crypto
from .config import get_settings


class BlobStorage(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...


class LocalEncryptedStorage:
    def __init__(self, root: str | Path, kek: bytes):
        self.root = Path(root)
        # a separate key for blobs, derived from the key-encryption key
        self.key = hashlib.sha256(b"examguard-blob-v1" + kek).digest()

    def _path(self, key: str) -> Path:
        if not key or ".." in key or key.startswith(("/", "\\")):
            raise ValueError("invalid storage key")
        return self.root / key

    def put(self, key: str, data: bytes) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(crypto.seal(self.key, data, key.encode()))
        os.replace(tmp, path)

    def get(self, key: str) -> bytes:
        return crypto.unseal(self.key, self._path(key).read_text(), key.encode())

    def delete(self, key: str) -> None:
        self._path(key).unlink(missing_ok=True)


def get_storage() -> BlobStorage:
    s = get_settings()
    return LocalEncryptedStorage(s.storage_dir, s.kek)
