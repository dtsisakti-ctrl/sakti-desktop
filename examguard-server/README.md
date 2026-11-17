# ExamGuard Server — Phase 3b-1

Backend ExamGuard (PRD v0.3.1). Phase 1a: tenancy, akun, ujian, registrasi, audit log.
Phase 1b: attempt state machine, timing, scheduler, invigilator, aksi staf.
Phase 1c-1: **protokol client** — kunci Ed25519 & key set, launch token, Signed Exam Config,
autentikasi EG-Sig, full state sync, command bertanda tangan (HTTPS & WebSocket), event & incident,
attestation token. Spesifikasi wire format untuk client: [`docs/PROTOCOL.md`](docs/PROTOCOL.md).
Phase 1c-2: **Integration API untuk LMS**, completion token, webhook bertanda tangan, foto identity check
terenkripsi, emergency unlock, API incident, `seed live-exam`. Dengan ini **Phase 1 (server) selesai**.
Phase 3a: **Admin Web** (React, folder `examguard-web`) disajikan oleh server di `/admin/`.
Phase 3b-1: **Candidate Portal** di `/portal/` dan halaman masuk di `/`.

## Candidate Portal (Phase 3b-1, PRD §28)

Buka **http://127.0.0.1:8080/** lalu pilih *Masuk sebagai peserta* (portal, `/portal/`) atau
*Masuk sebagai staf* (Admin Web, `/admin/`). Akun peserta dan staf terpisah; sesi keduanya juga
terpisah di browser yang sama.

Endpoint baru:

| Endpoint | Fungsi |
|---|---|
| `POST /api/v1/candidate/auth/password-reset/request` | Kirim tautan atur ulang kata sandi (berlaku 60 menit); jawaban sama walau email tidak terdaftar |
| `POST /api/v1/candidate/auth/password-reset/confirm` | Simpan kata sandi baru; semua sesi akun dikeluarkan; email ikut terverifikasi |
| `PATCH /api/v1/candidate/me` | Ubah nama (sesuai kartu identitas) |
| `POST /api/v1/candidate/me/password` | Ganti kata sandi; sesi lain dikeluarkan, sesi ini tetap |
| `POST /api/v1/public/invitations/preview` | Isi undangan (ujian, penyelenggara, email tujuan) sebelum masuk |

`GET /api/v1/candidate/enrollments` kini juga memuat jadwal lengkap, nama penyelenggara, status
attempt, `can_launch` + `launch_reason`, `can_change`, dan `cancel_reason`. Tombol **Mulai ujian**
(`POST /enrollments/{id}/launch`) hanya berlaku dari check-in dibuka sampai batas mulai, atau selama
attempt berjalan (buka ulang setelah crash). Integration API dan `examguard sim link` tidak dibatasi
jendela ini.

**Tautan di email** (verifikasi, atur ulang kata sandi, undangan) kini mengarah ke
`<EXAMGUARD_PUBLIC_BASE_URL>/portal`. Jika `.env` Anda masih berisi
`EXAMGUARD_PORTAL_BASE_URL=http://localhost:5173` (dari `.env.example` lama), **hapus baris itu**.
Email development dibaca dengan `examguard outbox list --to <email>`.

```bash
pip install -e ".[dev]"     # tidak ada migrasi baru
```

## Perbaikan Phase 3a: deteksi terputus (PRD v0.3.5)

Status **Terputus** dan **Offline** kini selalu muncul bersamaan:

- Client tertutup (crash, Ctrl+C, aplikasi ditutup): koneksi WebSocket tertutup → attempt langsung
  `INTERRUPTED` dan `OFFLINE` (terukur ±0,05 detik di server; tampil di Admin Web ≤ 2 detik).
- Jaringan hilang diam-diam: keduanya muncul setelah ambang ujian, default **30 detik** (sebelumnya
  Offline 30 detik, Terputus 60 detik). Ambang tetap bisa diubah per ujian (15–600 detik).
- Request bertanda tangan apa pun dari client melanjutkan attempt; jeda < 10 detik tidak membuat incident.
- Scheduler default tiap 2 detik (sebelumnya 5). `seed live-exam` menambah akhiran (`LIVE-1024-1507-2`)
  bila kode ujian sudah dipakai.

```bash
pip install -e ".[dev]"
examguard db upgrade        # migrasi 0006 (default ambang 60 → 30 detik bila belum diubah)
```

