"""ExamGuard administration CLI.

    examguard db bootstrap --superuser-url postgresql://postgres:...@127.0.0.1:5432/postgres
    examguard db upgrade
    examguard platform create-admin --email admin@example.com --name "Admin"
    examguard org create --slug acme --name "PT Acme" --admin-email hr@acme.id
    examguard seed demo
    examguard serve --with-scheduler
    examguard scheduler run
    examguard sim launch --exam DEMO-LIVE --email peserta1@demo.example.com
"""
import json
import re
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlsplit

import psycopg
import typer
from psycopg import sql
from sqlalchemy import select

from . import audit, clock
from .config import get_settings
from .db import transaction
from .models import EmailOutbox, Membership, Organization
from .principal import Principal

app = typer.Typer(help="ExamGuard Server administration", no_args_is_help=True)
db_app = typer.Typer(help="Database setup and migrations", no_args_is_help=True)
platform_app = typer.Typer(help="Platform administration", no_args_is_help=True)
org_app = typer.Typer(help="Organizations", no_args_is_help=True)
audit_app = typer.Typer(help="Audit log", no_args_is_help=True)
outbox_app = typer.Typer(help="Email outbox (development)", no_args_is_help=True)
seed_app = typer.Typer(help="Demo data", no_args_is_help=True)
scheduler_app = typer.Typer(help="Time-driven transitions", no_args_is_help=True)
keys_app = typer.Typer(help="Signing keys and the root-signed key set (PRD §19)", no_args_is_help=True)
sim_app = typer.Typer(help="Simulate client actions (development, until the Phase 2 simulator)",
                      no_args_is_help=True)
for sub, name in ((db_app, "db"), (platform_app, "platform"), (org_app, "org"),
                  (audit_app, "audit"), (outbox_app, "outbox"), (seed_app, "seed"),
                  (scheduler_app, "scheduler"), (sim_app, "sim"), (keys_app, "keys")):
    app.add_typer(sub, name=name)

SYSTEM = Principal(kind="SYSTEM")
IDENT = re.compile(r"^[a-z_][a-z0-9_]{0,62}$")
ROOT = Path(__file__).resolve().parents[2]


def _conn_parts(url: str) -> dict:
    u = urlsplit(url.replace("+psycopg", ""))
    return {"user": u.username, "password": u.password, "host": u.hostname or "127.0.0.1",
            "port": u.port or 5432, "dbname": u.path.lstrip("/")}


def _fail(msg: str) -> None:
    typer.secho(msg, fg=typer.colors.RED, err=True)
    raise typer.Exit(1)


# ------------------------------------------------------------------ db
@db_app.command("bootstrap")
def db_bootstrap(
    superuser_url: str = typer.Option(..., help="postgresql://postgres:pw@host:5432/postgres"),
    drop_existing: bool = typer.Option(False, help="DROP the database first (development only!)"),
):
    """Create the owner role, runtime role and database described by the EXAMGUARD_* URLs."""
    s = get_settings()
    owner, app_ = _conn_parts(s.migration_database_url), _conn_parts(s.database_url)
    if owner["dbname"] != app_["dbname"]:
        _fail("DATABASE_URL and MIGRATION_DATABASE_URL must point to the same database")
    for r in (owner["user"], app_["user"]):
        if not IDENT.match(r or ""):
            _fail(f"invalid role name {r!r}")
    if app_["user"] != s.app_role:
        _fail("EXAMGUARD_APP_ROLE must match the user in EXAMGUARD_DATABASE_URL")
    dbname = owner["dbname"]
    with psycopg.connect(superuser_url.replace("+psycopg", ""), autocommit=True) as c:
        if drop_existing:
            if not s.is_dev:
                _fail("--drop-existing is only allowed with EXAMGUARD_ENV=dev")
            c.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(dbname)))
        for role, pw, extra in ((owner["user"], owner["password"], ""), (app_["user"], app_["password"], "")):
            exists = c.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            c.execute(sql.SQL(verb + " ROLE {} LOGIN PASSWORD {} NOSUPERUSER NOBYPASSRLS").format(
                sql.Identifier(role), sql.Literal(pw)))
        if not c.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dbname,)).fetchone():
            c.execute(sql.SQL("CREATE DATABASE {} OWNER {}").format(
                sql.Identifier(dbname), sql.Identifier(owner["user"])))
        c.execute(sql.SQL("REVOKE ALL ON DATABASE {} FROM PUBLIC").format(sql.Identifier(dbname)))
        c.execute(sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
            sql.Identifier(dbname), sql.Identifier(app_["user"])))
    typer.secho(f"database '{dbname}' ready (owner={owner['user']}, runtime={app_['user']})",
                fg=typer.colors.GREEN)


