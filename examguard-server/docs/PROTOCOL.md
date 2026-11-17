# ExamGuard Client Protocol — wire format (server Phase 1c)

Pelengkap PRD v0.3.1 §12, §16.2, §17, §18, §19. Dokumen ini menetapkan detail yang dibutuhkan
implementasi client (Rust, Phase 2 dan 5). Implementasi referensi yang dapat dieksekusi ada di
`tests/refclient.py`; semua contoh di bawah diuji oleh `tests/test_protocol.py`.

## 1. Kunci dan key set (§19)

- `GET /.well-known/examguard-keys.json` → envelope `{"kid", "body", "sig"}` yang ditandatangani
  **root trust key**. `kid` root = `root-` + 16 hex pertama SHA-256 dari public key root (32 byte).
- `body` (JSON string): `{"v":1, "issuer", "issued_at", "keys":[...]}`. Setiap entri:
  `{"kid", "use", "alg":"EdDSA", "crv":"Ed25519", "x", "not_before", "not_after", "status"}`,
  dengan `x` = base64url tanpa padding dari 32 byte public key dan `status` ∈ `active | retired | revoked`.
- `kid` server berbentuk `<base>.<use>`, `use` ∈ `command | state | config | token`. Pada MVP satu
  pasangan kunci dipakai untuk keempat `use`, tetapi client **wajib** mencocokkan `use` per kid.
- Client menerima envelope hanya jika: kid ada di key set yang lolos verifikasi root, status bukan
  `revoked`, `use` sesuai konteks, dan signature valid atas byte persis `body`.

## 2. Envelope bertanda tangan (§17.2)

`sig = base64url(Ed25519(UTF-8 bytes dari string body))`. Server menulis `body` sebagai JSON
kompak dengan key terurut, tetapi client **tidak boleh** menyusun ulang: verifikasi selalu atas
string `body` apa adanya, lalu baru di-parse. Waktu memakai ISO 8601 UTC dengan akhiran `Z`.

## 3. Launch (§12.1–12.3)

1. `POST /client/v1/launch {"launch_token"}` → `{"config": envelope(use=config)}`. **Tidak**
   menghabiskan token, sehingga aman diulang bila koneksi putus.
2. `POST /client/v1/device-sessions`
   `{"launch_token", "public_key", "client_version", "os_info", "preflight"}` → `201`
   `{"device_session_id", "device_status", "state": envelope(use=state)}`. Menghabiskan token.
   `device_status` = `ACTIVE`, atau `PENDING_APPROVAL` bila ini pindah perangkat (§18).

Error: `401 INVALID_LAUNCH_TOKEN`, `401 LAUNCH_TOKEN_EXPIRED` (15 menit), `409 LAUNCH_TOKEN_USED`,
`426 CLIENT_TOO_OLD`, `422 INVALID_PUBLIC_KEY`, serta error alur dari server (mis. `CHECKIN_NOT_OPEN`).

Respons registrasi juga berisi `attempt_unlock_secret` (32 byte base64url, sama untuk semua device
session satu attempt). Client menyimpannya di recovery state terenkripsi untuk emergency unlock (§8).

Isi Signed Exam Config: `exam_id, exam_code, exam_name, attempt_id, candidate_id, exam_url,
allowed_origins, policy, integration_level, identity_check, checkin_open, window_start, latest_start,
window_end, min_client_version, server_endpoints{api, ws, key_set}, issued_at, expires_at (30 menit),
config_hash, emergency_code_hashes`.

## 4. Autentikasi request: EG-Sig (§18)

```text
Authorization: EG-Sig sid=<device_session_id>, ts=<unix_ms>, sig=<base64url>
sig = Ed25519( METHOD "\n" PATH "\n" ts "\n" sha256_hex(body) )
```

- `METHOD` huruf besar; `PATH` = path URL, ditambah `?query` bila ada; `sha256_hex` huruf kecil
  (body kosong → hash string kosong).
- `ts` di luar ±60 detik → `401 CLOCK_SKEW`; signature salah → `401 INVALID_SIGNATURE`; sesi
  dicabut → `401 DEVICE_SESSION_REVOKED`; attempt lain → `403`.

