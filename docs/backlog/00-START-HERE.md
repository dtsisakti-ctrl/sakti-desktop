# 00-START-HERE: ExamGuard Developer Quickstart

Welcome to **ExamGuard** (PRD v0.3.7) — the secure exam browser, device lockdown, and proctoring platform for the SAKTI ecosystem.

---

## 1. System Ecosystem & Current Condition (Phase 3b-1 Complete)

ExamGuard consists of:
1. **`examguard-server`** (Port 8080): Python FastAPI authoritative server managing state machines, timing, Ed25519 signing keys, LMS Integration API, signed webhooks, and scheduler.
2. **`examguard-web`**: React + Vite + TypeScript application built and hosted directly by the server:
   - **`/admin/`**: Admin Web for exam organizers, proctors, and invigilators (live monitoring console, incident timeline, emergency actions).
   - **`/portal/`**: Candidate Portal for test-takers (account registration, email verification, catalog, launch token generation).
   - **`/`**: Unified landing portal ("Masuk sebagai Peserta" vs "Masuk sebagai Staf").
3. **`ExamGuard Client`**: Secure cross-platform desktop browser built with **Rust + Chromium Embedded Framework (CEF)** with ONNX Runtime for local AI proctoring (Phase 2 headless simulator `eg-sim` complete; Phase 5 full GUI client in roadmap).

---

## 2. 60-Minute Quickstart

### Step 1: Python Environment & Server Dependencies
From `sakti-desktop/examguard-server/`:
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
```

### Step 2: Configure Environment & Database
```bash
Copy-Item .env.example .env
```
Ensure PostgreSQL and Redis are running (or use SAKTI Docker containers on port 5433 and 6379):
```bash
examguard db upgrade
```

### Step 3: Seed Demo Live Exam & Test Accounts
```bash
examguard seed live-exam --identity-check MANUAL
```
This provisions a live testing session with an active check-in queue, mock candidate attempts, and invigilators.

### Step 4: Run Server with Background Scheduler
```bash
examguard serve --port 8080 --with-scheduler
```
Server starts on `http://127.0.0.1:8080/`.

---

## 3. Seed Accounts & Roles

| Email | Password | Role | Access Scope |
| :--- | :--- | :--- | :--- |
| `admin@pt-contoh-jaya.demo.example.com` | `Password123!` | `ORG_ADMIN` | Full organization settings, members, LMS integrations |
| `exams@pt-contoh-jaya.demo.example.com` | `Password123!` | `EXAM_ADMIN` | Exam authoring, schedule windows, security policy |
| `pengawas@pt-contoh-jaya.demo.example.com`| `Password123!` | `INVIGILATOR` | Assigned exam live monitoring grid, check-in, emergency unlock |
| *Candidate Register* | *Self-registered* | `CANDIDATE` | Personal portal at `/portal/`, session catalog, launch link |

*Tip: In development, verification emails can be read directly via CLI:*
```bash
examguard outbox list --to <email>
```

---

## 4. Engineering Non-Negotiables

1. **State Machine As Single Source of Truth**: Attempt status (`ACTIVE`, `INTERRUPTED`, `COMPLETED`, `TERMINATED`) and exam status (`DRAFT`, `READY`, `RUNNING`, `CLOSED`) must follow the formal transition matrix in `docs/backlog/00-standards/state-machines.md`.
2. **Ed25519 Request Signing (`EG-Sig`)**: Every client request, heartbeat, and command envelope is signed with Ed25519. Unsigned or invalid signature requests are rejected.
3. **Simultaneous Disconnection Rule**: Sockets closing (crash, kill) trigger `INTERRUPTED` and `OFFLINE` status simultaneously within $\le 2$ seconds.
4. **Desktop Screen Design Priority**: Both Admin Web and Candidate Portal are designed for desktop/laptop screens where the actual examinations occur.