def run_migrations(url: str | None = None, app_role: str | None = None) -> None:
    from alembic import command
    from alembic.config import Config

    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    if url:
        cfg.attributes["url"] = url
    if app_role:
        cfg.attributes["app_role"] = app_role
    command.upgrade(cfg, "head")


@db_app.command("upgrade")
def db_upgrade():
    """Apply migrations (as the owner role)."""
    run_migrations()
    typer.secho("migrations applied", fg=typer.colors.GREEN)


# ------------------------------------------------------------------ platform
@platform_app.command("create-admin")
def create_admin(
    email: str = typer.Option(...),
    name: str = typer.Option(...),
    password: str = typer.Option(..., prompt=True, hide_input=True, confirmation_prompt=True),
):
    """Create a platform administrator (or promote an existing staff user)."""
    from .services.orgs import get_or_create_user

    with transaction("system") as db:
        user, created = get_or_create_user(db, email, name, password, platform_admin=True)
        audit.record(db, org_id=None, actor_kind="system", actor_id=None, action="platform_admin.granted",
                     target_type="user", target_id=user.id, data={"email": email, "created": created})
    typer.secho(f"platform admin {'created' if created else 'granted'}: {email}", fg=typer.colors.GREEN)


# ------------------------------------------------------------------ organizations
@org_app.command("create")
def org_create(
    slug: str = typer.Option(...),
    name: str = typer.Option(...),
    public: bool = typer.Option(False, "--public", help="Allow publishing PUBLIC exams"),
    admin_email: str | None = typer.Option(None),
    admin_name: str | None = typer.Option(None),
    admin_password: str | None = typer.Option(None, help="Required when the admin account is new"),
):
    from .services.orgs import create_org

    with transaction("system") as db:
        org = create_org(db, SYSTEM, slug=slug, name=name, can_publish_public=public,
                         admin_email=admin_email, admin_full_name=admin_name, admin_password=admin_password)
        typer.secho(f"organization {org.slug} created: {org.id}", fg=typer.colors.GREEN)


@org_app.command("list")
def org_list():
    with transaction("system") as db:
        for o in db.scalars(select(Organization).order_by(Organization.slug)):
            n = len(list(db.scalars(select(Membership.id).where(Membership.org_id == o.id))))
            typer.echo(f"{o.slug:24} {str(o.id)}  public={o.can_publish_public!s:5}  members={n}  {o.name}")


@org_app.command("add-member")
def org_add_member(
    org: str = typer.Option(..., help="organization slug"),
    email: str = typer.Option(...),
    role: str = typer.Option(..., help="ORG_ADMIN | EXAM_ADMIN | INVIGILATOR"),
    name: str | None = typer.Option(None),
    password: str | None = typer.Option(None),
):
    from .services.orgs import get_or_create_user, get_org_by_slug

    if role not in ("ORG_ADMIN", "EXAM_ADMIN", "INVIGILATOR"):
        _fail("invalid role")
    with transaction("system") as db:
        o = get_org_by_slug(db, org)
        user, _ = get_or_create_user(db, email, name, password)
        if db.scalar(select(Membership.id).where(Membership.org_id == o.id, Membership.user_id == user.id,
                                                 Membership.role == role)):
            _fail("membership already exists")
        db.add(Membership(org_id=o.id, user_id=user.id, role=role))
        audit.record(db, org_id=o.id, actor_kind="system", actor_id=None, action="member.added",
                     target_type="user", target_id=user.id, data={"email": email, "role": role})
    typer.secho(f"{email} is now {role} of {org}", fg=typer.colors.GREEN)


