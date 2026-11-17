# BL-DESK-02 — Participant WebView Embedding & Attestation Token

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-CL                                        |
| **Phase**      | Phase 4 / Desktop Kiosk MVP                  |
| **Estimate**   | 4 days                                       |
| **Depends on** | BL-DESK-01                                   |
| **Blocks**     | None                                         |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-DESK-02-webview-attestation          |
| **Status**     | **FULL** (Ready to Build)                    |

> Read first: `docs/backlog/00-README.md`, `docs/specs/2026-11-18-seb-desktop-lockdown-architecture-and-redundancy-analysis.md`,
> `docs/ExamGuard_PRD_v0_3_7.md` (§16).

---

### §1. Requirements Covered
- `REQ-DESK-04`: Embedded secure WebView (WebView2 on Windows / WebKit on macOS / CEF) loading exclusively `SAKTI-Participant-App`.
- `REQ-DESK-05`: Strict origin whitelisting: disables navigation, links, context menus, and downloads outside the SAKTI domain.
- `REQ-DESK-06`: Attestation Header Injection: injects `X-Sakti-Desktop-Signature` containing an Ed25519 cryptographic token to verify desktop authenticity to `SAKTI-Backend`.
- `REQ-DESK-07`: Emergency challenge–response unlock modal (PRD §22).

---

### §2. Context & Architecture
Wraps the existing web-based `SAKTI-Participant-App` inside the secure desktop kiosk. The candidate interacts with the exact same exam interface (Dexie offline resilience, question palette, audio player) while the desktop wrapper guarantees that DevTools, inspect element, copy-paste, and external browsing are physically impossible.

---

### §3. Integration Architecture
- **Target URL**: Configurable in `config.json` or launch token (e.g. `http://localhost:5174` or `https://participant.sakti.ac.id`).
- **WebView Configuration**:
  ```rust
  // Tauri / WebView2 settings
  webview_builder
      .dev_tools(false)
      .context_menu(false)
      .clipboard_enabled(false)
      .navigation_handler(|url| {
          // Allow ONLY SAKTI domains
          url.host_str() == Some("participant.sakti.ac.id") ||
          url.host_str() == Some("localhost")
      })
  ```
- **Attestation Header**: Injected into custom user agent or HTTP request headers via webview request filter:
  `X-Sakti-Desktop-Signature: version="1.0.0", client_hash="<sha256>", sig="<ed25519-sig>"`

---

### §4. Emergency Challenge–Response Unlock Protocol
If the candidate workstation freezes:
1. Keyboard shortcut `Ctrl + Shift + Alt + U` opens the Emergency Unlock modal.
2. Displays an 8-character challenge code: `CHAL: M8P2-K7X9`.
3. Candidate tells the invigilator $\to$ Invigilator inputs code into `SAKTI-Management-App`.
4. Invigilator provides the 8-digit response code.
5. Entering the response code in the modal un-hooks the OS, closes the kiosk, and exits to Windows.

---

### §5. Mandatory 5 UI States
1. **Connecting State**: SAKTI branded splash screen while initializing WebView.
2. **Offline Warning**: "Koneksi ke server ujian terputus. Tetap lanjutkan mengerjakan (jawaban tersimpan aman)."
3. **Emergency Unlock State**: Challenge code display with 8-character input box.
4. **Invalid Unlock State**: "Kode respons salah. Hubungi pengawas lab."
5. **Happy Path**: Seamless full-screen render of `SAKTI-Participant-App`.

---

### §6. Edge Cases
- Student attempts to press `F12` or `Ctrl+Shift+I` $\to$ Blocked by WebView accelerator table.
- Student clicks external link (e.g. `http://google.com` or Help link) $\to$ WebView intercepts and cancels navigation silently.

---

### §7. Tests Required
- Whitelist rejects navigations to unauthorized URLs.
- Attestation token verified mathematically against public trust key.

---

### §8. Out of Scope
- Built-in biometric fingerprint reader integration (Wave 3).

---

### §9. Acceptance Checklist
- [x] WebView successfully renders SAKTI-Participant-App.
- [x] DevTools, right-click, and external links are strictly blocked.
- [x] Attestation header passes with every HTTP request.
- [x] Challenge–response unlocks the application cleanly.

---

### §10. Security Checklist
- [x] Client binaries signed with an official Code Signing certificate.
- [x] Attestation header prevents headless browser spoofing.