| Endpoint (prefix `/client/v1/attempts/{attempt_id}`) | Fungsi |
|---|---|
| `GET /state` | Full state sync → envelope(use=state) |
| `POST /start` | NOT_STARTED/REOPENED/REINSTATED → ACTIVE → state envelope |
| `POST /identity` | `{"content_type": "image/jpeg"\|"image/png"\|"image/webp", "selfie": base64, "id_card": base64}`, masing-masing ≤ 3 MB |
| `POST /finish` | Level 0 "Selesai Ujian" → state envelope |
| `POST /heartbeat` | Fallback HTTPS untuk heartbeat WSS |
| `POST /events` | Batch ≤ 500 event, idempoten per `(device_session_id, seq)`; sesi yang sudah dicabut tetap boleh mengunggah |
| `GET /commands` | Fallback HTTPS: command yang belum di-ACK (envelope identik byte-per-byte saat dikirim ulang) |
| `POST /commands/{id}/ack` | `{"result": "APPLIED"\|"STALE"\|"REJECTED", "reason"}` |
| `POST /attestation` | Attestation JWT (EdDSA, kid `…token`), berlaku 5 menit |

Isi state: `v, attempt_id, exam_id, candidate_id, device_session_id, device_status, status,
state_version, deadline, server_time, resume_allowed, pause_timer_mode, identity_status,
window_start, pending_warning`.

## 5. WebSocket (§17.1, §17.5, §17.6)

`GET /client/v1/ws?sid=<id>&ts=<unix_ms>&sig=<b64u>` dengan
`sig = Ed25519("GET\n/client/v1/ws\n" + ts + "\n" + sha256_hex(""))`. Gagal → close code `4401`.

Server → client:

| Pesan | Kapan |
|---|---|
| `{"type":"STATE","envelope"}` | Saat terhubung, dan setiap kali `state_version` berubah |
| `{"type":"COMMAND","envelope"}` | Command baru (envelope use=command) |
| `{"type":"HEARTBEAT_ACK", "server_time", "status", "state_version", "sync_required", …}` | Balasan heartbeat |
| `{"type":"ACK_OK","command_id","delivery_status"}` | Balasan ACK |
| `{"type":"REVOKED","reason"}` lalu close `4403` | Device session dicabut (mis. pindah perangkat disetujui) |
| `{"type":"ERROR","code"}` | Pesan tidak valid |

Client → server:

- Heartbeat tiap 10 detik, ditandatangani device key atas string `body`:
  `{"type":"HEARTBEAT","body":"{\"device_session_id\":…,\"seq\":…,\"ts\":…,\"last_state_version\":…,\"health\":{…}}","sig":"…"}`.
  `recovery_cause` opsional di body saat tersambung kembali.
- `{"type":"ACK","command_id","result","reason"}` dan `{"type":"SYNC"}` (minta state).

### Deteksi terputus (PRD v0.3.5 §17.6)

- **Koneksi WebSocket tertutup** tanpa server yang menutupnya (client crash, aplikasi ditutup, Ctrl+C,
  laptop mati): attempt `ACTIVE` langsung menjadi `INTERRUPTED` dan koneksi `OFFLINE` pada saat yang
  sama (data transisi `detected: "connection_closed"`). Attempt `PAUSED` tetap `PAUSED`, hanya `OFFLINE`.
  Socket lama yang tertutup setelah client sudah mengirim heartbeat lewat socket yang lebih baru diabaikan.
- **Hilang diam-diam** (kabel dicabut, tanpa TCP close): `OFFLINE` dan `INTERRUPTED` muncul bersamaan
  setelah `interruption_threshold_seconds` ujian tanpa heartbeat (default **30 detik**).
- **Setiap request bertanda tangan** dari device session aktif (heartbeat, `GET /state`, `/finish`,
  `/events`, `/commands`, ack, attestation) adalah bukti hidup: memperbarui waktu terakhir terlihat dan
  melanjutkan attempt `INTERRUPTED` (auto-resume / menunggu persetujuan seperti heartbeat).
- Karena itu **request pertama setelah tersambung kembali sebaiknya heartbeat dengan `recovery_cause`**
  (`CLIENT_CRASH`, `NETWORK_FAILURE`, …); bila yang pertama adalah sync, penyebab tercatat `UNKNOWN`.