# ------------------------------------------------------------------ audit
@audit_app.command("verify")
def audit_verify(
    org: str | None = typer.Option(None, help="organization slug; omit for all chains"),
):
    """Recompute hash chains and report the first broken entry, if any."""
    from .services.orgs import get_org_by_slug

    with transaction("system") as db:
        if org:
            chains = [audit.chain_key(get_org_by_slug(db, org).id)]
        else:
            chains = ["platform"] + [audit.chain_key(o) for o in db.scalars(select(Organization.id))]
        bad = 0
        for ch in chains:
            r = audit.verify(db, ch)
            color = typer.colors.GREEN if r["ok"] else typer.colors.RED
            typer.secho(f"{ch:48} ok={r['ok']!s:5} entries={r['checked']}"
                        + ("" if r["ok"] else f"  first_bad_seq={r['first_bad_seq']} ({r['reason']})"),
                        fg=color)
            bad += not r["ok"]
    raise typer.Exit(1 if bad else 0)


# ------------------------------------------------------------------ outbox
@outbox_app.command("list")
def outbox_list(limit: int = typer.Option(20), to: str | None = typer.Option(None)):
    with transaction("system") as db:
        q = select(EmailOutbox).order_by(EmailOutbox.id.desc()).limit(limit)
        if to:
            q = q.where(EmailOutbox.to_email == to)
        for m in db.scalars(q):
            typer.secho(f"#{m.id} {m.created_at:%Y-%m-%d %H:%M} to={m.to_email} [{m.template}] {m.subject}",
                        bold=True)
            typer.echo(m.body)


