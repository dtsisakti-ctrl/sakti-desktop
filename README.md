# sakti-desktop (ExamGuard & Safe Exam Browser Kiosk)

The desktop lockdown, operating system kiosk enforcement, and secure proctoring client repository for the SAKTI ecosystem.

---

## Strategic Vision: The SAKTI Safe Exam Browser (SEB) Replica

As established in **[SPEC-DESK-01](docs/specs/2026-11-18-seb-desktop-lockdown-architecture-and-redundancy-analysis.md)**:
`sakti-desktop` serves as the native desktop wrapper (**Safe Exam Browser replica**) that turns a student's laptop into a secure kiosk:
1. **OS Kiosk Lockdown**: Intercepts low-level keyboard input (`SetWindowsHookEx`), blocking `Alt + Tab`, `Windows Key`, `Alt + F4`, `Ctrl + Alt + Del`, and `Cmd + Tab`.
2. **Process Guardian**: Continuously scans running processes, terminating prohibited software (Discord, AnyDesk, TeamViewer, OBS Studio, ChatGPT).
3. **Multi-Monitor Enforcement**: Detects and blanks secondary displays.
4. **Embedded WebView**: Embeds **`SAKTI-Participant-App`** (`https://participant.sakti.ac.id`), whitelisting only SAKTI URLs and disabling DevTools, inspect element, and copy-paste.
5. **Hardware Attestation Header**: Transmits `X-Sakti-Desktop-Signature` to `SAKTI-Backend` to cryptographically prove the exam is running inside the official locked desktop client.

---

## Project Structure

```
sakti-desktop/
├── docs/
│   ├── ExamGuard_PRD_v0_3_7.md    # Upstream PRD detailing lockdown & event dictionaries
│   ├── Claude-Chat-History-Izzat.md # Implementation and architectural log
│   ├── specs/
│   │   └── 2026-11-18-seb-desktop-lockdown-architecture-and-redundancy-analysis.md
│   └── backlog/                   # Kalbe-Optimus Backlog System (BL-EG-01..05 DONE, BL-DESK-01..02)
├── examguard-server/              # Standalone Python FastAPI server & timing engine
│   ├── src/examguard/
│   │   ├── api/                   # Client wire endpoints, org admin & candidate APIs
│   │   ├── core/                  # Attempt state engine, timing formulas & scheduler
│   │   ├── crypto/                # Ed25519 signing (EG-Sig) & challenge unlock
│   │   └── models/                # SQLAlchemy models & RLS context
│   ├── migrations/                # Alembic database migrations (0001–0006)
│   ├── tests/                     # 172 unit & integration tests
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── .env.example
└── examguard-web/                 # Vite + React multi-entrypoint web app
    ├── admin/                     # Admin Web & Live Monitoring Console (/admin/)
    ├── portal/                    # Candidate Portal & deep link launcher (/portal/)
    ├── e2e/                       # Playwright browser automation tests
    ├── package.json
    └── vite.config.ts
```

---

## Prerequisites

- [Python](https://www.python.org/) (v3.11+ recommended)
- [Node.js](https://nodejs.org/) (v18.x or v20.x)
- Running PostgreSQL database (port 5433) and Redis (port 6379)
- [Rust & Cargo](https://rustup.rs/) (for desktop client development in Phase 4/5)

---

## Local Development Quickstart

### 1. Running the Reference Server (`examguard-server`)

From `sakti-desktop/examguard-server/`:

```powershell
# 1. Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate

# 2. Install dependencies in editable development mode
pip install -e ".[dev]"

# 3. Configure environment
Copy-Item .env.example .env

# 4. Apply database migrations (0001 -> 0006)
examguard db upgrade

# 5. Seed live test exam with manual check-in queue
examguard seed live-exam --identity-check MANUAL

# 6. Start server with background scheduler
examguard serve --port 8080 --with-scheduler
```
Server starts on `http://127.0.0.1:8080/`.

---

### 2. Accessing the Web Interfaces

The Python server directly hosts the pre-built `examguard-web` assets:
* **Landing Page**: `http://127.0.0.1:8080/` (choose between Candidate Portal and Admin Web)
* **Candidate Portal**: `http://127.0.0.1:8080/portal/`
* **Admin Web**: `http://127.0.0.1:8080/admin/`

#### To Run `examguard-web` in Live Vite Development Mode:
```powershell
cd sakti-desktop/examguard-web
npm install
npm run dev
```

---

## Default Staf & Candidate Demo Accounts

| Role | Email | Password |
| :--- | :--- | :--- |
| **Org Admin** | `admin@pt-contoh-jaya.demo.example.com` | `Password123!` |
| **Exam Admin** | `exams@pt-contoh-jaya.demo.example.com` | `Password123!` |
| **Invigilator** | `pengawas@pt-contoh-jaya.demo.example.com`| `Password123!` |
| **Candidate** | Self-register at `/portal/` | *Custom* |

*Tip: Read development emails (verification tokens, password resets) via CLI:*
```powershell
examguard outbox list --to <email>
```

---

## Verification & Test Commands

```powershell
# Run backend test suite (172 tests)
pytest tests/

# Run web test suite
cd examguard-web
npm test
```

---

## Documentation & Backlog

* **[SEB Replica Architecture Blueprint](docs/specs/2026-11-18-seb-desktop-lockdown-architecture-and-redundancy-analysis.md)**
* **[00-START-HERE Developer Guide](docs/backlog/00-START-HERE.md)**
* **[Cryptographic Wire Protocol (EG-Sig)](docs/backlog/00-standards/protocol-security.md)**
* **[Desktop Kiosk Lockdown Spec (BL-DESK-01)](docs/backlog/50-upcoming-roadmap/BL-DESK-01-kiosk-lockdown-process-guardian.md)**
* **[WebView Embedding Spec (BL-DESK-02)](docs/backlog/50-upcoming-roadmap/BL-DESK-02-participant-webview-attestation.md)**