- Jeda < 10 detik tidak membuat incident `UNMONITORED_INTERRUPTION` (tetap tercatat di riwayat transisi).

## 6. Command (§17.3–17.4)

Body: `v, command_id, type, exam_id, attempt_id, candidate_id, device_session_id, state_version,
issued_at, expires_at (5 menit), nonce (16 byte base64url), payload`. Aturan client: tolak jika
kid/use/signature/ID tidak cocok atau kedaluwarsa; `state_version` ≤ versi terakhir → STALE (tetap di-ACK).

Klarifikasi (ditemukan saat implementasi client Phase 2): aturan STALE hanya berlaku untuk command
yang mengubah status (`PAUSE_EXAM`, `RESUME_EXAM`, `UPDATE_DEADLINE`, `ALLOW_REENTRY`,
`REJECT_REENTRY`, `FORCE_SUBMIT`, `FORCE_TERMINATE`). `WARNING` dan `EMERGENCY_UNLOCK` diterbitkan
dengan `state_version` saat ini tanpa kenaikan, sehingga tidak pernah dianggap STALE. Command yang
sudah pernah diterapkan tidak diterapkan ulang dan di-ACK `APPLIED` lagi.

Urutan pemeriksaan di client (PRD v0.3.3 §17.3, Q20): kid/use/signature → kecocokan ID sesi →
duplikat → kedaluwarsa → STALE. Duplikat diperiksa sebelum kedaluwarsa agar pengiriman ulang yang
terlambat tetap mendapat ACK `APPLIED`, bukan `REJECTED`.

## 7. Attestation JWT (§16.2)

Header `{"alg":"EdDSA","typ":"JWT","kid":"<base>.token"}`. Claims: `iss, aud (origin exam_url),
exam_id, attempt_id, candidate_ref, device_session_id, attempt_status, state_version, config_hash,
iat, exp`. LMS memverifikasi dengan key set yang sama.

## 8. Emergency unlock (§22)

- **Online:** command `EMERGENCY_UNLOCK` `{reason}`.
- **Challenge–response:** client menampilkan challenge 8 karakter base32 (`A–Z`, `2–7`). Respons =
  `f"{int.from_bytes(HMAC_SHA256(key=attempt_unlock_secret (string ASCII apa adanya), msg=CHALLENGE huruf besar)[:4], 'big') % 10^8:08d}"`.
- **Kode cadangan:** format `XXXXX-XXXXX` (base32). Client menormalisasi input (huruf besar, tanpa `-`)
  lalu membandingkan `sha256_hex(exam_id + ":" + kode)` dengan `emergency_code_hashes` di config.
- Setelah unlock, client mengirim event `EMERGENCY_UNLOCK_USED` dengan
  `metadata {"method": "ONLINE"|"CHALLENGE"|"BACKUP_CODE", "code_hash"?}`. Server menandai kode
  terpakai, membuat incident HIGH, dan memindahkan attempt `ACTIVE` ke `INTERRUPTED`.

## 9. Completion token (§16.5)

JWT EdDSA dari `kid …token`, diterbitkan server saat LMS memanggil `/integration/v1/attempts/{id}/completion`.
Claims: `typ = "completion"`, `iss`, `aud = "examguard-client"`, `exam_id`, `attempt_id`,
`device_session_id`, `state_version`, `nonce`, `iat`, `exp` (10 menit). Client memverifikasi kid/use,
signature, `typ`, ID sesi, `exp`, dan bahwa `nonce` belum pernah dipakai, sebelum `EXIT_AUTHORIZED`.
Jalur cadangan: state `SUBMITTED` yang di-push lewat WSS.

## 10. Webhook (§16.6)

```text
X-ExamGuard-Event-Id: <uuid>
X-ExamGuard-Event: attempt.submitted
X-ExamGuard-Signature: kid=<…token>, ts=<unix_ms>, sig=<base64url Ed25519(ts + "." + body)>
```

Body: `event_id, type, occurred_at, exam_id, attempt_id, candidate_ref, status, state_version,
deadline, reason_category`. Penerima harus idempoten terhadap `event_id` dan membalas 2xx.
