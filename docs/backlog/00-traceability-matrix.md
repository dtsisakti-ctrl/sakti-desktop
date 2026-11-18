# 00-traceability-matrix: ExamGuard & SAKTI Desktop Traceability Matrix (PRD v0.3.7)

This matrix maps every functional requirement in the ExamGuard PRD and SAKTI Desktop Specs to its implementing specification, owner, phase, and verification status.

---

| PRD Section | Requirement Description | BL Spec ID | Owner | Phase | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **§9, §10** | **REQ-EG-STATE-01**: Formal Attempt State Machine with atomic transition validation and reason categories | `BL-EG-01` | EG-BE | Phase 1b | **DONE** |
| **§11** | **REQ-EG-TIME-01**: Precision Timing Engine (Fixed-end vs Full-duration, late start, clock offset, pause modes) | `BL-EG-01` | EG-BE | Phase 1b | **DONE** |
| **§10, §17** | **REQ-EG-SCHED-01**: Background scheduler with simultaneous `INTERRUPTED` & `OFFLINE` detection ($\le 2$s) | `BL-EG-01` | EG-BE | Phase 1b | **DONE** |
| **§18, §19** | **REQ-EG-SIG-01**: Ed25519 request signing (`EG-Sig`), device session registration, and trust anchor key rotation | `BL-EG-02` | EG-BE | Phase 1c-1 | **DONE** |
| **§12, §17** | **REQ-EG-CONF-01**: Launch token exchange, Signed Exam Config envelope, and full state synchronization | `BL-EG-02` | EG-BE | Phase 1c-1 | **DONE** |
| **§16** | **REQ-EG-LMS-01**: Integration API for LMS, Attestation Token header, and signed Completion Tokens | `BL-EG-03` | EG-BE | Phase 1c-2 | **DONE** |
| **§16.6** | **REQ-EG-HOOK-01**: Ed25519-signed outgoing webhooks to subscribing organizations with retry policy | `BL-EG-03` | EG-BE | Phase 1c-2 | **DONE** |
| **§22** | **REQ-EG-UNLOCK-01**: Emergency Unlock: Online signed command, 8-character Challenge–Response, and printed backup codes | `BL-EG-03` | EG-BE | Phase 1c-2 | **DONE** |
| **§12.5** | **REQ-EG-PHOTO-01**: Encrypted identity check photos (selfie + ID card) with audit-logged staff decryption access | `BL-EG-03` | EG-BE | Phase 1c-2 | **DONE** |
| **§27** | **REQ-EG-ADMIN-01**: Admin Web dashboard, Live Monitoring Console with real-time candidate tiles and emergency actions | `BL-EG-04` | EG-FE | Phase 3a | **DONE** |
| **§15, §27.6**| **REQ-EG-INC-01**: Incident timeline with localized event names, severity, confidence scores, and review workflow | `BL-EG-04` | EG-FE | Phase 3a | **DONE** |
| **§28** | **REQ-EG-PORTAL-01**: Candidate Portal (`/portal/`) with public catalog, session transfers, and password reset | `BL-EG-05` | EG-FE | Phase 3b-1 | **DONE** |
| **§28.4** | **REQ-EG-PORTAL-02**: Time-window gated "Mulai Ujian" launcher with crash re-open and `examguard://` protocol links | `BL-EG-05` | EG-FE | Phase 3b-1 | **DONE** |
| **§27.7** | **REQ-EG-ADMIN-02**: Advanced Admin Web: Organization member delegation, LMS API key management, Hash-Chain audit inspection | `BL-EG-06` | EG-FE | Phase 3b-2 | **FULL** |
| **SPEC §3, PRD §13** | **REQ-DESK-01**: Full OS kiosk lockdown disabling Alt+Tab, Win Key, Alt+F4, and task switching | `BL-DESK-01` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §13** | **REQ-DESK-02**: Physical multi-display hard block requiring physical disconnection (`SM_CMONITORS > 1`) | `BL-DESK-01` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §13** | **REQ-DESK-03**: Process Guardian polling and terminating blacklisted apps (Discord, AnyDesk, TeamViewer, etc.) | `BL-DESK-01` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §13** | **REQ-DESK-04**: Anti-Screen Capture Shield (`WDA_EXCLUDEFROMCAPTURE`) blinding OBS, Discord, and Snipping Tool | `BL-DESK-01` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §13** | **REQ-DESK-05**: Anti-VM & Sandbox Detection (CPUID hypervisor flag, SMBIOS vendor, virtual drivers) | `BL-DESK-01` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §13** | **REQ-DESK-06**: Remote Desktop (RDP) & Session Hijacking detection (`SM_REMOTESESSION`) | `BL-DESK-01` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §16** | **REQ-DESK-07**: Secure embedded WebView loading exclusively SAKTI-Participant-App | `BL-DESK-02` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §16** | **REQ-DESK-08**: Origin whitelisting blocking all external URLs, context menus, popups, and DevTools | `BL-DESK-02` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §16** | **REQ-DESK-09**: SSL/TLS certificate pinning & VPN/TUN virtual adapter detection | `BL-DESK-02` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §16** | **REQ-DESK-10**: Attestation Header `X-Sakti-Desktop-Signature` passed to SAKTI-Backend | `BL-DESK-02` | EG-CL | Phase 4 | **FULL** |
| **SPEC §3, PRD §22** | **REQ-DESK-11**: Emergency Challenge–Response unlock protocol modal & teardown | `BL-DESK-02` | EG-CL | Phase 4 | **FULL** |
| **PRD §14** | **REQ-DESK-12**: Native Decoupled AI Engine running in low-priority background thread (Zero UI lag) | `BL-DESK-03` | EG-CL | Phase 4 | **FULL** |
| **PRD §14** | **REQ-DESK-13**: Potato-resilient cascade pipeline (YuNet + Head Pose PnP at 1-2 FPS, $\le 6\%$ CPU) | `BL-DESK-03` | EG-CL | Phase 4 | **FULL** |
| **PRD §14, §27** | **REQ-DESK-14**: Continuous adaptive WebRTC live video streaming (360p @ 10-12 FPS, 150 kbps) | `BL-DESK-03` | EG-CL | Phase 4 | **FULL** |
| **PRD §27.5** | **REQ-DESK-15**: Permanent Proctor Surveillance Wall with Dynacast/Simulcast multi-candidate gallery | `BL-DESK-03` | EG-CL | Phase 4 | **FULL** |
| **PRD §14.5** | **REQ-DESK-16**: Automated cloud archive recording (SFU Egress) for post-exam review | `BL-DESK-03` | EG-CL | Phase 4 | **FULL** |
| **§13, §14** | **REQ-EG-CLIENT-01**: Native Rust + CEF/WebView secure desktop client with local ONNX AI proctoring models | `BL-EG-07` | EG-CL | Phase 5 | **STUB** |
