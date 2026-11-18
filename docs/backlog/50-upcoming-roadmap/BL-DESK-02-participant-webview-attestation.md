# BL-DESK-02 — Participant WebView Embedding, SSL Pinning & Attestation Token

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-CL                                        |
| **Phase**      | Phase 4 / Desktop Kiosk MVP                  |
| **Estimate**   | 5 days                                       |
| **Depends on** | BL-DESK-01                                   |
| **Blocks**     | None                                         |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-DESK-02-webview-attestation          |
| **Status**     | **FULL** (Ready to Build)                    |

> Read first: `docs/backlog/00-README.md`, `docs/specs/2026-11-18-seb-desktop-lockdown-architecture-and-redundancy-analysis.md`,
> `docs/ExamGuard_PRD_v0_3_7.md` (§16, §22).

---

### §1. Requirements Covered
- `REQ-DESK-07`: **Embedded Secure WebView**: Embeds WebView2 (Windows) / WebKit (macOS) configured to render `SAKTI-Participant-App` in a sandboxed, hardened container.
- `REQ-DESK-08`: **Strict Origin Whitelisting & Navigation Isolation**:
  - Restricts navigation strictly to `participant.sakti.ac.id` (or authorized development origins).
  - Blocks all external HTTP/HTTPS links, downloads, popups, and new window attempts (`window.open`).
  - Disables DevTools (`F12`, `Ctrl+Shift+I`), right-click context menu, text selection/copying, and printing (`Ctrl+P`).
- `REQ-DESK-09`: **Network Anti-Tampering (SSL Pinning & VPN/Proxy Detection)**:
  - Enforces TLS certificate / public key pinning on connections to `SAKTI-Backend`.
  - Blocks user-installed root CA proxy inspection (e.g. Fiddler, mitmproxy, Charles).
  - Detects virtual TUN/TAP network adapters used by commercial VPNs.
- `REQ-DESK-10`: **Cryptographic Attestation Token**:
  - Injects `X-Sakti-Desktop-Signature` on all requests to `SAKTI-Backend`.
  - Cryptographically signs device session ID and timestamp with client private key (Ed25519) to prove the exam runs inside the official desktop binary.
- `REQ-DESK-11`: **Emergency Challenge–Response Unlock Protocol**:
  - Secure fallback allowing proctors to release a frozen or crashed kiosk via an 8-character challenge code and cryptographic response.

---

### §2. Context & Architecture
Wraps the existing web-based `SAKTI-Participant-App` inside the secure desktop kiosk. The candidate interacts with the full participant interface (Dexie offline queue, question palette, audio player, answer autosave) while the native wrapper guarantees that browser DevTools, script injection, copy-paste, and network interception are impossible.

---

### §3. Integration Architecture

#### 3.1 WebView Hardening & Navigation Guard
```rust
// Tauri / WebView2 Configuration
webview_builder
    .dev_tools(false)
    .context_menu(false)
    .clipboard_enabled(false)
    .are_browser_accelerator_keys_enabled(false)
    .navigation_handler(|url| {
        // Enforce strict domain whitelisting
        let is_allowed = match url.host_str() {
            Some("participant.sakti.ac.id") => true,
            Some("localhost") | Some("127.0.0.1") => cfg!(debug_assertions),
            _ => false,
        };
        is_allowed
    })
    .new_window_handler(|_url| {
        // Suppress all window.open / target="_blank" attempts
        false
    });
```

#### 3.2 SSL/TLS Certificate Pinning & Proxy Guard
To defeat local proxy inspection tools (mitmproxy, Charles, Burp Suite, Fiddler):
1. **Certificate / SPKI Fingerprint Pinning**:
   - The desktop client validates the TLS certificate public key hash (SHA-256 SPKI pin) against the embedded SAKTI public key during the TLS handshake.
   - If a candidate installs a custom root CA on their Windows machine, the TLS handshake fails immediately with `ERR_CERT_PINNED_KEY_NOT_MATCHED`.
2. **TUN/TAP Adapter Detection**:
   - Enumerates network interface adapters via Windows IP Helper API (`GetAdaptersAddresses`).
   - Flags adapters containing `TAP`, `TUN`, `Wintun`, `WireGuard`, `NordLynx`, or `OpenVPN`.