## Admin Web (Phase 3a)

```bash
examguard serve --port 8080 --with-scheduler
```

Buka **http://127.0.0.1:8080/admin/** dan masuk dengan akun staf demo, misalnya
`exams@pt-contoh-jaya.demo.example.com` (Exam Admin) atau `pengawas@pt-contoh-jaya.demo.example.com`
(pengawas). Hasil build UI sudah ada di `src/examguard/webui/admin`, jadi tidak perlu Node.js.
Untuk mengubah UI, lihat README di `examguard-web`.

Endpoint baru untuk Admin Web (`/api/v1/org`):

| Endpoint | Fungsi |
|---|---|
| `GET /dashboard` | Ujian siap/berjalan/ditutup dengan jumlah online, terputus, menunggu, incident (pengawas: hanya ujian yang ditugaskan) |
| `GET /invigilators` | Anggota berperan INVIGILATOR untuk dipilih (Exam Admin) |

Baris `GET /exams/{id}/attempts` kini memuat `open_incidents`, `health` (dari heartbeat), dan
`client_version`; `GET /attempts/{id}` memuat `events` (timeline §27.6) dan `incidents` peserta
(yang belum ditinjau dulu, lalu terbaru; PRD v0.3.6).
`examguard seed live-exam --identity-check MANUAL` membuat ujian demo dengan Check-in Queue.

## Upgrade dari Phase 1c-1

```bash
pip install -e ".[dev]"
examguard db upgrade        # migrasi 0004, 0005, 0006
```

## Check-in, emergency unlock, incident (PRD §12.5, §22, §27.8)

| Endpoint (`/api/v1/org`) | Fungsi | Izin |
|---|---|---|
| `GET /exams/{id}/checkin-queue` | Peserta menunggu persetujuan identitas + link foto | invigilator |
| `GET /identity-photos/{id}` | Foto (didekripsi saat dibaca; setiap akses tercatat di audit log) | invigilator |
| `POST /attempts/{id}/emergency-unlock` | Metode online: command `EMERGENCY_UNLOCK` bertanda tangan | invigilator |
| `POST /attempts/{id}/unlock-response` | Metode challenge–response: masukkan challenge 8 karakter dari layar client | invigilator |
| `POST /exams/{id}/backup-codes` | Kode cadangan cetak (`XXXXX-XXXXX`), ditampilkan sekali; buat **sebelum** peserta launch | invigilator |
| `GET /exams/{id}/incidents` | Incident terbuka dulu, lalu HIGH → INFO; filter `status`, `severity`, `attempt_id` | monitor |
| `GET /incidents/{id}`, `POST /incidents/{id}/review` | Detail + event; review `REVIEWED`/`DISMISSED`/`ESCALATED` | monitor / invigilator |

Foto identity check disimpan terenkripsi (AES-256-GCM) di `EXAMGUARD_STORAGE_DIR`
(default `.examguard/storage`). Lapisan `storage.py` bisa diganti backend S3 tanpa mengubah API.

## Integration API (LMS / website ujian, PRD §16.4–16.6)

1. Org Admin membuat integrasi: `POST /api/v1/org/integrations {"name", "webhook_url"}`. Respons
   berisi `client_id` dan `secret` — **secret hanya ditampilkan sekali** (bisa diganti lewat
   `/rotate-secret`, dicabut lewat `/revoke`).
2. LMS memanggil `/integration/v1/...` dengan HTTP Basic (`client_id` sebagai username, `secret`
   sebagai password). Di `/docs`, isi kotak **IntegrationCredentials** pada tombol Authorize.

| Endpoint | Fungsi |
|---|---|
| `GET /integration/v1/exams` | Daftar ujian organisasi |
| `POST /integration/v1/exams/{id}/candidates` | Daftarkan peserta (`email`, `full_name`, `candidate_ref`); idempoten per `candidate_ref`; mengembalikan launch link bila ujian sudah dibuka |
| `POST /integration/v1/attempts/{id}/launch` | Launch link baru (15 menit) saat peserta menekan "Mulai" |
| `GET /integration/v1/attempts/{id}` | Status, deadline, `state_version` |
| `POST /integration/v1/attempts/{id}/completion` | Jawaban final tersimpan → ACTIVE → SUBMITTED + **completion token** (JWT, 10 menit). Diulang setelah respons hilang → token baru, tanpa transisi kedua. Status selain ACTIVE → `409 ATTEMPT_NOT_ACTIVE` (LMS wajib menolak jawaban) |
| `POST /integration/v1/attempts/{id}/result` | Simpan skor/hasil setelah attempt final |