# ------------------------------------------------------------------ demo data
@seed_app.command("demo")
def seed_demo(password: str = typer.Option("demo-password-123", help="password for all demo accounts"),
              live_in_minutes: int = typer.Option(5, min=1, help="DEMO-LIVE exam starts this many minutes from now")):
    """Create demo platform admin, a public-test organization, a company, and exams."""
    from .schemas import ExamCreateIn
    from .services import exams
    from .services.orgs import create_org, get_or_create_user

    now = clock.now().replace(minute=0, second=0, microsecond=0)
    with transaction("system") as db:
        if db.scalar(select(Organization.id).where(Organization.slug == "examguard-public")):
            _fail("demo data already present")
        get_or_create_user(db, "platform@demo.example.com", "Platform Admin", password, platform_admin=True)
        pub = create_org(db, SYSTEM, slug="examguard-public", name="ExamGuard Public Testing",
                         can_publish_public=True, admin_email="admin@public.demo.example.com",
                         admin_full_name="Public Program Admin", admin_password=password)
        acme = create_org(db, SYSTEM, slug="pt-contoh-jaya", name="PT Contoh Jaya",
                          can_publish_public=False, admin_email="hr@contohjaya.demo.example.com",
                          admin_full_name="HR Contoh Jaya",
                          admin_password=password)
        for org in (pub, acme):
            u, _ = get_or_create_user(db, f"exams@{org.slug}.demo.example.com", f"Exam Admin {org.name}", password)
            db.add(Membership(org_id=org.id, user_id=u.id, role="EXAM_ADMIN"))
        db.flush()

        def mk(org, code, name, visibility, start_days, series=None, capacity=None):
            actor = Principal(kind="STAFF", org_id=org.id)
            start = now + timedelta(days=start_days, hours=9 - now.hour)
            body = ExamCreateIn(code=code, name=name, visibility=visibility, series=series,
                                exam_url="http://localhost:8100/exam", window_start=start,
                                window_end=start + timedelta(minutes=120), duration_minutes=90,
                                capacity=capacity,
                                registration_open=now if visibility == "PUBLIC" else None,
                                registration_close=start - timedelta(days=1) if visibility == "PUBLIC" else None)
            exam = exams.create_exam(db, actor, body)
            exams.publish(db, actor, exam.id)
            return exam

        mk(pub, "EPT-2026-10-A", "English Proficiency Test — Sesi A", "PUBLIC", 7, "EPT", 200)
        mk(pub, "EPT-2026-10-B", "English Proficiency Test — Sesi B", "PUBLIC", 14, "EPT", 200)
        mk(acme, "REKRUT-ENG-01", "Tes Rekrutmen Engineer", "PRIVATE", 10)

        # A private exam that starts shortly, for trying Phase 1b with `examguard sim`.
        from .models import Candidate, InvigilatorAssignment
        from .security import hash_password
        from .services.registration import _create_enrollment
        actor = Principal(kind="STAFF", org_id=acme.id)
        live_start = clock.now().replace(second=0, microsecond=0) + timedelta(minutes=live_in_minutes)
        live = exams.create_exam(db, actor, ExamCreateIn(
            code="DEMO-LIVE", name="Demo Ujian Langsung", visibility="PRIVATE",
            exam_url="http://localhost:8100/exam", window_start=live_start,
            window_end=live_start + timedelta(minutes=120), duration_minutes=90))
        exams.publish(db, actor, live.id)
        inv, _ = get_or_create_user(db, "pengawas@pt-contoh-jaya.demo.example.com", "Pengawas Demo", password)
        db.add(Membership(org_id=acme.id, user_id=inv.id, role="INVIGILATOR"))
        db.add(InvigilatorAssignment(exam_id=live.id, user_id=inv.id))
        for i in range(1, 4):
            cand = Candidate(email=f"peserta{i}@demo.example.com", full_name=f"Peserta Demo {i}",
                             password_hash=hash_password(password), email_verified_at=clock.now())
            db.add(cand)
            db.flush()
            _create_enrollment(db, live, cand, "IMPORTED")
    kid = ensure_dev_keys()
    typer.secho("demo data created; all accounts use the given password", fg=typer.colors.GREEN)
    if kid:
        typer.echo(f"dev signing keys created (server key {kid}, root key {DEV_ROOT_KEY})")
    for e in ("platform@demo.example.com", "admin@public.demo.example.com", "exams@examguard-public.demo.example.com",
              "hr@contohjaya.demo.example.com", "exams@pt-contoh-jaya.demo.example.com",
              "pengawas@pt-contoh-jaya.demo.example.com  (INVIGILATOR, assigned to DEMO-LIVE)",
              "peserta1..3@demo.example.com  (candidates enrolled in DEMO-LIVE)"):
        typer.echo(f"  {e}")
    typer.echo(f"DEMO-LIVE: check-in {live.checkin_open:%H:%M}, start {live_start:%H:%M} UTC "
               f"(latest start {live.latest_start:%H:%M})")


# ------------------------------------------------------------------ misc
@app.command("serve")
def serve(host: str = "127.0.0.1", port: int = 8000, reload: bool = False,
          with_scheduler: bool = typer.Option(False, "--with-scheduler",
                                              help="also run the scheduler in a background thread"),
          scheduler_interval: float = typer.Option(2.0, help="seconds between scheduler ticks")):
    import logging

    import uvicorn

    if with_scheduler:
        if reload:
            _fail("--with-scheduler cannot be combined with --reload; run `examguard scheduler run` instead")
        from .scheduler import start_background
        logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(name)s %(message)s")
        logging.getLogger("examguard.scheduler").setLevel(logging.INFO)
        start_background(scheduler_interval)
        typer.secho(f"scheduler running every {scheduler_interval:g}s", fg=typer.colors.GREEN)
    uvicorn.run("examguard.main:app", host=host, port=port, reload=reload)


# ------------------------------------------------------------------ scheduler
@scheduler_app.command("run")
def scheduler_run(once: bool = typer.Option(False, "--once", help="run a single tick and exit"),
                  interval: float = typer.Option(2.0, help="seconds between ticks")):
    """Run time-driven transitions. Safe to run next to the server or on several machines."""
    import logging
    import time

    from .scheduler import tick

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    while True:
        counts = tick()
        typer.echo(f"{clock.now():%H:%M:%S} " + " ".join(f"{k}={v}" for k, v in counts.items()))
        if once:
            return
        time.sleep(interval)


