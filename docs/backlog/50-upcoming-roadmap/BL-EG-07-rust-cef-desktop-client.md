# BL-EG-07 — Cross-Platform Desktop Client (Rust + CEF + ONNX Runtime)

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-CL                                        |
| **Phase**      | Phase 5                                      |
| **Estimate**   | 15 days                                      |
| **Depends on** | BL-EG-02, BL-EG-06                           |
| **Blocks**     | None                                         |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-EG-07-rust-cef-desktop-client        |
| **Status**     | **STUB** (Roadmap Phase 5)                   |

> Read first: `docs/ExamGuard_PRD_v0_3_7.md` (§13, §14, §15, §30.2).

---

### §1. Scope & Requirements
- **Native Browser Shell**: Rust application embedding Chromium Embedded Framework (CEF) with full OS kiosk lockdown on Windows, macOS, and Linux (X11).
- **Security Lockdown Matrix (PRD §13)**:
  - System hotkeys blocked (Alt+Tab, Win key, Ctrl+Alt+Del, Cmd+Tab, Mission Control).
  - Multi-monitor detection: secondary displays blanked or disabled.
  - Virtual machine & remote access software detection (TeamViewer, AnyDesk, RDP, VNC).
- **Client-Side AI Proctoring (PRD §14)**:
  - Local inference via ONNX Runtime (direct C FFI from Rust).
  - Head pose estimation and eye gaze direction vector tracking.
  - Multi-person detection and candidate absence detection.
- **Offline Incident Queue & Crash Recovery**:
  - Encrypted local cache surviving operating system restart.
  - Single-use challenge–response emergency unlock interface.