**Webhook.** Setiap transisi penting (`attempt.started/paused/resumed/deadline_updated/submitted/
expired/terminated/reopened/reinstated`) masuk outbox dalam transaksi yang sama dengan transisinya,
lalu dikirim scheduler ke `webhook_url` setiap integrasi aktif organisasi. Header:

```text
X-ExamGuard-Event-Id: <event_id>            (kunci idempotensi; retry memakai id yang sama)
X-ExamGuard-Signature: kid=<…token>, ts=<unix_ms>, sig=<base64url Ed25519(ts + "." + body)>
```

LMS memverifikasi dengan key set yang sama dengan attestation token (lihat `webhooks.verify`).
Gagal → dicoba ulang 30 d, 1 m, 2 m, 5 m, 10 m, 30 m, lalu tiap jam; setelah 10 kali → FAILED.
Riwayat pengiriman: `GET /api/v1/org/integrations/{id}/deliveries`.

## Ujian demo baru tanpa reset

```bash
examguard seed live-exam --in-minutes 3      # membuat LIVE-MMDD-HHMM dengan peserta1..3 dan pengawas
```

## Upgrade dari Phase 1b

```bash
pip install -e ".[dev]"     # dependency baru: cryptography, websockets
examguard db upgrade        # menerapkan migrasi 0003
examguard keys dev-init     # dev: root key di .examguard/dev-root.key + server key + key set
```

`seed demo` juga menjalankan `keys dev-init` otomatis. Untuk produksi, root key dibuat dan disimpan
**offline** (`examguard keys init-root --out D:\root.key`), lalu `examguard keys rotate --root-key ...`;
server hanya menyimpan server key terenkripsi dengan `EXAMGUARD_KEY_ENCRYPTION_KEY`.

## Isi Phase 1c-1

| Area | Yang sudah jalan |
|---|---|
| Kunci (§19) | Server key per `use` (`<base>.command/state/config/token`), key set ditandatangani root key, rotasi & revoke lewat CLI |
| Launch (§12) | `POST /api/v1/candidate/enrollments/{id}/launch` → `examguard://launch?t=…` (sekali pakai, 15 menit); Signed Exam Config |
| Device session (§18) | Registrasi public key Ed25519; semua request berikutnya ditandatangani (EG-Sig, ±60 detik) |
| State & command (§17) | Full state sync bertanda tangan; command dari outbox ditandatangani sekali dan dikirim lewat WebSocket atau HTTPS; ACK |
| Event (§15, §17.8) | Upload batch idempoten; incident otomatis sesuai Event Dictionary (OPEN/CLOSE digabung); `UNMONITORED_INTERRUPTION` saat reconnect |
| Attestation (§16.2) | JWT EdDSA 5 menit untuk website ujian |

### Mencoba protokol

```bash
examguard sim link --exam DEMO-LIVE --email peserta1@demo.example.com   # launch link peserta
```

Client sungguhan belum ada (Phase 2). `tests/refclient.py` adalah client referensi Python yang
menandatangani request persis seperti yang harus dilakukan client Rust.

## Upgrade dari Phase 1a

```bash
pip install -e ".[dev]"     # wajib: entry point CLI berubah
examguard db upgrade        # menerapkan migrasi 0002 ke database yang sudah ada
```

Data 1a tetap utuh. Untuk mencoba fitur 1b dengan data demo baru, pakai database kosong
(`examguard db bootstrap --superuser-url ... --drop-existing`, lalu `db upgrade` dan `seed demo`).

## Isi Phase 1b