# ------------------------------------------------------------------ client simulation (dev)
def _resolve_attempt(db, attempt: str | None, exam: str | None, email: str | None, org: str | None):
    from uuid import UUID

    from sqlalchemy import func

    from .models import Attempt, Candidate, Enrollment, Exam
    if attempt:
        return db.get(Attempt, UUID(attempt)) or _fail("attempt not found")
    if not (exam and email):
        _fail("give --attempt ID, or --exam CODE and --email EMAIL")
    q = (select(Attempt).join(Enrollment, Enrollment.id == Attempt.enrollment_id)
         .join(Exam, Exam.id == Enrollment.exam_id).join(Candidate, Candidate.id == Enrollment.candidate_id)
         .where(Exam.code == exam, func.lower(Candidate.email) == email.lower(), Enrollment.status == "CONFIRMED"))
    if org:
        q = q.join(Organization, Organization.id == Exam.org_id).where(Organization.slug == org)
    rows = list(db.scalars(q))
    if len(rows) != 1:
        _fail("no matching attempt" if not rows else "ambiguous; add --org SLUG")
    return rows[0]


def _show(result: dict) -> None:
    for k in ("device_session_id", "device_status", "status", "state_version", "deadline", "identity_status"):
        if k in result and result[k] is not None:
            v = result[k]
            typer.echo(f"  {k:18} {v.isoformat() if hasattr(v, 'isoformat') else v}")


_ATTEMPT = typer.Option(None, "--attempt", help="attempt id")
_EXAM = typer.Option(None, "--exam", help="exam code (with --email)")
_EMAIL = typer.Option(None, "--email", help="candidate email (with --exam)")
_ORG = typer.Option(None, "--org", help="organization slug, if the exam code is ambiguous")


@sim_app.command("attempts")
def sim_attempts(exam: str = typer.Option(..., "--exam"), org: str | None = _ORG):
    """List attempts of an exam with their current state."""
    from .models import Attempt, Candidate, Enrollment, Exam
    with transaction("system") as db:
        q = (select(Attempt, Candidate.email).join(Enrollment, Enrollment.id == Attempt.enrollment_id)
             .join(Exam, Exam.id == Enrollment.exam_id).join(Candidate, Candidate.id == Enrollment.candidate_id)
             .where(Exam.code == exam).order_by(Candidate.email))
        if org:
            q = q.join(Organization, Organization.id == Exam.org_id).where(Organization.slug == org)
        for a, email in db.execute(q).all():
            dl = f"{a.deadline:%H:%M:%S}" if a.deadline else "-"
            typer.echo(f"{a.id}  {email:32} {a.status:24} v{a.state_version:<3} deadline={dl}")


@sim_app.command("launch")
def sim_launch(attempt: str | None = _ATTEMPT, exam: str | None = _EXAM, email: str | None = _EMAIL,
               org: str | None = _ORG,
               new_device: bool = typer.Option(False, "--new-device",
                                               help="launch on another device although one is active")):
    """Register a device session and start the attempt (what the client does after preflight).

    A client that restarts on the same device keeps its device session and just sends
    heartbeats (`sim heartbeat`); launching again means a different device (PRD §18).
    """
    from . import sessions
    from .services import client_flow
    with transaction("system") as db:
        a = _resolve_attempt(db, attempt, exam, email, org)
        if sessions.active(db, a.id) and a.status in ("ACTIVE", "INTERRUPTED") and not new_device:
            _fail("attempt already has an active device; use `sim heartbeat`, or --new-device "
                  "to simulate switching devices (needs invigilator approval)")
        r = client_flow.register_device(db, a.id, client_version="sim", os_info={"os": "simulated"})
        if r["status"] == "NOT_STARTED" and r["device_status"] == "ACTIVE":
            r = {**r, **client_flow.start(db, a.id, r["device_session_id"])}
    typer.secho("launched", fg=typer.colors.GREEN)
    _show(r)


@sim_app.command("register")
def sim_register(attempt: str | None = _ATTEMPT, exam: str | None = _EXAM, email: str | None = _EMAIL,
                 org: str | None = _ORG):
    """Register a device session only (e.g. a second device, or before an identity check)."""
    from .services import client_flow
    with transaction("system") as db:
        a = _resolve_attempt(db, attempt, exam, email, org)
        r = client_flow.register_device(db, a.id, client_version="sim", os_info={"os": "simulated"})
    _show(r)