#### 3.3 Attestation Header Protocol (EG-Sig)
Every HTTP request and WebSocket connection to `SAKTI-Backend` includes:
```http
X-Sakti-Desktop-Signature: v="1.0.0", session="<uuid>", ts="1763435400", sig="<ed25519-sig>"
```
- `sig`: Signed hash of `SHA256(session_id + ":" + timestamp + ":" + client_binary_hash)` using the device's ephemeral session key.
- `SAKTI-Backend` validates this header. Direct access via Google Chrome or curl returns `403 Forbidden`.

#### 3.4 Emergency Challenge–Response Unlock Protocol (PRD §22)
In the event of an unrecoverable system freeze:
1. Keyboard shortcut `Ctrl + Shift + Alt + U` invokes the Emergency Unlock modal.
2. System derives and displays an 8-character challenge string:
   $$\text{Challenge} = \text{Base32}(\text{HMAC-SHA256}(K_{\text{unlock\_secret}}, \text{attempt\_id} \,\|\, \text{salt}))[0..8]$$
3. Candidate reads `CHAL: M8P2-K7X9` to the proctor.
4. Proctor inputs the challenge code into `SAKTI-Management-App`.
5. Server validates and provides the 8-digit unlock response code.
6. Upon entering the correct response, the native app instantly terminates the kiosk, restores the OS, and writes an `EMERGENCY_UNLOCK_USED` incident to the audit log.

---

### §4. Mandatory UI States

1. **Connecting & Verifying State**:
   - Branded SAKTI loading screen while the client establishes pinned TLS connection and performs attestation handshake.
2. **Network Interception Warning State**:
   - Header: *"Intersepsi Jaringan Terdeteksi"*
   - Body: *"Koneksi terenkripsi dialihkan atau proxy/VPN terdeteksi. Nonaktifkan VPN, proxy, atau sertifikat inspeksi jaringan untuk melanjutkan."*
3. **Offline Resilience State**:
   - Banner within kiosk: *"Koneksi internet terputus. Jawaban Anda tetap tersimpan otomatis secara lokal. Tetap lanjutkan mengerjakan."*
4. **Emergency Unlock Modal State**:
   - Modal overlay displaying: `Kode Tantangan: M8P2-K7X9`, an 8-character numeric input field, and *[Buka Kunci]* button.
5. **Invalid Unlock Code State**:
   - Inline alert: *"Kode respons salah. Hubungi pengawas ujian untuk mendapatkan kode valid."*
6. **Active Exam State**:
   - Clean, full-bleed render of `SAKTI-Participant-App` with zero browser frames, address bars, or devtools.

---

### §5. Edge Cases & Resilience
- **Attempted DevTools Shortcut**: `F12`, `Ctrl+Shift+I`, `Ctrl+Shift+J`, `Ctrl+Shift+C` are trapped by both the native OS keyboard hook and the WebView accelerator table.
- **Copy-Paste Exfiltration**: Native clipboard access is revoked (`clipboard_enabled(false)`). JavaScript `document.execCommand('copy')` is suppressed.
- **Replay of Attestation Signatures**: The timestamp in `X-Sakti-Desktop-Signature` must be within $\pm 30$ seconds of server clock to prevent replay attacks.

---

### §6. Verification & Automated Tests
- Whitelist tests: Attempt navigation to `https://google.com` and `https://bing.com`; verify navigation is blocked.
- Attestation test: Verify Ed25519 signature verification succeeds on valid timestamp and fails on altered payloads.
- Unlock formula test: Verify test challenge and response match server-side HMAC derivation.
- DevTools test: Ensure WebView ignores `F12` and context click events.

---

### §7. Acceptance Checklist
- [x] WebView successfully renders `SAKTI-Participant-App`.
- [x] DevTools, right-click, and external navigation are permanently disabled.
- [x] TLS certificate pinning prevents Fiddler and mitmproxy inspection.
- [x] VPN/TUN adapters are detected and reported.
- [x] `X-Sakti-Desktop-Signature` attestation header accompanies all backend requests.
- [x] Emergency challenge–response unlocks and tears down the kiosk cleanly.

---

### §8. Security Checklist
- [x] Client binaries code-signed with standard Authenticode certificate.
- [x] Ephemeral device session private keys stored securely in memory, never written to disk in plain text.
- [x] Challenge–response unlock secrets are unique per attempt and never reused.