| Area | Yang sudah jalan |
|---|---|
| State machine | Seluruh transisi §10.3 di satu tabel (`state.py`); `INVALID_TRANSITION` untuk sisanya; row lock + `expected_state_version`; setiap perubahan menulis `state_transitions` dan audit log |
| Timing | Rumus deadline §11.2, pause `KEEP_RUNNING`/`PAUSE_TIMER`, add time, extend seluruh ujian, deadline absolut |
| Scheduler | READY→RUNNING, NO_SHOW, EXPIRED, INTERRUPTED (threshold per ujian), RUNNING→CLOSED; aman multi-instance (`FOR UPDATE SKIP LOCKED`) |
| Alur client (internal) | Device session, start, heartbeat, reconnect (auto-resume / menunggu persetujuan), pindah perangkat, submit, identity check; diekspos lewat protokol di Phase 1c |
| Invigilator | Penugasan per ujian; izin invigilator hanya berlaku di ujian yang ditugaskan |
| Aksi staf | Warning, pause/resume, add time, force submit, terminate (kategori wajib), re-entry, reopen/reinstate, identity approve/reject, bulk, extend, finalize |
| Command outbox | Setiap aksi yang perlu sampai ke client dicatat di `commands` (PENDING); Phase 1c menandatangani dan mengirimnya |

## Isi Phase 1a

| Area | Yang sudah jalan |
|---|---|
| Multi-organisasi | Organisasi, membership & role (ORG_ADMIN, EXAM_ADMIN, INVIGILATOR), Platform Admin, isolasi data dengan PostgreSQL Row-Level Security |
| Akun | Registrasi peserta + verifikasi email, login staf & peserta, sesi opaque yang bisa dicabut |
| Ujian | Create/edit (DRAFT), publish dengan validasi lengkap, unpublish, cancel; default `latest_start`, `checkin_open`, `allowed_origins` |
| Tes publik (model TOEFL) | Katalog publik, registrasi mandiri, kuota atomik, voucher/access code, batal & pindah sesi dalam satu `series` |
| Tes instansi | Undangan email per ujian, token terikat ke email, kelola enrollment & akomodasi waktu |
| Pengaturan berjenjang | Platform → organisasi → ujian, dengan batas (bounds) dan konfirmasi saat memperpendek retensi |
| Audit log | Append-only, hash-chained per organisasi, bisa diverifikasi lewat API dan CLI |
| Email | Outbox transaksional (pengiriman nyata di Phase 3); dibaca dengan `examguard outbox list` |

## Quickstart

Prasyarat: Python 3.11+, PostgreSQL 14+ (diuji di 16).

```bash
pip install -e ".[dev]"
cp .env.example .env            # sesuaikan password & host

# 1. buat role owner + runtime dan database (sekali, dengan akun superuser)
examguard db bootstrap --superuser-url postgresql://postgres:PASSWORD@127.0.0.1:5432/postgres

# 2. jalankan migrasi (sebagai role owner)
examguard db upgrade

# 3. data demo (opsional) lalu jalankan server + scheduler
examguard seed demo
examguard serve --port 8080 --with-scheduler   # dokumentasi interaktif: http://127.0.0.1:8080/docs
```

Scheduler juga bisa dijalankan terpisah: `examguard scheduler run` (atau `--once` untuk satu kali tick).
Tanpa scheduler, status berbasis waktu (NO_SHOW, EXPIRED, INTERRUPTED, CLOSED) tidak bergerak.

### Mencoba Phase 1b tanpa client

`seed demo` membuat ujian **DEMO-LIVE** (PT Contoh Jaya) yang mulai 5 menit lagi
(`--live-in-minutes N` untuk mengubahnya), dengan pengawas dan tiga peserta. Jam yang ditampilkan dalam UTC.

```bash
examguard sim attempts  --exam DEMO-LIVE
examguard sim launch    --exam DEMO-LIVE --email peserta1@demo.example.com   # setelah window_start
examguard sim heartbeat --exam DEMO-LIVE --email peserta1@demo.example.com --count 0   # Ctrl+C untuk berhenti
```

Hentikan heartbeat lebih dari 30 detik untuk melihat INTERRUPTED, lalu kirim heartbeat lagi:
jeda < 10 menit dilanjutkan otomatis, ≥ 10 menit menunggu persetujuan pengawas.
`sim launch --new-device` mensimulasikan pindah perangkat. Aksi pengawas dilakukan lewat `/docs`
dengan login `pengawas@pt-contoh-jaya.demo.example.com`.

Akun demo (password default `demo-password-123`):

