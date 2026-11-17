# SPEC-DESK-01: Safe Exam Browser (SEB) Replica Architecture & Redundancy Resolution

* **Status**: `APPROVED / ARCHITECTURAL BLUEPRINT`
* **Target Repository**: `sakti-desktop`
* **Inspired by**: Safe Exam Browser (SEB), Respondus Lockdown Browser, ExamGuard PRD v0.3.7

---

## 1. Executive Summary & Strategic Rationale

The objective for `sakti-desktop` is to build a **Safe Exam Browser (SEB) replica** for the SAKTI ecosystem: a native desktop application that turns a student's computer into a temporary high-security examination kiosk.

### The Problem: Legacy Redundancy in `sakti-desktop`
The initial code imported into `sakti-desktop` contained `examguard-server` (FastAPI / PostgreSQL) and `examguard-web` (React / Vite).
This created **90% architectural redundancy**:
- `examguard-server` duplicates `SAKTI-Backend` (attempts, users, scheduling, state machines).
- `examguard-web` duplicates `SAKTI-Management-App` (live monitoring) and `SAKTI-Participant-App` (candidate portal).
- **Crucially: Neither `examguard-server` nor `examguard-web` is the actual desktop executable (`.exe`).**

### The Resolution: Unified Single-Stack Architecture
1. **Consolidate Backend & Web**: `SAKTI-Backend`, `SAKTI-Management-App`, and `SAKTI-Participant-App` remain the **single source of truth** for all APIs, websockets, databases, and web interfaces.
2. **Transform `sakti-desktop` into the Native Desktop Kiosk**: `sakti-desktop` focuses exclusively on being the **Safe Exam Browser native desktop wrapper** (`sakti-browser.exe`).
3. **Embed SAKTI-Participant-App**: The native app locks down the operating system and loads `https://participant.sakti.ac.id` (or local dev port) inside an isolated, tamper-proof WebView, whitelisting only SAKTI URLs.
4. **Cryptographic Attestation**: The desktop client passes a hardware attestation token (`X-Sakti-Desktop-Signature`) to `SAKTI-Backend` on every request to prove that the exam is running inside the official locked-down client and not in standard Chrome with DevTools enabled.

---

## 2. Target Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      sakti-desktop (Native Kiosk App)                   │
│                                                                         │
│  ┌───────────────────────────────┐     ┌─────────────────────────────┐  │
│  │ OS Kiosk Lockdown Engine      │     │ Process Guardian Service    │  │
│  │ (Rust / Win32 API / Cocoa)    │     │ (Background process polling)│  │
│  │ - LowLevelKeyboardProc hook   │     │ - Detect & kill blacklisted │  │
│  │ - Block Alt+Tab, Win Key      │     │   apps (Discord, AnyDesk,   │  │
│  │ - Multi-monitor blanking      │     │   TeamViewer, Chrome)       │  │
│  └──────────────┬────────────────┘     └──────────────┬──────────────┘  │
│                 │                                     │                 │
│                 └──────────────────┬──────────────────┘                 │
│                                    ▼                                    │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │ Secure Embedded WebView (Tauri / Rust + WebView2 / CEF)           │  │
│  │ - Whitelist ONLY: SAKTI-Participant-App URL                       │  │
│  │ - Disables DevTools, Right-Click Context Menu, Address Bar        │  │
│  │ - Disables File Downloads & Printing                              │  │
│  │ - Injects `X-Sakti-Desktop-Signature` Attestation Header          │  │
│  └─────────────────────────────────┬─────────────────────────────────┘  │
└────────────────────────────────────┼────────────────────────────────────┘
                                     │ HTTPS & WSS
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              SAKTI-Backend                              │
│ - Verifies Desktop Attestation Signature                                │
│ - Manages Attempts, Dexie Outbox Ingestion, and WebSocket Telemetry     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         SAKTI-Management-App                            │
│ - Live Surveillance Grid & Proctor Remote Workstation Recovery          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 3. Core Feature Specifications

### 3.1 Operating System Lockdown (The SEB Replica)
1. **System Hotkey Hooks**:
   - Windows: Implements `SetWindowsHookEx` with `WH_KEYBOARD_LL` intercepting and swallowing `VK_TAB + VK_MENU` (Alt+Tab), `VK_LWIN`, `VK_RWIN`, `Ctrl+Alt+Del` mitigation, and `Alt+F4`.
   - macOS: Kiosk mode disabling `Cmd+Tab`, Mission Control, and Dock visibility.
2. **Multi-Monitor Enforcement**:
   - Enumerates connected displays via OS display APIs.
   - If secondary monitors are detected, either:
     - Blanks/blacks out secondary displays with an un-clickable black window.
     - Mandates disconnection of secondary displays before allowing exam entrance.
3. **Process Guardian (Anti-Cheat Blacklist)**:
   - Polls running OS process tree every 1,500ms.
   - Blacklist includes: Discord, Slack, TeamViewer, AnyDesk, Telegram, OBS Studio, Bandicam, Snipping Tool, ChatGPT Desktop.
   - Action: Displays warning overlay and terminates unauthorized processes.

### 3.2 Secure Embedded WebView
- Loads exclusively `SAKTI-Participant-App`. Navigation to any unauthorized external origin is blocked at the webview level.
- Clipboard: External copy-paste into the exam webview is disabled.
- Context menu: Right-click is completely suppressed.
- DevTools & Shortcuts: `F12`, `Ctrl+Shift+I`, and `Ctrl+U` are disabled.

### 3.3 Hardware Attestation Header
On every HTTP request and WebSocket handshake to `SAKTI-Backend`:
```http
X-Sakti-Desktop-Signature: version="1.0.0", machine_id="<uuid>", sig="<ed25519-signature>"
```
`SAKTI-Backend` validates this header. If a student attempts to load the exam URL directly in regular Google Chrome, `SAKTI-Backend` rejects the session with:
`403 Forbidden: Ujian hanya dapat diakses melalui SAKTI Exam Browser.`

### 3.4 Emergency Challenge–Response Unlock (PRD §22)
If a student's desktop client crashes or freezes in full kiosk lockdown:
- The screen renders an 8-character challenge code: `CHAL: K9X2-M7PQ`.
- The student calls the proctor. The proctor inputs this challenge into `SAKTI-Management-App` to generate an 8-digit unlock response code.
- Typing the response into the client immediately exits the kiosk lockdown safely.

---

## 4. Execution & Migration Roadmap

| Phase | Deliverable | Status |
| :--- | :--- | :--- |
| **Phase 0** | Blueprint & Redundancy Resolution (this document) | **APPROVED** |
| **Phase 1** | Project scaffolding for `sakti-desktop` using **Tauri 2.0 (Rust + WebView2)** | Next Sprint (`BL-DESK-01`) |
| **Phase 2** | OS Kiosk Lockdown Engine & Process Guardian (`WH_KEYBOARD_LL`) | Next Sprint (`BL-DESK-01`) |
| **Phase 3** | SAKTI Participant WebView embedding & Attestation Signature | Next Sprint (`BL-DESK-02`) |
| **Phase 4** | Emergency Challenge–Response Unlock & Windows Installer (`.msi` / `.exe`) | Upcoming (`BL-DESK-03`) |