@sim_app.command("identity")
def sim_identity(attempt: str | None = _ATTEMPT, exam: str | None = _EXAM, email: str | None = _EMAIL,
                 org: str | None = _ORG):
    """Submit the identity check (photos arrive in Phase 1c)."""
    from .services import client_flow
    with transaction("system") as db:
        a = _resolve_attempt(db, attempt, exam, email, org)
        _show(client_flow.submit_identity(db, a.id))


@sim_app.command("start")
def sim_start(attempt: str | None = _ATTEMPT, exam: str | None = _EXAM, email: str | None = _EMAIL,
              org: str | None = _ORG):
    """Start with the attempt's active device session."""
    from . import sessions
    from .services import client_flow
    with transaction("system") as db:
        a = _resolve_attempt(db, attempt, exam, email, org)
        ds = sessions.active(db, a.id) or _fail("no active device session; run `sim register` first")
        _show(client_flow.start(db, a.id, ds.id))


@sim_app.command("heartbeat")
def sim_heartbeat(attempt: str | None = _ATTEMPT, exam: str | None = _EXAM, email: str | None = _EMAIL,
                  org: str | None = _ORG,
                  count: int = typer.Option(1, help="number of heartbeats; 0 = until Ctrl+C"),
                  interval: float = typer.Option(10.0, help="seconds between heartbeats"),
                  cause: str | None = typer.Option(None, help="NETWORK_FAILURE | UNEXPECTED_SHUTDOWN | CLIENT_CRASH")):
    """Send heartbeats from the attempt's device (pending device if one is waiting for approval)."""
    import time

    from . import sessions
    from .services import client_flow
    n = 0
    while count == 0 or n < count:
        with transaction("system") as db:
            a = _resolve_attempt(db, attempt, exam, email, org)
            ds = sessions.pending(db, a.id) or sessions.active(db, a.id) or _fail("no device session")
            r = client_flow.heartbeat(db, ds.id, ds.last_heartbeat_seq + 1, cause=cause)
        n += 1
        dl = r["deadline"].strftime("%H:%M:%S") if r["deadline"] else "-"
        typer.echo(f"{clock.now():%H:%M:%S} #{n} {r['status']} v{r['state_version']} deadline={dl}")
        if count == 0 or n < count:
            time.sleep(interval)


@sim_app.command("submit")
def sim_submit(attempt: str | None = _ATTEMPT, exam: str | None = _EXAM, email: str | None = _EMAIL,
               org: str | None = _ORG):
    """Finish normally (Level 0 'Selesai Ujian')."""
    from .services import client_flow
    with transaction("system") as db:
        a = _resolve_attempt(db, attempt, exam, email, org)
        _show(client_flow.submit(db, a.id))


@app.command("openapi")
def openapi(out: Path = typer.Option(Path("openapi.json"))):
    from .main import app as fastapi_app

    out.write_text(json.dumps(fastapi_app.openapi(), indent=2), encoding="utf-8")
    typer.secho(f"wrote {out}", fg=typer.colors.GREEN)


# ------------------------------------------------------------------ keys (PRD §19)
DEV_ROOT_KEY = Path(".examguard") / "dev-root.key"


def _load_root(path: Path):
    from . import crypto
    if not path.exists():
        _fail(f"root key file {path} not found (create one with `examguard keys init-root`)")
    return crypto.load_private_pem(path.read_bytes())


@keys_app.command("init-root")
def keys_init_root(out: Path = typer.Option(..., "--out", help="where to write the ROOT private key (keep offline)"),
                   force: bool = False):
    """Create the root trust key. Its public key goes into the client binary and EXAMGUARD_ROOT_PUBLIC_KEY."""
    from . import crypto, keys
    if out.exists() and not force:
        _fail(f"{out} exists; use --force to overwrite")
    key = crypto.new_private_key()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(crypto.private_pem(key))
    pub = crypto.public_raw(key)
    typer.secho(f"root key written to {out} — keep it OFFLINE", fg=typer.colors.GREEN)
    typer.echo(f"root kid:   {keys.root_kid(pub)}")
    typer.echo(f"EXAMGUARD_ROOT_PUBLIC_KEY={pub}")