| Email | Peran |
|---|---|
| platform@demo.example.com | Platform Admin |
| admin@public.demo.example.com | ORG_ADMIN — ExamGuard Public Testing (boleh tes publik) |
| exams@examguard-public.demo.example.com | EXAM_ADMIN — ExamGuard Public Testing |
| hr@contohjaya.demo.example.com | ORG_ADMIN — PT Contoh Jaya |
| exams@pt-contoh-jaya.demo.example.com | EXAM_ADMIN — PT Contoh Jaya |
| pengawas@pt-contoh-jaya.demo.example.com | INVIGILATOR — ditugaskan ke DEMO-LIVE |
| peserta1..3@demo.example.com | Peserta DEMO-LIVE |

## CLI

```text
examguard db bootstrap --superuser-url URL [--drop-existing]   buat role & database
examguard db upgrade                                           migrasi
examguard platform create-admin --email E --name N             Platform Admin (password diminta)
examguard org create --slug S --name N [--public] [--admin-email E --admin-name N --admin-password P]
examguard org list
examguard org add-member --org S --email E --role EXAM_ADMIN [--name N --password P]
examguard audit verify [--org S]                               exit code 1 jika ada rantai rusak
examguard outbox list [--to E] [--limit N]                     lihat email yang antre (dev)
examguard seed demo [--live-in-minutes N]
examguard serve [--host H --port P --reload] [--with-scheduler --scheduler-interval S]
examguard scheduler run [--once] [--interval S]
examguard sim attempts --exam CODE
examguard sim launch|register|identity|start|submit (--attempt ID | --exam CODE --email E) [--new-device]
examguard sim heartbeat (...) [--count N --interval S --cause NETWORK_FAILURE]
examguard keys init-root --out PATH | rotate --root-key PATH | publish | revoke KID | list | dev-init
examguard sim link (--exam CODE --email E)
examguard seed live-exam [--org SLUG --in-minutes N --candidates N]
examguard openapi --out openapi.json
```

Error bisnis di CLI ditampilkan satu baris, misalnya `LATE_START_CLOSED: the latest start time has passed`.

## API

Spesifikasi lengkap ada di `openapi.json` (juga di `/docs` saat server jalan). Ringkasan:

| Prefix | Pengguna | Autentikasi |
|---|---|---|
| `/api/v1/public/exams` | Siapa saja | — |
| `/api/v1/candidate/...` | Peserta (Candidate Portal) | `Authorization: Bearer <token peserta>` |
| `/api/v1/staff/...` | Staf: login, `me` | `Authorization: Bearer <token staf>` |
| `/api/v1/org/...` | Staf dalam satu organisasi (Admin Web) | Bearer staf + `X-Org-Id: <uuid>` |
| `/api/v1/platform/...` | Platform Admin | Bearer staf dengan flag platform admin |

Endpoint Phase 1b (semua di bawah `/api/v1/org`, butuh `X-Org-Id`):

| Endpoint | Fungsi | Izin |
|---|---|---|
| `GET /exams/{id}/attempts` | Live Monitoring: status, koneksi, sisa waktu, ringkasan | monitor |
| `GET /attempts/{id}` | Candidate Detail: transisi, device session, command, `available_actions` | monitor |
| `GET /exams/{id}/reentry` | Interrupted Sessions & Re-entry Requests | monitor |
| `POST /attempts/{id}/warning`, `pause`, `resume`, `add-time` | Kontrol individu | invigilator |
| `POST /attempts/{id}/force-submit`, `terminate` | Mengakhiri attempt (`terminate` wajib `reason_category`) | invigilator |
| `POST /attempts/{id}/reentry/allow`, `reentry/reject` | Persetujuan masuk kembali | invigilator |
| `POST /attempts/{id}/identity/approve`, `identity/reject` | Check-in (foto menyusul di 1c) | invigilator |
| `POST /attempts/{id}/reopen`, `reinstate` | Deadline baru wajib di masa depan | Exam Admin |
| `POST /exams/{id}/bulk` | WARNING/PAUSE/RESUME/ADD_TIME; TERMINATE butuh `confirm_exam_code` | invigilator / Exam Admin |
| `POST /exams/{id}/extend`, `finalize` | Seluruh ujian | Exam Admin |
| `GET/POST /exams/{id}/invigilators`, `DELETE .../{user_id}` | Penugasan pengawas | Exam Admin |

Semua aksi menerima `expected_state_version` opsional. Bila attempt sudah berubah sejak Admin Web
memuatnya, server menjawab `409 STATE_CONFLICT` sehingga dua pengawas tidak saling menimpa.

