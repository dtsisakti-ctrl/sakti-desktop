"""Test fixtures.

Tests run against a real PostgreSQL (RLS cannot be tested with SQLite or mocks).
Set EXAMGUARD_TEST_SUPERUSER_URL to point at a superuser connection; a throw-away
database `examguard_test` is created, migrated, and truncated between tests.
"""
import os
import re
from datetime import datetime, timedelta, timezone
from uuid import UUID

import psycopg
import pytest
from fastapi.testclient import TestClient

SUPERUSER_URL = os.environ.get("EXAMGUARD_TEST_SUPERUSER_URL",
                               "postgresql://postgres:postgres@127.0.0.1:5432/postgres")
TEST_DB = "examguard_test"
OWNER, OWNER_PW = "examguard_test_owner", "owner-test-pw"
APP, APP_PW = "examguard_test_app", "app-test-pw"
OWNER_URL = f"postgresql+psycopg://{OWNER}:{OWNER_PW}@127.0.0.1:5432/{TEST_DB}"
APP_URL = f"postgresql+psycopg://{APP}:{APP_PW}@127.0.0.1:5432/{TEST_DB}"

os.environ.update({
    "EXAMGUARD_DATABASE_URL": APP_URL,
    "EXAMGUARD_MIGRATION_DATABASE_URL": OWNER_URL,
    "EXAMGUARD_APP_ROLE": APP,
    "EXAMGUARD_ENV": "dev",
})

from examguard import clock  # noqa: E402
from examguard.config import get_settings  # noqa: E402
from examguard.db import reset_engine, transaction  # noqa: E402

NOW = datetime(2026, 10, 1, 2, 0, tzinfo=timezone.utc)
PASSWORD = "correct-horse-battery"
TABLES = ("audit_log", "email_outbox", "identity_photos", "backup_codes", "webhook_deliveries", "events", "incidents", "launch_tokens", "server_keys", "key_sets",
          "commands", "state_transitions", "device_sessions",
          "invigilator_assignments", "invitations", "attempts", "enrollments", "exams",
          "auth_sessions", "one_time_tokens", "candidates", "integrations", "memberships", "users", "organizations")


def owner_conn():
    return psycopg.connect(OWNER_URL.replace("+psycopg", ""), autocommit=True)


@pytest.fixture(scope="session", autouse=True)
def database():
    get_settings.cache_clear()
    reset_engine()
    with psycopg.connect(SUPERUSER_URL, autocommit=True) as c:
        c.execute(f"DROP DATABASE IF EXISTS {TEST_DB} WITH (FORCE)")
        for role, pw in ((OWNER, OWNER_PW), (APP, APP_PW)):
            verb = "ALTER" if c.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (role,)).fetchone() else "CREATE"
            c.execute(f"{verb} ROLE {role} LOGIN PASSWORD '{pw}' NOSUPERUSER NOBYPASSRLS")
        c.execute(f"CREATE DATABASE {TEST_DB} OWNER {OWNER}")
        c.execute(f"GRANT CONNECT ON DATABASE {TEST_DB} TO {APP}")
    from examguard.cli import run_migrations
    run_migrations(OWNER_URL, APP)
    with owner_conn() as c:
        default_settings = c.execute("SELECT settings FROM platform_settings WHERE id = 1").fetchone()[0]
    yield default_settings
    reset_engine()


