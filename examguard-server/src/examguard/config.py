"""Runtime configuration, read from environment variables (prefix EXAMGUARD_) or .env."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="EXAMGUARD_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://examguard_app:app-password@127.0.0.1:5432/examguard"
    migration_database_url: str = (
        "postgresql+psycopg://examguard_owner:owner-password@127.0.0.1:5432/examguard"
    )
    app_role: str = "examguard_app"
    env: str = "dev"
    portal_base_url: str | None = None                  # links in emails; default <public_base_url>/portal
    staff_session_hours: int = 12
    candidate_session_hours: int = 24
    email_verify_hours: int = 48
    invitation_days: int = 14
    min_password_length: int = 10
    # Phase 1c: protocol
    public_base_url: str = "http://127.0.0.1:8080"      # issuer of tokens, base of server_endpoints
    key_encryption_key: str | None = None               # base64url 32 bytes; required outside dev
    root_public_key: str | None = None                  # base64url; if set, uploaded key sets are verified
    launch_token_minutes: int = 15
    config_ttl_minutes: int = 30
    attestation_ttl_seconds: int = 300
    request_clock_skew_seconds: int = 60
    ws_poll_seconds: float = 1.0
    min_client_version: str = "0.1.0"
    storage_dir: str = ".examguard/storage"            # encrypted identity photos (local backend)
    identity_photo_max_bytes: int = 3_000_000
    web_ui_dir: str | None = None                       # override the packaged web build (landing, /admin, /portal)
    password_reset_minutes: int = 60

    @property
    def portal_url(self) -> str:
        return (self.portal_base_url or f"{self.public_base_url.rstrip('/')}/portal").rstrip("/")

    @property
    def is_dev(self) -> bool:
        return self.env == "dev"

    @property
    def kek(self) -> bytes:
        """Key-encryption key for server private keys at rest (production: from KMS/HSM)."""
        import base64
        import hashlib
        if self.key_encryption_key:
            raw = base64.urlsafe_b64decode(self.key_encryption_key + "=" * (-len(self.key_encryption_key) % 4))
            if len(raw) != 32:
                raise ValueError("EXAMGUARD_KEY_ENCRYPTION_KEY must decode to 32 bytes")
            return raw
        if not self.is_dev:
            raise RuntimeError("EXAMGUARD_KEY_ENCRYPTION_KEY is required when EXAMGUARD_ENV is not dev")
        return hashlib.sha256(b"examguard-dev-only-key-encryption-key").digest()


@lru_cache
def get_settings() -> Settings:
    return Settings()