@keys_app.command("rotate")
def keys_rotate(root_key: Path = typer.Option(..., "--root-key"), valid_days: int = typer.Option(90, min=1),
                retire_old: bool = typer.Option(False, help="mark older ACTIVE keys RETIRED (still published)")):
    """Create a new server signing key and publish a key set signed with the root key."""
    from . import keys
    from .models import ServerKey
    root = _load_root(root_key)
    with transaction("system") as db:
        if retire_old:
            for k in db.scalars(select(ServerKey).where(ServerKey.status == "ACTIVE")):
                k.status = "RETIRED"
        row = keys.create_server_key(db, valid_days=valid_days)
        keys.publish(db, root)
    typer.secho(f"new server key {row.kid_base} (valid until {row.not_after:%Y-%m-%d}); key set published",
                fg=typer.colors.GREEN)


@keys_app.command("publish")
def keys_publish(root_key: Path = typer.Option(..., "--root-key")):
    """Re-sign and publish the key set (e.g. after a revoke, or before keys expire)."""
    from . import keys
    with transaction("system") as db:
        env = keys.publish(db, _load_root(root_key))
    typer.secho(f"key set published ({len(json.loads(env['body'])['keys'])} entries)", fg=typer.colors.GREEN)


@keys_app.command("revoke")
def keys_revoke(kid_base: str, root_key: Path = typer.Option(..., "--root-key")):
    """Revoke a server key and publish the key set with it marked revoked."""
    from . import keys
    with transaction("system") as db:
        keys.set_status(db, kid_base, "REVOKED")
        keys.publish(db, _load_root(root_key))
    typer.secho(f"{kid_base} revoked; key set published", fg=typer.colors.YELLOW)


@keys_app.command("list")
def keys_list():
    from .models import ServerKey
    with transaction("system") as db:
        for k in db.scalars(select(ServerKey).order_by(ServerKey.not_before)):
            typer.echo(f"{k.kid_base:28} {k.status:8} {k.not_before:%Y-%m-%d} → {k.not_after:%Y-%m-%d}  "
                       f"uses={','.join(k.uses)}")


def ensure_dev_keys() -> str | None:
    """Development only: create a local root key and a server key if none is active."""
    from . import keys
    from .models import ServerKey
    if not get_settings().is_dev:
        return None
    with transaction("system") as db:
        if db.scalar(select(ServerKey).where(ServerKey.status == "ACTIVE")) is not None:
            return None
    if not DEV_ROOT_KEY.exists():
        from . import crypto
        DEV_ROOT_KEY.parent.mkdir(parents=True, exist_ok=True)
        DEV_ROOT_KEY.write_bytes(crypto.private_pem(crypto.new_private_key()))
    root = _load_root(DEV_ROOT_KEY)
    with transaction("system") as db:
        row = keys.create_server_key(db)
        keys.publish(db, root)
    return row.kid_base


@keys_app.command("dev-init")
def keys_dev_init():
    """Development shortcut: root key in .examguard/dev-root.key + a server key + published key set."""
    kid = ensure_dev_keys()
    if kid is None:
        typer.echo("an active server key already exists (or EXAMGUARD_ENV is not dev)")
    else:
        typer.secho(f"dev keys ready: server key {kid}, root key {DEV_ROOT_KEY}", fg=typer.colors.GREEN)


@sim_app.command("link")
def sim_link(attempt: str | None = _ATTEMPT, exam: str | None = _EXAM, email: str | None = _EMAIL,
             org: str | None = _ORG):
    """Create a launch link for a candidate (what the Candidate Portal shows)."""
    from .models import Candidate, Enrollment
    from .services import protocol
    with transaction("system") as db:
        a = _resolve_attempt(db, attempt, exam, email, org)
        enr = db.get(Enrollment, a.enrollment_id)
        r = protocol.issue_launch_token(db, db.get(Candidate, enr.candidate_id), enr.id)
    typer.echo(r["launch_url"])
    typer.echo(f"expires {r['expires_at']:%H:%M:%S} UTC")


