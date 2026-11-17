# 00-standards/protocol-security: ExamGuard Cryptographic Protocol

---

## 1. Asymmetric Request Signing (`EG-Sig`)

Every request sent by the ExamGuard Desktop Client (heartbeats, events, state sync) is signed using an **Ed25519** keypair generated during device registration:

### HTTP Header Format
```http
EG-Sig: key_id="<device-session-id>", ts="<unix-timestamp>", sig="<base64-ed25519-signature>"
```
- Signed payload: `HTTP_METHOD + "\n" + REQUEST_URI + "\n" + TIMESTAMP + "\n" + SHA256(BODY)`
- The server validates timestamp drift ($\le 120$ seconds) to prevent replay attacks.

---

## 2. Server Key Sets & Trust Anchors
- The server exposes public verification keys at `/.well-known/examguard-keys.json`.
- Key format follows standard JWKS with `kty: OKP`, `crv: Ed25519`.
- Root keys (`dev-root.key`) are stored securely and rotated annually.

---

## 3. Emergency Challenge–Response Unlock Protocol (PRD §22)

When a candidate’s workstation is locked due to an unmonitored crash or network cut:
1. The client screen displays an **8-character alphanumeric challenge code** (e.g. `K9X2-M7PQ`).
2. The candidate informs the invigilator via phone/intercom.
3. The invigilator enters the challenge into Admin Web at `POST /api/v1/org/attempts/{id}/unlock-response`.
4. The server computes:
   ```python
   response_code = hmac_sha256(attempt_unlock_secret, challenge)[:8].upper()
   ```
5. The invigilator reads the 8-digit response code to the candidate.
6. The candidate types the response into the client screen; the desktop browser immediately unlocks.