**Mencoba API di `/docs`:** login lewat `POST /api/v1/staff/auth/login`, klik tombol **Authorize**
di kanan atas, isi `SessionToken` dengan token (tanpa kata `Bearer`) dan `OrgId` dengan `org_id` dari
`GET /api/v1/staff/me`. Keduanya lalu terkirim otomatis ke semua endpoint.

Format error selalu `{"error": {"code": "...", "message": "...", "details": ...}}`. Kode yang dipakai
klien antara lain `EXAM_FULL`, `REGISTRATION_CLOSED`, `ALREADY_REGISTERED`, `EMAIL_NOT_VERIFIED`,
`INVALID_ACCESS_CODE`, `NOT_SAME_SERIES`, `EXAM_NOT_PUBLISHABLE`, `RETENTION_SHORTEN_CONFIRMATION_REQUIRED`.

Data milik organisasi lain selalu dijawab **404** (bukan 403), sehingga keberadaannya tidak bocor. Header `X-Org-Id` untuk organisasi yang pengguna bukan anggotanya dijawab 403.

## Model keamanan data

- **Dua role database.** Migrasi berjalan sebagai `examguard_owner` (pemilik tabel). Aplikasi berjalan
  sebagai `examguard_app`, yang *bukan* pemilik, sehingga RLS selalu berlaku untuknya.
- **Konteks per transaksi.** Setiap request menyetel `app.ctx` (`public`, `candidate`, `staff`,
  `platform`, `system`), `app.org_id`, `app.user_id`, `app.candidate_id` secara transaction-local.
  Policy di `migrations/sql/0001_initial.sql` membaca nilai ini.
- **Dua lapis.** Setiap query di service tetap memfilter `org_id`; RLS memastikan query yang lupa
  filter pun hanya melihat data organisasinya sendiri (lihat `tests/test_tenancy_isolation.py`).
- **Integritas dari database.** `org_id` pada enrollment, attempt, dan undangan diturunkan oleh trigger
  dari parent-nya, bukan dari input. Hanya konteks platform yang dapat mengubah `can_publish_public`
  atau `is_platform_admin`.
- **Audit log.** Role runtime tidak punya INSERT/UPDATE/DELETE pada `audit_log`; penulisan hanya lewat
  fungsi `eg_audit_append()` yang menghitung hash chain. `eg_audit_verify()` mendeteksi perubahan
  isi maupun baris yang dihapus.
- **Kuota.** `eg_reserve_seat()` memakai UPDATE bersyarat (row lock), sehingga registrasi serentak
  tidak pernah melebihi kapasitas (diuji dengan 20 thread untuk 5 kursi).
- **State version.** Trigger `attempts_version_guard` menolak perubahan status atau deadline yang tidak
  menaikkan `state_version` tepat satu. `state_transitions` hanya bisa di-INSERT oleh role runtime.
- **Urutan lock.** Selalu exam → attempt, sehingga extend dan reopen tidak deadlock satu sama lain.

## Testing

Test memakai PostgreSQL sungguhan, karena RLS tidak bisa diuji dengan SQLite atau mock.

```bash
export EXAMGUARD_TEST_SUPERUSER_URL=postgresql://postgres:PASSWORD@127.0.0.1:5432/postgres
pytest
```

Fixture membuat database `examguard_test` beserta role uji tersendiri, lalu mengosongkan tabel di
antara test. Waktu dibekukan lewat `examguard.clock.set_now()`.