@seed_app.command("live-exam")
def seed_live_exam(org: str = typer.Option("pt-contoh-jaya", help="organization slug"),
                   in_minutes: int = typer.Option(5, min=1, help="window starts this many minutes from now"),
                   candidates: int = typer.Option(3, min=1, max=50),
                   password: str = typer.Option("demo-password-123", help="password for new candidate accounts"),
                   identity_check: str = typer.Option("NONE", help="NONE | MANUAL (selfie + ID card, Check-in Queue)")):
    """A new private exam that starts shortly, without resetting the database (for trying the flows)."""
    if identity_check not in ("NONE", "MANUAL"):
        _fail("--identity-check must be NONE or MANUAL")
    from sqlalchemy import func

    from .models import Candidate, Exam, InvigilatorAssignment
    from .schemas import ExamCreateIn
    from .security import hash_password
    from .services import exams
    from .services.registration import _create_enrollment
    with transaction("system") as db:
        o = db.scalar(select(Organization).where(Organization.slug == org)) or _fail(f"organization {org} not found")
        actor = Principal(kind="STAFF", org_id=o.id)
        start = clock.now().replace(second=0, microsecond=0) + timedelta(minutes=in_minutes)
        base = f"LIVE-{start:%m%d-%H%M}"
        taken = set(db.scalars(select(Exam.code).where(Exam.org_id == o.id, Exam.code.like(f"{base}%"))))
        code = base if base not in taken else next(f"{base}-{n}" for n in range(2, 1000) if f"{base}-{n}" not in taken)
        live = exams.create_exam(db, actor, ExamCreateIn(
            code=code, name=f"Ujian Uji {start:%d/%m %H:%M} UTC", visibility="PRIVATE",
            exam_url="http://localhost:8100/exam", window_start=start,
            window_end=start + timedelta(minutes=120), duration_minutes=90, identity_check=identity_check))
        exams.publish(db, actor, live.id)
        for m in db.scalars(select(Membership).where(Membership.org_id == o.id, Membership.role == "INVIGILATOR")):
            db.add(InvigilatorAssignment(exam_id=live.id, user_id=m.user_id))
        emails = []
        for i in range(1, candidates + 1):
            email = f"peserta{i}@demo.example.com"
            cand = db.scalar(select(Candidate).where(func.lower(Candidate.email) == email))
            if cand is None:
                cand = Candidate(email=email, full_name=f"Peserta Demo {i}", password_hash=hash_password(password),
                                 email_verified_at=clock.now())
                db.add(cand)
                db.flush()
            _create_enrollment(db, live, cand, "IMPORTED")
            emails.append(email)
    ensure_dev_keys()
    typer.secho(f"{code} created in {org}: {len(emails)} candidates, invigilators assigned", fg=typer.colors.GREEN)
    typer.echo(f"check-in {live.checkin_open:%H:%M}, start {start:%H:%M} UTC, latest start {live.latest_start:%H:%M} UTC")
    typer.echo(f"try: examguard sim launch --exam {code} --email {emails[0]}")


def main() -> None:
    """Console entry point: business and database errors are printed as one line, not a traceback."""
    from sqlalchemy.exc import OperationalError as SAOperationalError

    from .errors import AppError

    try:
        app()
    except AppError as e:
        typer.secho(f"{e.code}: {e.message}" + (f"  {e.details}" if e.details else ""),
                    fg=typer.colors.RED, err=True)
        raise SystemExit(1)
    except (psycopg.OperationalError, SAOperationalError) as e:
        orig = getattr(e, "orig", e)
        msg = str(orig).strip().splitlines()[0] if str(orig).strip() else type(orig).__name__
        hint = ("check the password in .env / --superuser-url" if "password authentication failed" in msg
                else "is PostgreSQL (Docker) running and is the host/port in .env correct?")
        typer.secho(f"DATABASE_UNAVAILABLE: {msg}\n  hint: {hint}", fg=typer.colors.RED, err=True)
        raise SystemExit(2)


if __name__ == "__main__":
    main()
