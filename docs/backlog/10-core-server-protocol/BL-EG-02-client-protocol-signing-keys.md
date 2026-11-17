# BL-EG-02 — Client Wire Protocol, Ed25519 Signing (EG-Sig) & Key Sets

|                |                                              |
| -------------- | -------------------------------------------- |
| **Owner**      | EG-BE                                        |
| **Phase**      | Phase 1c-1                                   |
| **Estimate**   | 5 days                                       |
| **Depends on** | BL-EG-01                                     |
| **Blocks**     | BL-EG-03                                     |
| **Repo**       | sakti-desktop                                |
| **Branch**     | feat/BL-EG-02-client-protocol-signing-keys   |
| **Status**     | **DONE**                                     |

---

### §1. Requirements Covered
- `REQ-EG-SIG-01`: Ed25519 request signing protocol (`EG-Sig`), device session registration, and trust anchor key management with rotation commands.
- `REQ-EG-CONF-01`: Single-use launch token exchange, Signed Exam Config envelope, and full state synchronization over HTTPS and WebSocket.

---

### §2. Context & Architecture
Establishes the cryptographic wire protocol between the desktop client and server. Before entering an exam, the client exchanges a launch token for a signed configuration envelope containing server public keys, security policies, and attempt parameters.

---

### §3. Data Model (Database Layer)
- Alembic Migration: `0003_keys_and_signing.py`
- Models: `DeviceSession`, `SigningKey`, `TrustAnchor`, `LaunchToken`
- Public endpoint: `/.well-known/examguard-keys.json`

---

### §4. Client Wire Protocol & Endpoints
- `POST /api/v1/client/launch` (Exchanges single-use launch token for Signed Exam Config)
- `POST /api/v1/client/register-device` (Exchanges client public key for `device_session_id`)
- `POST /api/v1/client/heartbeat` (Signed heartbeat ping with workstation telemetry)
- `POST /api/v1/client/events` (Batch upload of security events with Ed25519 signatures)
- `POST /api/v1/client/sync` (Full state sync retrieving pending commands)

---

### §5. Service & Implementation Logic
- Validates `EG-Sig` HTTP headers: verifies timestamp drift ($\le 120$s) and Ed25519 signature over request method, URI, timestamp, and body SHA-256 digest.
- Mints Signed Exam Config containing cryptographic signature verifying server provenance.

---

### §6. Edge Cases
- Replay attacks: identical timestamp and signature within window rejected.
- Client restart after crash: resumes existing `DeviceSession` without re-minting new identity.

---

### §7. Tests Required
- Byte-for-byte signature verification against Rust client simulator (`eg-sim`).
- Full state sync recovery after crash and restart.

---

### §8. Out of Scope
- TPM / Hardware Secure Enclave chip verification (Wave 3).

---

### §9. Acceptance Checklist
- [x] Launch token successfully exchanges for Signed Exam Config.
- [x] EG-Sig signature header validated on all client endpoints.
- [x] Server exposes valid JWKS key set at `/.well-known/examguard-keys.json`.

---

### §10. Security Checklist
- [x] Private signing keys stored encrypted at rest.
- [x] Single-use launch tokens consumed upon initial device registration.