| File | Cakupan |
|---|---|
| `test_auth.py` | Registrasi, verifikasi email, login, logout, kedaluwarsa sesi, anti-enumerasi |
| `test_tenancy_isolation.py` | Isolasi API dan RLS, trigger integritas, audit append-only |
| `test_exams.py` | Validasi publish, default, pembekuan setelah publish, cancel, izin role |
| `test_registration.py` | Katalog, aturan registrasi, jendela registrasi, kuota, batal, pindah sesi, konkurensi |
| `test_invitations.py` | Undangan, keterikatan email, revoke/kedaluwarsa, pengelolaan enrollment |
| `test_settings.py` | Resolusi berjenjang, validasi, konfirmasi retensi, clamping batas platform |
| `test_audit_and_platform.py` | Urutan & verifikasi audit, deteksi manipulasi, administrasi platform |
| `test_timing.py` | Rumus deadline §11.2 (contoh PRD 09:20 → 10:30), akomodasi, extend, pause timer |
| `test_state_machine.py` | Tabel transisi = §10.3; seluruh 12 status × 18 trigger ke database; kategori terminate; trigger versi |
| `test_client_flow.py` | Check-in, start, late start, identity check, heartbeat, auto-resume, re-entry, pindah perangkat |
| `test_scheduler.py` | RUNNING, NO_SHOW, EXPIRED, PAUSE_TIMER, INTERRUPTED per ujian, CLOSED, `SKIP LOCKED` |
| `test_staff_actions.py` | Semua aksi staf, conflict versi, reopen/reinstate, finalize, extend, bulk, 4 thread serentak |
| `test_invigilator_access.py` | Lingkup invigilator, Org Admin read-only, 404 lintas org, RLS tabel 1b |
| `test_openapi_auth.py` | `/docs` memakai security scheme (tombol Authorize), bukan parameter header |
| `test_integration_api.py` | Kredensial & rotasi, pendaftaran idempoten, isolasi org, alur Level 2 + completion token, webhook bertanda tangan/retry/gagal |
| `test_admin_web_api.py` | Dashboard & lingkup pengawas, daftar pengawas, incident/health/event di monitoring, penyajian `/admin` |
| `test_proctoring.py` | Foto terenkripsi & Check-in Queue, challenge–response, unlock online, kode cadangan, review incident |
| `test_protocol.py` | Key set & root, launch token, EG-Sig (skew, signature, body palsu), state/command bertanda tangan, event/incident, attestation, WebSocket |

## Batasan yang disadari

- Retensi data (§24.1, mis. penghapusan foto identitas) belum dijadwalkan otomatis.
- Pengecekan event dari client memakai Event Dictionary default; override severity lewat `policy.severity_overrides`.
- Webhook dikirim ke semua integrasi aktif organisasi yang punya `webhook_url` (belum ada filter per ujian).
- `POST /integration/v1/exams` (membuat ujian dari LMS, opsional di PRD) belum ada; ujian dibuat lewat Admin API.
- WebSocket memeriksa command baru dengan polling DB (`EXAMGUARD_WS_POLL_SECONDS`, default 1 detik)
  per koneksi. Cukup untuk MVP; `LISTEN/NOTIFY` PostgreSQL bisa menggantikannya tanpa mengubah protokol.
- Tanda tangan EG-Sig dapat di-replay dalam jendela ±60 detik. Dampaknya terbatas (heartbeat memakai
  `seq`, event idempoten, transisi divalidasi state machine); nonce per request bisa ditambah nanti.
- Unfinalize (override Platform Admin + Org Admin) bukan MVP.
- Reset password, rate limiting login, dan pengiriman email sungguhan → Phase 3.
- Import peserta via CSV dan Integration API untuk website ujian → Phase 1b/3.
- Konteks `system` dapat disetel oleh kode aplikasi mana pun. RLS di sini adalah pertahanan lapis
  kedua terhadap bug query, bukan perlindungan terhadap server aplikasi yang sudah dibobol.
- Signup dengan email yang sudah terdaftar mengembalikan `409`, sehingga keberadaan akun dapat
  diketahui. Ini kompromi UX yang umum; bisa diganti alur "cek email Anda" bila diperlukan.

## Struktur

```text
migrations/sql/0001_initial.sql   skema, trigger, RLS policy, fungsi audit & kuota
migrations/sql/0002_state_engine.sql  timing attempt, transisi, device session, command, invigilator
migrations/versions/
src/examguard/
  api/            router FastAPI (candidate, staff/org, attempts, platform) dan dependency auth
  services/       logika bisnis (auth, orgs, exams, registration, attempts, lifecycle,
                  client_flow, invigilators)
  state.py        tabel transisi & apply()
  timing.py       rumus deadline (tanpa database)
  scheduler.py    transisi berbasis waktu
  access.py       otorisasi per ujian
  sessions.py     device session & status koneksi
  commands.py     command outbox
  db.py           engine, session, konteks RLS
  audit.py        pencatatan & verifikasi audit
  settings_service.py  pengaturan berjenjang
  cli.py          CLI `examguard`
tests/
```