@pytest.fixture(autouse=True)
def clean(database):
    import json
    with owner_conn() as c:
        c.execute(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE")
        c.execute("UPDATE platform_settings SET settings = %s WHERE id = 1", (json.dumps(database),))
    clock.set_now(NOW)
    yield
    clock.set_now(None)


@pytest.fixture
def client():
    from examguard.main import create_app
    with TestClient(create_app()) as c:
        yield c


# ------------------------------------------------------------------ helpers
class World:
    """Builds organizations, users and candidates, and wraps API calls."""

    def __init__(self, client: TestClient):
        self.c = client

    # --- direct setup (system context, like the CLI)
    def platform_admin(self, email="root@platform.example.com") -> str:
        from examguard.services.orgs import get_or_create_user
        with transaction("system") as db:
            get_or_create_user(db, email, "Root", PASSWORD, platform_admin=True)
        return self.staff_login(email)

    def org(self, slug, *, public=False, admin=None, exam_admin=None) -> UUID:
        from examguard.models import Membership
        from examguard.principal import Principal
        from examguard.services.orgs import create_org, get_or_create_user
        with transaction("system") as db:
            org = create_org(db, Principal(kind="SYSTEM"), slug=slug, name=slug.upper(),
                             can_publish_public=public, admin_email=admin, admin_full_name="Admin",
                             admin_password=PASSWORD)
            if exam_admin:
                u, _ = get_or_create_user(db, exam_admin, "Exam Admin", PASSWORD)
                db.add(Membership(org_id=org.id, user_id=u.id, role="EXAM_ADMIN"))
            return org.id

    def outbox_token(self, email: str, template: str) -> str:
        from sqlalchemy import func, select
        from examguard.models import EmailOutbox
        with transaction("system") as db:
            msg = db.scalars(select(EmailOutbox).where(func.lower(EmailOutbox.to_email) == email.lower(),
                                                       EmailOutbox.template == template)
                             .order_by(EmailOutbox.id.desc())).first()
        assert msg is not None, f"no {template} email for {email}"
        return re.search(r"token=([\w-]+)", msg.body).group(1)

    def outbox(self, email: str) -> list[str]:
        from sqlalchemy import select
        from examguard.models import EmailOutbox
        with transaction("system") as db:
            return [m.template for m in db.scalars(select(EmailOutbox).where(EmailOutbox.to_email == email)
                                                   .order_by(EmailOutbox.id))]

    # --- API
    def staff_login(self, email: str) -> str:
        r = self.c.post("/api/v1/staff/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return r.json()["token"]

    def candidate(self, email: str, *, verify=True, name="Peserta") -> str:
        r = self.c.post("/api/v1/candidate/auth/signup",
                        json={"email": email, "password": PASSWORD, "full_name": name})
        assert r.status_code == 201, r.text
        if verify:
            tok = self.outbox_token(email, "candidate_verify_email")
            assert self.c.post("/api/v1/candidate/auth/verify-email", json={"token": tok}).status_code == 200
        return self.candidate_login(email)

    def candidate_login(self, email: str) -> str:
        r = self.c.post("/api/v1/candidate/auth/login", json={"email": email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        return r.json()["token"]

    @staticmethod
    def h(token: str, org_id: UUID | None = None) -> dict:
        h = {"Authorization": f"Bearer {token}"}
        if org_id:
            h["X-Org-Id"] = str(org_id)
        return h

    def exam_body(self, code="EX1", visibility="PRIVATE", start_in=timedelta(days=7), **kw) -> dict:
        start = NOW + start_in
        body = {"code": code, "name": f"Exam {code}", "visibility": visibility,
                "exam_url": "https://exam.example.edu/run",
                "window_start": start.isoformat(), "window_end": (start + timedelta(hours=2)).isoformat(),
                "duration_minutes": 90}
        if visibility == "PUBLIC":
            body.update(registration_open=NOW.isoformat(),
                        registration_close=(start - timedelta(days=1)).isoformat())
        body.update(kw)
        return body

    def published_exam(self, token, org_id, **kw) -> dict:
        r = self.c.post("/api/v1/org/exams", json=self.exam_body(**kw), headers=self.h(token, org_id))
        assert r.status_code == 201, r.text
        r = self.c.post(f"/api/v1/org/exams/{r.json()['id']}/publish", headers=self.h(token, org_id))
        assert r.status_code == 200, r.text
        return r.json()


@pytest.fixture
def world(client):
    return World(client)


# ------------------------------------------------------------------ Phase 1b helpers
class Exam1b:
    """A published exam with an Exam Admin, plus shortcuts for attempts and the client flow."""

    def __init__(self, world: "World", *, org_slug="acme", code="EX1", identity_check=None, **exam_kw):
        self.w = world
        self.org_admin_email = f"admin@{org_slug}.example.com"
        self.exam_admin_email = f"exams@{org_slug}.example.com"
        self.org_id = world.org(org_slug, admin=self.org_admin_email, exam_admin=self.exam_admin_email)
        self._tokens: dict[str, tuple[str, datetime]] = {}
        kw = dict(exam_kw)
        if identity_check:
            kw["identity_check"] = identity_check
        self.exam = world.published_exam(self.ea, self.org_id, code=code, **kw)
        self.id = UUID(self.exam["id"])
        self.window_start = datetime.fromisoformat(self.exam["window_start"])
        self.latest_start = datetime.fromisoformat(self.exam["latest_start"])
        self.window_end = datetime.fromisoformat(self.exam["window_end"])
        self.checkin_open = datetime.fromisoformat(self.exam["checkin_open"])

    # --- staff (tokens are re-issued when the test clock has moved past their lifetime)
    def token(self, email: str) -> str:
        cached = self._tokens.get(email)
        now = clock.now()
        if cached is None or not timedelta(0) <= now - cached[1] < timedelta(hours=6):
            self._tokens[email] = (self.w.staff_login(email), now)
        return self._tokens[email][0]

    @property
    def ea(self) -> str:
        return self.token(self.exam_admin_email)

    @property
    def admin(self) -> str:
        return self.token(self.org_admin_email)

    def as_(self, email: str) -> str:
        return self.token(email)

    def h(self, token=None):
        return self.w.h(token or self.ea, self.org_id)

    def post(self, path, json=None, token=None):
        return self.w.c.post(f"/api/v1/org{path}", json=json or {}, headers=self.h(token))

    def get(self, path, token=None):
        return self.w.c.get(f"/api/v1/org{path}", headers=self.h(token))

    def add_staff(self, email, role="INVIGILATOR") -> tuple[UUID, str]:
        r = self.w.c.post("/api/v1/org/members", headers=self.h(self.admin),
                          json={"email": email, "role": role, "full_name": "Staff", "initial_password": PASSWORD})
        assert r.status_code == 201, r.text
        return UUID(r.json()["user_id"]), email

    # --- enrollment (direct, like an import)
    def enroll(self, email, *, name="Peserta", accommodation=0) -> UUID:
        from examguard.models import Candidate, Exam
        from examguard.security import hash_password
        from examguard.services.registration import _create_enrollment
        with transaction("system") as db:
            cand = Candidate(email=email, full_name=name, password_hash=hash_password(PASSWORD),
                             email_verified_at=NOW)
            db.add(cand)
            db.flush()
            enr = _create_enrollment(db, db.get(Exam, self.id), cand, "IMPORTED")
            enr.time_accommodation_minutes = accommodation
            db.flush()
            from sqlalchemy import select
            from examguard.models import Attempt
            return db.scalar(select(Attempt.id).where(Attempt.enrollment_id == enr.id))

    # --- client flow (internal services, system context)
    @staticmethod
    def call(fn, *args, **kw):
        with transaction("system") as db:
            return fn(db, *args, **kw)

    def register(self, attempt_id, **kw):
        from examguard.services import client_flow
        return self.call(client_flow.register_device, attempt_id, **kw)

    def launch(self, attempt_id) -> UUID:
        """Register a device session and start (clock must be inside the start window)."""
        from examguard.services import client_flow
        ds = self.register(attempt_id)["device_session_id"]
        self.call(client_flow.start, attempt_id, ds)
        return ds

    def heartbeat(self, ds, seq, **kw):
        from examguard.services import client_flow
        return self.call(client_flow.heartbeat, ds, seq, **kw)

    def attempt(self, attempt_id):
        from examguard.models import Attempt
        with transaction("system") as db:
            return db.get(Attempt, attempt_id)

    def detail(self, attempt_id, token=None):
        r = self.get(f"/attempts/{attempt_id}", token)
        assert r.status_code == 200, r.text
        return r.json()


def at(t: datetime) -> None:
    clock.set_now(t)


@pytest.fixture
def ex(world) -> Exam1b:
    return Exam1b(world)



# ------------------------------------------------------------------ Phase 1c helpers
@pytest.fixture
def root_key():
    """Root trust key (offline in production) + one server key + a published key set."""
    from examguard import crypto, keys
    root = crypto.new_private_key()
    with transaction("system") as db:
        keys.create_server_key(db)
        keys.publish(db, root)
    return root
