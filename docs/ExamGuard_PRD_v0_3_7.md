# Product Requirements Document
## ExamGuard — Secure Exam Browser & Proctoring Platform

| Item | Nilai |
|---|---|
| Versi | 0.3.7 (Draft untuk review) |
| Versi sebelumnya | 0.3.6 |
| Desktop Client | Rust + Chromium Embedded Framework (CEF) |
| Target Platform | Windows, macOS, Linux X11; Linux Wayland wajib di roadmap (§13.2) |
| AI Runtime | ONNX Runtime (dipanggil langsung dari Rust) |
| Server/Web | ExamGuard Server, Admin Web, Candidate Portal, Reference Exam Website |
| Model penyelenggaraan | Tes instansi dan tes perorangan publik (§8) |
| Reference Server | Python FastAPI + PostgreSQL + Redis |

---

# 0. Riwayat Perubahan

## 0.1 Perubahan v0.3.6 → v0.3.7

Revisi hasil implementasi Phase 3b-1 (Candidate Portal). Model produk tidak berubah.

| Area | v0.3.6 | v0.3.7 |
|---|---|---|
| Pintu masuk web | Admin Web di `/admin/`; Candidate Portal belum ada | Halaman masuk di `/` dengan dua pilihan: peserta (`/portal/`) dan staf (`/admin/`). Login, akun, dan sesi peserta dan staf tetap terpisah, termasuk di browser yang sama (§28.5, Q28) |
| Perangkat peserta | Tidak ditegaskan untuk portal | Peserta memakai laptop/PC, sama seperti untuk ujian; portal dirancang untuk layar desktop dan tetap terbaca di layar kecil (§28.5) |
| Tombol Mulai Ujian | Aktif dari `checkin_open` sampai `latest_start` | Tetap, ditambah: aktif juga selama attempt berjalan (membuka ulang client setelah crash) dan untuk attempt `REOPENED`/`REINSTATED`. Aturan jendela berlaku untuk portal; Integration API (LMS) dan alat pengembangan tidak dibatasi (§28.4, Q29) |
| Reset password | Disebut di §28.1 | Tautan email sekali pakai, berlaku 60 menit; tautan lama batal saat yang baru dipakai; semua sesi akun dikeluarkan; membuka tautan sekaligus memverifikasi email (§28.1) |
| Undangan | Diterima setelah masuk | Halaman undangan menampilkan isinya sebelum masuk, mengarahkan ke masuk atau buat akun dengan email tujuan, dan mengingat undangan sampai peserta masuk (§28.3) |
| Fase | Phase 3b satu tahap | 3b-1 Candidate Portal ✓; 3b-2 Admin Web lanjutan; 3b-3 terjemahan Inggris (§30.2) |

## 0.2 Perubahan v0.3.5 → v0.3.6

Revisi hasil uji coba Phase 3a: kolom Incident di Live Monitoring hanya menampilkan jumlah, tanpa keterangan incident apa yang terjadi. Model produk tidak berubah.

| Area | v0.3.5 | v0.3.6 |
|---|---|---|
| Candidate Detail | Timeline event mentah (kode event) | Bagian **Incident** di atas aksi: waktu mulai–selesai, nama kejadian dalam bahasa pengguna beserta penjelasan singkat, severity, durasi (atau "berlangsung" yang terus dihitung), rincian (penyebab terputus, tingkat keyakinan AI, jumlah event), dan status tinjauan; klik baris untuk event terkait dan meninjau (§27.6, Q27) |
| Live Monitoring | Angka incident hanya teks | Angka incident dapat diklik dan langsung membuka Candidate Detail di bagian Incident (§27.5) |
| Label event | Kode event (`FOCUS_LOST`) | Nama yang dapat dibaca ("Keluar dari jendela ujian"); kode tetap terlihat di dialog incident (§15, §27.8) |
| Status tinjauan `OPEN` | "Terbuka" | "Belum ditinjau", agar tidak tertukar dengan incident yang masih berlangsung (§8.6) |

## 0.3 Perubahan v0.3.4 → v0.3.5

Revisi hasil uji coba Phase 3a: pengawas melihat status Offline dan Terputus muncul pada waktu yang berbeda (Offline 30 detik, Terputus 60 detik, ditambah jeda scheduler), sehingga membingungkan. Model produk tidak berubah.

| Area | v0.3.4 | v0.3.5 |
|---|---|---|
| Client tertutup (crash, aplikasi ditutup, laptop mati) | Baru terdeteksi dari heartbeat yang hilang: Offline 30 detik, Terputus 60 detik | Koneksi WSS yang tertutup langsung membuat attempt `INTERRUPTED` dan `OFFLINE` bersamaan; tampil di Admin Web ≤ 2 detik (§17.6, Q25) |
| Jaringan hilang diam-diam | Offline 30 detik, Terputus 60 detik | Satu ambang untuk keduanya: `interruption_threshold`, default **30 detik** (§10.2, §17.6, Q25) |
| Bukti hidup | Hanya heartbeat (dan request start, Q18) | Setiap request bertanda tangan dari device session aktif; request itu juga melanjutkan attempt yang terputus (§17.6) |
| Penyebab reconnect | Dikirim pada heartbeat setelah sync | Dikirim pada request pertama setelah tersambung kembali (§20.3) |
| Incident jeda singkat | Setiap reconnect membuat `UNMONITORED_INTERRUPTION` | Hanya bila jeda ≥ 10 detik; jeda lebih singkat tetap tercatat di riwayat transisi (§20.3, Q26) |

## 0.4 Perubahan v0.3.3 → v0.3.4

Revisi hasil implementasi Phase 3a (Admin Web). Model produk tidak berubah.

| Area | v0.3.3 | v0.3.4 |
|---|---|---|
| Teknologi Admin Web | Tidak ditetapkan | React + Vite + TypeScript; hasil build disajikan server di `/admin/`, sehingga operasional tidak butuh Node.js (§27, Q21) |
| Pembaruan Live Monitoring | WebSocket Admin Web | Pemuatan ulang berkala tiap 2 detik selama tab terlihat; target < 3 detik (§25) tetap terpenuhi. WebSocket staf dapat ditambahkan tanpa mengubah UI (§27.5, Q22) |
| Status review incident | OPEN / DISMISSED / NOTED / ACTIONED | OPEN / REVIEWED / DISMISSED / ESCALATED, sesuai implementasi server sejak Phase 1c (§8.6, §27.8, Q23) |
| Fase | Phase 3 satu tahap | Phase 3a (Admin Web inti) selesai; Phase 3b (pengaturan, integrasi, audit, platform, Candidate Portal, terjemahan Inggris) menyusul (§30.2, Q24) |

## 0.5 Perubahan v0.3.2 → v0.3.3

Revisi hasil implementasi Phase 2 (headless client simulator). Model produk tidak berubah.

| Area | v0.3.2 | v0.3.3 |
|---|---|---|
| Aturan STALE | Berlaku untuk semua command dengan `state_version` ≤ versi terakhir | Hanya untuk command yang mengubah status; `WARNING` dan `EMERGENCY_UNLOCK` tidak pernah STALE (§17.3, Q20) |
| Command duplikat | Ditolak tanpa ACK yang jelas | Tidak diterapkan ulang, tetapi tetap di-ACK `APPLIED` (§17.3, §17.5, Q20) |
| Fase | Phase 2 belum selesai | Phase 2 selesai; skenario crash, reconnect, dan replay lulus terhadap server (§30.2) |

## 0.6 Perubahan v0.3.1 → v0.3.2

Revisi hasil implementasi server Phase 1c. Model produk tidak berubah; beberapa detail protokol ditetapkan. Detail wire format lengkap ada di `docs/PROTOCOL.md` pada repositori server.

| Area | v0.3.1 | v0.3.2 |
|---|---|---|
| Launch token | Single-use | `/client/v1/launch` (menukar token dengan config) boleh diulang; token baru habis saat registrasi device session (§12.1) |
| Integration API | Belum ada cara meminta launch link baru | `POST /integration/v1/attempts/{id}/launch`; autentikasi HTTP Basic; completion idempoten saat diulang (§16.4, §16.5) |
| Webhook | "Ditandatangani" | Ed25519 dengan kunci `use=token`, format header dan jadwal retry ditetapkan; dikirim ke semua integrasi aktif organisasi (§16.6, Q17) |
| Start setelah check-in | Tidak diatur | Request start bertanda tangan dihitung sebagai heartbeat, sehingga waktu tunggu check-in tidak dianggap jeda (§18, Q18) |
| Event dari perangkat yang dicabut | Tidak diatur | Tetap boleh diunggah karena merupakan bukti (§18, Q19) |
| Emergency unlock | Rumus umum | Format challenge, respons 8 digit, format dan hash kode cadangan ditetapkan; `attempt_unlock_secret` dikirim saat registrasi (§22) |
| Foto identity check | Diunggah terenkripsi | Disimpan terenkripsi at rest; setiap akses foto oleh staf tercatat di audit log (§12.5) |
| Fase | Phase 1c belum selesai | Phase 1 (server) selesai (§30.2) |

## 0.7 Perubahan v0.3 → v0.3.1

Revisi klarifikasi dan temuan implementasi Phase 1b. Tidak ada perubahan pada model produk maupun protokol; state model mendapat satu transisi yang sebelumnya hanya tersirat di §18.

| Area | v0.3 | v0.3.1 |
|---|---|---|
| Fase pengembangan | Phase 1 sebagai satu fase | Phase 1 dipecah menjadi 1a, 1b, dan 1c dengan exit criteria masing-masing (§30.2) |
| Akomodasi waktu | Perilaku saat attempt sudah berjalan tidak diatur | Perubahan akomodasi setelah attempt dimulai tidak menggeser deadline; tambahan waktu melalui Add Time (§11.3, Q12) |
| Enrollment ujian `PRIVATE` | Batas waktu undangan dan enrollment tidak diatur | Undangan dan enrollment baru ditolak sejak exam `RUNNING` (§8.4, §9, Q13) |
| Pindah perangkat saat ujian berjalan | §18 mewajibkan persetujuan, tetapi §10.3 hanya punya jalur dari `INTERRUPTED` | Transisi `ACTIVE → WAITING_FOR_INVIGILATOR` ditambahkan; registrasi perangkat baru saat `PAUSED` ditolak (§10.3, §18, Q15) |
| `state_version` | Naik pada setiap transisi status | Juga naik pada perubahan deadline tanpa perubahan status (§10.3) |
| Extend seluruh ujian | Hanya attempt yang sudah berjalan | Juga berlaku untuk peserta yang mulai setelah extend (§11.3, Q16) |

## 0.8 Perubahan v0.2 → v0.3

| Area | v0.2 | v0.3 |
|---|---|---|
| Model penyelenggaraan | Satu penyelenggara | Tes instansi **dan** tes perorangan publik dengan pendaftaran mandiri, seperti model TOEFL (§8) |
| Tenancy | Direkomendasikan single-tenant | Organization menjadi entitas utama sejak awal, isolasi ditegakkan dengan RLS (§8.2) |
| Akun peserta | Didaftarkan admin | Akun global; registrasi mandiri ke sesi publik dan undangan instansi (§8.4) |
| Komponen | Client, Server, Admin Web | Ditambah **Candidate Portal** (§28) dan **Reference Exam Website** (§29) |
| Roles | 4 role | Candidate, Invigilator, Exam Admin, Org Admin, Platform Admin (§7) |
| Identitas peserta | Tidak ada | Identity check manual (selfie + foto kartu identitas) per ujian (§12.5) |
| `latest_start` default | `window_end` | `window_start` + 30 menit (§11.1) |
| Reject re-entry | TERMINATED | TERMINATED dengan `reason_category` wajib (§10.3) |
| Linux | Kiosk diusulkan untuk STRICT | X11 di MVP; Wayland menjadi requirement wajib di roadmap, arsitektur disiapkan sejak MVP (§13.2) |
| Deteksi VM | Blokir di template Strict | Warn-only di MVP; roadmap deteksi tanpa hypervisor bit dan opsi blokir WSL (§13.3) |
| Emergency unlock | Online + challenge–response | Ditambah kode cadangan cetak dan safety valve setelah deadline (§22) |
| Retensi | 90 hari tetap | Berjenjang platform → organisasi → ujian; default 30/90 hari (§24.1) |
| Integration API | Untuk LMS pihak lain | Tetap menjadi batas arsitektur walau website ujian dibuat sendiri; endpoint hasil ditambahkan (§16) |
| Fase | 7 fase | 8 fase + roadmap pasca-MVP (§30) |

## 0.9 Perubahan v0.1 → v0.2

| Area | v0.1 | v0.2 |
|---|---|---|
| State model | Satu state machine campuran exam + attempt | Dipisah: **Exam State** (§9) dan **Attempt State** (§10) dengan tabel transisi lengkap |
| State yang hilang | `DRAFT`, `WAITING_FOR_INVIGILATOR` hanya di UI | Masuk ke model formal; `EXTENDED` dihapus (itu event, bukan state) |
| Konektivitas | `INTERRUPTED` bercampur dengan status online | Dimensi terpisah: `connection_status` (ONLINE/OFFLINE) vs `attempt_status` |
| Timing | Start, End, Duration tanpa relasi jelas | Rumus deadline, late start, akomodasi waktu, pause timer, clock offset (§11) |
| Launch & login | Tidak didefinisikan | Launch token, signed exam config, preflight checks (§12) |
| Lockdown | Diasumsikan setara di semua OS | Matriks tingkat jaminan per OS; Wayland eksplisit dibatasi (§13) |
| Integrasi LMS | Hanya JS Bridge | Tiga level integrasi, **Attestation Header**, Integration API, webhook (§16) |
| Completion token | Penandatangan tidak jelas | Ditandatangani ExamGuard Server atas permintaan LMS (§16.5) |
| Protokol | Daftar field command | Envelope formal, `kid`, `state_version`, ACK, aturan replay (§17) |
| Command | `REOPEN_EXAM`, `ADMIN_REINSTATE` dikirim ke client | Menjadi transisi server-side; client sudah tertutup saat itu (§17.4) |
| Device session key | Dibuat, tapi penggunaannya tidak jelas | Dipakai untuk menandatangani setiap request & heartbeat (§18) |
| Key management | Private/public key tunggal | Key set bertanda tangan, trust anchor, rotasi (§19) |
| Emergency unlock | Invigilator code / offline code tanpa detail | Challenge–response berbasis HMAC per attempt (§22) |
| Event | Tersebar, `PROHIBITED_APP` tidak terdaftar | Kamus event lengkap dengan severity default (§15) |
| Vektor kecurangan | Tidak mencakup remote access / VM | `REMOTE_ACCESS_DETECTED`, `VIRTUAL_MACHINE_DETECTED` masuk MVP (§13.3) |
| Privasi | Tidak dibahas | Consent, retensi, akses evidence, konteks UU PDP (§24) |
| NFR | Tidak ada | Skala, latensi, budget CPU/RAM, availability (§25) |
| Urutan fase | Client dulu | Protokol + Server dulu, dengan headless client simulator (§30) |

Keputusan yang sudah diambil dicatat di **§32.1 Decision Log**; keputusan sementara yang dapat ditinjau ulang di **§32.2**.

---

# 1. Product Overview

ExamGuard adalah platform ujian yang terdiri dari tiga komponen utama.

### ExamGuard Client

Aplikasi desktop cross-platform berbasis Rust yang digunakan peserta ujian. Fungsi utama: secure browser, device lockdown, application/process monitoring, camera dan microphone monitoring, AI-assisted proctoring, secure exam lifecycle, recovery setelah crash/restart, serta komunikasi real-time dengan ExamGuard Server.

### ExamGuard Server

Backend yang menjadi **authoritative source of truth** untuk status ujian, waktu, dan command administratif. Server juga menyediakan Integration API untuk website ujian (LMS).

### ExamGuard Admin Web

Aplikasi web untuk penyelenggara: membuat dan mengatur ujian, mendaftarkan peserta, menentukan URL website ujian, membuat security policy, memonitor peserta secara real-time, meninjau incident, mengendalikan sesi (pause/resume, tambahan waktu, terminate, reopen, reinstate), mengelola interrupted session, dan melihat audit trail.

### ExamGuard Candidate Portal

Portal web untuk peserta: membuat akun, mendaftar ke sesi tes publik, menerima undangan dari instansi, menjalankan system check, meluncurkan client, dan melihat status serta hasil ujian.

### Reference Exam Website

Website ujian fungsional (soal, pengerjaan, autosave, penilaian pilihan ganda) yang dibangun dalam proyek ini, sekaligus menjadi implementasi referensi integrasi. Dapat digantikan oleh sistem web ujian lain melalui Integration API.

### Model penyelenggaraan

ExamGuard mendukung dua model sekaligus:

- **Tes instansi**: perusahaan atau instansi membuat ujian untuk peserta yang mereka undang, misalnya untuk rekrutmen atau sertifikasi internal.
- **Tes perorangan (publik)**: penyelenggara menerbitkan jadwal sesi tes terbuka. Individu membuat akun, mendaftar sendiri, lalu mengikuti sesi bersama peserta perorangan lainnya, seperti model tes TOEFL.

Inti ExamGuard (client, protokol, state engine) tidak menyimpan soal maupun jawaban. Konten ujian berada di website ujian yang terhubung melalui Integration API (§16).

---

# 2. Scope & Non-Goals

## 2.1 In Scope

- Mengamankan perangkat peserta selama attempt aktif.
- Mendeteksi dan melaporkan event keamanan, proctoring, perangkat, dan sesi.
- Mengendalikan lifecycle attempt secara terpusat.
- Menyediakan kontrak integrasi yang dapat diverifikasi oleh website ujian.
- Mendukung penyelenggaraan tes oleh banyak instansi sekaligus tes perorangan publik dengan pendaftaran mandiri.

## 2.2 Non-Goals

- Inti ExamGuard (client, protokol, server) **bukan** LMS: tidak menyimpan soal atau jawaban. Konten ujian berada di website ujian.
- Reference Exam Website (§29) adalah website ujian fungsional, **bukan** platform assessment lengkap: tanpa adaptive testing, analisis butir soal, atau penerbitan sertifikat pada MVP.
- **Tidak** menyediakan payment gateway pada MVP; pendaftaran berbayar ditangani dengan voucher/access code.
- **Bukan** sistem penentu kecurangan: AI hanya menghasilkan event (§31).
- **Tidak** melakukan live video streaming ke pengawas pada MVP (hanya event + snapshot opsional).
- **Tidak** menjamin keamanan absolut terhadap perangkat yang sudah dikompromikan (root/admin penuh, kernel debugger, modified hardware). ExamGuard menaikkan biaya kecurangan dan mencatat anomali; tidak mengklaim mustahil dibobol.
- **Tidak** mendukung mobile/tablet pada MVP.

---

# 3. High-Level Architecture

```text
   ADMIN / INVIGILATOR / ORG ADMIN                 CANDIDATE
                 │                                     │
                 ▼                                     ▼
      ┌──────────────────────┐             ┌──────────────────────┐
      │ ExamGuard Admin Web  │             │  Candidate Portal    │
      └──────────┬───────────┘             └──────────┬───────────┘
                 └─────────────────┬──────────────────┘
                                   │ HTTPS
                                   ▼
                    ┌──────────────────────────┐      Integration API
                    │     ExamGuard Server     │◄─────────────────────────┐
                    │                          │      + signed webhooks   │
                    │ Tenancy & Registration   │─────────────────────────►│
                    │ Session & State Engine   │                          │
                    │ Policy Engine            │                ┌─────────┴──────────┐
                    │ Signing Service          │                │   Exam Website     │
                    │ WebSocket Gateway        │                │ (Reference Exam    │
                    │ Audit Log                │                │  Website / sistem  │
                    └────────────┬─────────────┘                │  web ujian lain)   │
                                 │ HTTPS (signed requests)      └─────────▲──────────┘
                                 │ WSS (signed commands)                  │ HTTPS
                                 ▼                                        │ + Attestation Header
                    ┌──────────────────────────┐                          │
                    │     ExamGuard Client     │──────────────────────────┘
                    │ Rust + CEF + ONNX        │
                    │ + Lockdown adapters      │
                    └──────────────────────────┘
```

Empat jalur komunikasi:

1. **Client ↔ Server**: HTTPS untuk sinkronisasi authoritative dan upload event; WSS untuk push command.
2. **Client ↔ Exam Website**: traffic browser biasa, ditambah Attestation Header dan JS Bridge.
3. **Exam Website ↔ Server**: Integration API (server-to-server) dan webhook.
4. **Admin Web / Candidate Portal ↔ Server**: HTTPS; Candidate Portal menerbitkan launch link untuk meluncurkan client.

---

# 4. System Components

```text
ExamGuard Platform
│
├── ExamGuard Client
│   ├── Secure Browser (CEF)
│   ├── Config Verifier
│   ├── Preflight Checker
│   ├── Lockdown Engine (+ Windows/macOS/Linux adapters)
│   ├── Device Monitor (process, display, remote access, VM)
│   ├── Camera Engine
│   ├── Audio Engine
│   ├── ONNX Proctor Engine
│   ├── Attempt State Engine
│   ├── Control Channel (WSS) + Sync Client (HTTPS)
│   ├── Device Session Keystore
│   ├── Local Event Queue (encrypted)
│   └── Recovery Engine
│
├── ExamGuard Server
│   ├── Authentication (staff & candidate accounts)
│   ├── Organization & Tenancy (RLS)
│   ├── Candidate Registration & Enrollment
│   ├── Identity Check
│   ├── Exam Management
│   ├── Attempt / Session Management (state machine)
│   ├── Timing Service (deadline, scheduler)
│   ├── Policy Management
│   ├── Signing Service (commands, config, attestation, completion)
│   ├── Event Ingestion
│   ├── Incident Management
│   ├── WebSocket Gateway
│   ├── Integration API + Webhook Dispatcher
│   └── Audit Logging (append-only, hash-chained)
│
├── ExamGuard Admin Web
│   ├── Dashboard
│   ├── Exams (list, create, edit, publish, finalize)
│   ├── Registrations
│   ├── Check-in Queue
│   ├── Live Monitoring
│   ├── Candidate Detail
│   ├── Incidents
│   ├── Interrupted Sessions & Re-entry Requests
│   ├── Audit Log
│   ├── Organization Settings
│   └── Platform Settings
│
├── ExamGuard Candidate Portal
│   ├── Account & Profile
│   ├── Public Test Catalog & Registration
│   ├── Invitations
│   ├── My Exams (system check, launch)
│   └── History & Results
│
└── Reference Exam Website
    ├── Question Bank (per exam)
    ├── Exam Delivery (navigation, autosave)
    ├── Attestation Verification
    ├── Submission & Completion
    └── Scoring (auto MC, manual essay)
```

---

# 5. ExamGuard Client Technology

**Bahasa utama: Rust.** Tidak menggunakan Python atau C# sebagai runtime dependency pada komputer peserta.

**Browser: Chromium Embedded Framework (CEF)**, untuk konsistensi rendering, JavaScript, WebRTC, kompatibilitas camera/microphone web, dan lingkungan browser yang terkendali.

**AI Inference:** ONNX model dijalankan langsung dari Rust melalui ONNX Runtime. Model di-bundle bersama installer dan diverifikasi hash-nya saat startup.

| Fungsi | Model awal | Lisensi (perlu diverifikasi legal) |
|---|---|---|
| Person Detection | OpenCV Zoo YOLOX | Apache-2.0 |
| Face Detection | OpenCV Zoo YuNet | MIT |
| Voice Activity Detection | Silero VAD | MIT |

---

# 6. ExamGuard Server Technology

Server tidak wajib menggunakan Rust. Reference implementation awal:

| Lapisan | Teknologi |
|---|---|
| Backend | Python FastAPI |
| Database | PostgreSQL |
| Isolasi tenant | PostgreSQL Row-Level Security (§8.2) |
| Realtime | WebSocket |
| Pub/Sub & cache | Redis (wajib bila > 1 instance server) |
| Key storage | File terenkripsi (MVP); KMS/HSM (produksi) |

Institusi lain dapat membuat compatible server (Java, Go, Rust, .NET, PHP, Node.js) selama mengikuti **ExamGuard Protocol** (§17) dan lulus conformance test suite yang akan disediakan bersama reference server.

---

# 7. User Roles & Permissions

Semua role staf (selain Platform Admin) berlaku **per organisasi**. Satu pengguna dapat memiliki role berbeda di organisasi berbeda.

| Aksi | Candidate | Invigilator | Exam Admin | Org Admin | Platform Admin |
|---|:-:|:-:|:-:|:-:|:-:|
| Membuat akun, mendaftar sesi publik, menerima undangan | ✓ | | | | |
| Mengikuti ujian, melihat hasil (bila diizinkan) | ✓ | | | | |
| Melihat peserta & event (ujian yang ditugaskan) | | ✓ | ✓ | ✓ | |
| Menyetujui / menolak identity check | | ✓ | ✓ | | |
| Kirim warning, pause / resume, tambah waktu individu | | ✓ | ✓ | | |
| Approve / reject re-entry, force submit, terminate individu | | ✓ | ✓ | | |
| Review incident, membuat emergency unlock response | | ✓ | ✓ | | |
| Terminate massal (elevated confirmation), extend seluruh ujian | | | ✓ | | |
| Create / edit / publish exam, kelola pendaftar & undangan | | | ✓ | | |
| Reopen, reinstate, finalize | | | ✓ | | |
| Kelola pengguna & role organisasi | | | | ✓ | |
| Pengaturan organisasi (retensi, policy template, re-entry, integrasi) | | | | ✓ | |
| Kelola organisasi & izin publikasi tes publik | | | | | ✓ |
| Signing key, versi client, default & batas global | | | | | ✓ |
| Unfinalize (override khusus) | | | | ✓ (persetujuan) | ✓ |

Catatan:

- Invigilator hanya dapat mengakses ujian (dan opsional kelompok peserta) yang ditugaskan kepadanya.
- Setiap aksi yang mengubah attempt wajib menyertakan **reason** dan tercatat di audit log.
- Akses Platform Admin ke data milik organisasi tercatat di audit log organisasi tersebut.

---

# 8. Organizations, Candidates & Domain Model

## 8.1 Model organisasi

```text
Platform (operator)
 ├── Organization A (instansi)          → ujian PRIVATE untuk peserta undangan
 ├── Organization B (instansi)          → ujian PRIVATE
 └── Organization P (program publik)    → ujian PUBLIC, pendaftaran mandiri
```

- Setiap ujian dimiliki tepat satu organisasi.
- Organisasi dengan flag `can_publish_public` (diberikan Platform Admin) dapat menerbitkan ujian `PUBLIC`. Tes perorangan umumnya diselenggarakan oleh organisasi milik platform operator sendiri.
- Satu akun peserta dapat mengikuti ujian publik maupun ujian dari beberapa instansi.

## 8.2 Isolasi data

- Semua tabel milik organisasi memiliki `org_id`.
- Isolasi ditegakkan dua lapis: filter di repository layer **dan** PostgreSQL Row-Level Security dengan konteks organisasi per request.
- Query lintas organisasi dilarang, kecuali untuk fungsi platform yang tercatat di audit log.
- Automated test wajib membuktikan pengguna organisasi A tidak dapat membaca atau mengubah data organisasi B.
- Organisasi hanya melihat data peserta yang terdaftar di ujian miliknya, bukan seluruh profil atau riwayat peserta di organisasi lain.

## 8.3 Visibility ujian

| Visibility | Cara peserta masuk | Parameter tambahan |
|---|---|---|
| `PRIVATE` | Undangan email, import CSV, atau Integration API | — |
| `PUBLIC` | Pendaftaran mandiri dari katalog Candidate Portal | `registration_open`, `registration_close`, `capacity`, `access_code` opsional (voucher), deskripsi & syarat peserta |

Pengurangan kuota saat pendaftaran dilakukan secara atomik sehingga tidak terjadi overbooking.

## 8.4 Akun peserta & enrollment

- Akun global dengan email terverifikasi. Profil minimal: nama lengkap sesuai identitas dan email; data tambahan (mis. tanggal lahir) hanya diminta bila ujian mensyaratkannya.
- **Enrollment** menghubungkan peserta dengan satu ujian dan mencatat sumbernya (`SELF_REGISTERED`, `INVITED`, `IMPORTED`, `API`).
- Attempt `NOT_STARTED` dibuat saat enrollment terkonfirmasi.
- Pada ujian publik, peserta dapat membatalkan atau pindah sesi sampai `registration_close`. Pembatalan menghapus attempt yang belum dimulai dan tercatat di audit log.
- Alur undangan instansi: email undangan → buat akun baru atau klaim akun yang sudah ada → ujian muncul di Candidate Portal.
- Undangan hanya dapat dibuat saat exam `DRAFT` atau `READY`, dan hanya dapat diterima saat exam `READY`. Sejak exam `RUNNING`, undangan, import, maupun pendaftaran via Integration API ditolak untuk semua visibility (Q13).

## 8.5 Pengaturan berjenjang

Beberapa pengaturan berlaku berjenjang: **default platform → organisasi → ujian**, yang paling spesifik berlaku. Platform Admin dapat menetapkan batas minimum dan maksimum.

Berlaku untuk: retensi data (§24.1), re-entry policy (§20.4), identity check (§12.5), dan policy template (§13.4).

## 8.6 Entitas

```text
Organization 1───* Membership *───1 User (staf)
Organization 1───* Exam 1───* Enrollment *───1 Candidate
                          │         │
                          │         └───1 Attempt 1───* DeviceSession
                          │                   ├───* Event ───? Incident
                          │                   ├───* Command
                          │                   └───* StateTransition
                          ├───1 SecurityPolicy (snapshot)
                          └───* InvigilatorAssignment
AuditLogEntry (append-only, hash-chained, ber-org_id)
```

| Entitas | Atribut kunci |
|---|---|
| Organization | `org_id`, `name`, `can_publish_public`, `settings` (retensi, re-entry, dll.) |
| User / Membership | `user_id`, `email`; `membership(org_id, role)` |
| Candidate | `candidate_id`, `email` (terverifikasi), `full_name`, `profile` minimal |
| Exam | `exam_id`, `org_id`, `code`, `name`, `visibility`, `exam_url`, `allowed_origins[]`, `window_start`, `latest_start`, `window_end`, `duration_minutes?`, `late_start_policy`, `checkin_open`, `identity_check`, `registration_open?`, `registration_close?`, `capacity?`, `integration_level`, `policy_snapshot`, `min_client_version`, `status` |
| Enrollment | `enrollment_id`, `exam_id`, `candidate_id`, `source`, `status` (CONFIRMED / CANCELLED), `time_accommodation_minutes`, `external_ref?` |
| Attempt | `attempt_id`, `enrollment_id`, `status`, `state_version`, `started_at?`, `deadline?`, `paused_at?`, `timer_mode_during_pause?`, `reopen_count`, `reinstate_count`, `termination_reason_category?` |
| DeviceSession | `device_session_id`, `attempt_id`, `public_key`, `client_version`, `os_info`, `created_at`, `revoked_at?`, `connection_status`, `last_heartbeat_at` |
| Event | `event_id`, `device_session_id`, `seq`, `type`, `severity`, `started_at`, `ended_at?`, `confidence?`, `metadata`, `evidence_ref?` |
| Incident | `incident_id`, `event_id`, `review_status` (OPEN / REVIEWED / DISMISSED / ESCALATED), `reviewer`, `note` |
| Command | `command_id`, `attempt_id`, `type`, `payload`, `issued_by`, `issued_at`, `delivery_status` |

---

# 9. Exam State Model

Status level **ujian** (bukan peserta).

```text
DRAFT ──publish──► READY ──window_start──► RUNNING ──semua attempt final──► CLOSED ──finalize──► FINALIZED
  │                  │
  └──── cancel ──────┴──► CANCELLED
```

| State | Arti |
|---|---|
| `DRAFT` | Sedang disusun; belum terlihat oleh peserta. |
| `READY` | Dipublikasikan; peserta dapat menjalankan preflight, belum dapat mulai. |
| `RUNNING` | `window_start` telah lewat; attempt dapat dimulai hingga `latest_start`. |
| `CLOSED` | Semua attempt berada di state final (SUBMITTED / EXPIRED / TERMINATED / NO_SHOW). Reopen/reinstate masih diizinkan. |
| `FINALIZED` | Terkunci. Semua attempt ikut FINALIZED. Hanya dapat dibuka dengan override Platform Admin + Org Admin. |
| `CANCELLED` | Dibatalkan sebelum berjalan. |

Jika attempt di-reopen atau di-reinstate saat exam `CLOSED`, exam kembali ke `RUNNING`.

Untuk ujian `PUBLIC`, registrasi hanya dapat berlangsung saat exam `READY` dan di dalam rentang `registration_open`–`registration_close` (§8.3). Untuk ujian `PRIVATE`, enrollment baru (undangan, import CSV, Integration API) hanya dapat dibuat sebelum exam `RUNNING` (§8.4). Ujian yang sudah memiliki pendaftar tidak dapat dikembalikan ke `DRAFT`; pembatalan (`CANCELLED`) wajib memberi notifikasi ke semua pendaftar.

---

# 10. Attempt State Model

## 10.1 Dua dimensi status

Setiap attempt memiliki dua dimensi yang **independen**:

- `attempt_status`: status lifecycle (tabel di bawah), authoritative di server.
- `connection_status`: `ONLINE` / `OFFLINE`, diturunkan dari heartbeat device session.

Dengan demikian peserta yang PAUSED dan kehilangan koneksi tetap `PAUSED` + `OFFLINE`, bukan berganti status.

## 10.2 Daftar state

| State | Final? | Arti |
|---|:-:|---|
| `NOT_STARTED` | | Terdaftar, belum mulai. |
| `ACTIVE` | | Sedang mengerjakan. |
| `PAUSED` | | Dibekukan oleh pengawas. Lockdown tetap aktif. |
| `INTERRUPTED` | | Client tidak terpantau saat ACTIVE: koneksi WSS tertutup, atau heartbeat hilang melewati `interruption_threshold` (default 30 detik). |
| `WAITING_FOR_INVIGILATOR` | | Client tersambung kembali tetapi re-entry membutuhkan persetujuan. |
| `REOPENED` | | Attempt yang sudah selesai dibuka kembali; menunggu peserta meluncurkan client. |
| `REINSTATED` | | Attempt TERMINATED dipulihkan; menunggu peserta meluncurkan client. |
| `SUBMITTED` | ✓ | Diselesaikan normal atau force submit. |
| `EXPIRED` | ✓ | Deadline terlewati. |
| `TERMINATED` | ✓ | Dihentikan paksa. |
| `NO_SHOW` | ✓ | Tidak mulai sampai `latest_start`. |
| `FINALIZED` | ✓ (permanen) | Dikunci saat exam difinalisasi. |

## 10.3 Tabel transisi

| Dari | Ke | Pemicu | Aktor | Catatan |
|---|---|---|---|---|
| NOT_STARTED | ACTIVE | Client selesai preflight + lockdown, identity check disetujui (bila diwajibkan), `now ∈ [window_start, latest_start]` | Candidate | `started_at` diset, deadline dihitung (§11) |
| NOT_STARTED | NO_SHOW | `now > latest_start` | System | |
| ACTIVE | PAUSED | `PAUSE_EXAM` | Invigilator | Memilih timer mode |
| PAUSED | ACTIVE | `RESUME_EXAM` | Invigilator | Deadline digeser jika `PAUSE_TIMER` |
| ACTIVE | INTERRUPTED | Koneksi WSS client tertutup, atau tidak ada heartbeat > `interruption_threshold` | System | Bersamaan dengan `OFFLINE` (§17.6) |
| INTERRUPTED | ACTIVE | Reconnect, gap < `reentry_approval_threshold`, device session sama, deadline belum lewat | System | Auto resume |
| INTERRUPTED | WAITING_FOR_INVIGILATOR | Reconnect, gap ≥ threshold **atau** device session berbeda | System | |
| ACTIVE | WAITING_FOR_INVIGILATOR | Device session baru didaftarkan saat device session lama masih aktif (§18) | System | Device baru berstatus menunggu persetujuan; device lama dicabut setelah disetujui |
| WAITING_FOR_INVIGILATOR | ACTIVE | `ALLOW_REENTRY` | Invigilator | |
| WAITING_FOR_INVIGILATOR | TERMINATED | `REJECT_REENTRY` | Invigilator | Reason `REENTRY_REJECTED`, kategori wajib (lihat di bawah) |
| ACTIVE | SUBMITTED | Completion via Integration API (§16.5) atau Manual Finish (Level 0) | Candidate / LMS | |
| ACTIVE, PAUSED, INTERRUPTED, WAITING_FOR_INVIGILATOR | SUBMITTED | `FORCE_SUBMIT` | Invigilator | Jawaban yang sudah tersimpan di LMS dipakai |
| ACTIVE, PAUSED, INTERRUPTED, WAITING_FOR_INVIGILATOR, REOPENED, REINSTATED | EXPIRED | `now ≥ deadline` | System | Saat PAUSED + `PAUSE_TIMER`, deadline tidak berjalan |
| ACTIVE, PAUSED, INTERRUPTED, WAITING_FOR_INVIGILATOR | TERMINATED | `FORCE_TERMINATE` | Invigilator | |
| SUBMITTED, EXPIRED | REOPENED | Reopen dengan deadline baru | Exam Admin | `reopen_count++` |
| TERMINATED | REINSTATED | Reinstate dengan deadline baru | Exam Admin | `reinstate_count++` |
| REOPENED, REINSTATED | ACTIVE | Client meluncur dan registrasi device session | Candidate | Lockdown diaktifkan kembali |
| SUBMITTED, EXPIRED, TERMINATED, NO_SHOW | FINALIZED | Exam difinalisasi | Exam Admin | |
| FINALIZED | status final sebelumnya | Unfinalize override | Platform Admin + Org Admin | Bukan MVP |

Aturan umum:

- Setiap transisi menaikkan `state_version` (monoton per attempt) dan menulis `StateTransition` + audit log. Perubahan deadline tanpa perubahan status (add time, extend, resume) juga menaikkan `state_version` satu kali, agar client dapat mengurutkan `UPDATE_DEADLINE` terhadap command lain (§17.3).
- Transisi yang tidak tercantum ditolak dengan error `INVALID_TRANSITION`.
- Setiap transisi ke `TERMINATED` wajib menyertakan `reason_category`: `TECHNICAL`, `ADMINISTRATIVE`, atau `DISCIPLINARY`. Dashboard, statistik, dan laporan memisahkan ketiganya agar peserta yang terputus karena masalah teknis tidak tercampur dengan kasus pelanggaran. Label tombol di UI dibuat eksplisit, misalnya "Tolak & akhiri attempt".
- Server memvalidasi transisi secara atomik (row lock / optimistic concurrency pada `state_version`), sehingga dua pengawas yang bertindak bersamaan tidak menghasilkan state ganda.

---

# 11. Exam Timing

Server adalah satu-satunya referensi waktu. Client tidak menentukan deadline berdasarkan timer lokal.

## 11.1 Parameter ujian

| Parameter | Arti |
|---|---|
| `window_start` | Waktu paling awal attempt dapat dimulai. |
| `latest_start` | Waktu paling akhir attempt dapat dimulai (default = `window_start` + 30 menit, dapat diatur). |
| `window_end` | Batas akhir jendela ujian. |
| `duration_minutes` | Opsional. Durasi per peserta. |
| `late_start_policy` | `FIXED_END` (default) atau `FULL_DURATION`. |
| `time_accommodation_minutes` | Per enrollment, yaitu per peserta pada ujian tertentu (mis. akomodasi disabilitas). |

## 11.2 Rumus deadline awal

```text
base = started_at + duration_minutes + time_accommodation_minutes     (jika duration diset)

FIXED_END      : deadline = min(base, window_end + time_accommodation_minutes)
FULL_DURATION  : deadline = base
Tanpa duration : deadline = window_end + time_accommodation_minutes
```

Contoh (`FIXED_END`, window 09:00–10:30, durasi 90 menit): peserta yang mulai 09:20 mendapat deadline 10:30, bukan 10:50.

## 11.3 Perubahan deadline

- Semua perubahan disimpan sebagai **deadline absolut** dan dikirim via `UPDATE_DEADLINE` (idempoten).
- Tambahan waktu individu dan extend seluruh ujian **boleh melewati** `window_end`.
- Extend seluruh ujian: server menghitung deadline baru per attempt non-final (`deadline_lama + X`), lalu mengirim `UPDATE_DEADLINE` terpisah ke masing-masing.
- `time_accommodation_minutes` hanya ikut dalam rumus deadline awal (§11.2). Mengubah akomodasi setelah attempt dimulai **tidak** menggeser deadline secara otomatis. Tambahan waktu bagi attempt yang sedang berjalan diberikan melalui Add Time (§27.7) sehingga tercatat dengan aktor dan alasan. Deadline reopen/reinstate diinput eksplisit oleh Exam Admin (§27.7) dan tidak dihitung dari akomodasi (Q12).
- Extend seluruh ujian dicatat sebagai `extension_minutes` pada ujian dan ditambahkan pada rumus deadline awal, sehingga peserta yang mulai setelah extend (masih sebelum `latest_start`) mendapat tambahan waktu yang sama (Q16).

## 11.4 Pause dan timer

| Mode | Perilaku |
|---|---|
| `KEEP_RUNNING` (default) | Deadline tidak berubah. Attempt dapat EXPIRED saat PAUSED. |
| `PAUSE_TIMER` | Server mencatat `paused_at`. Saat resume: `deadline += resumed_at − paused_at`, lalu mengirim `UPDATE_DEADLINE`. |

Client tidak menghitung durasi pause.

## 11.5 Crash dan waktu yang hilang

```text
09:35 komputer crash
09:45 komputer restart
```

Deadline tetap 10:30. Peserta kehilangan 10 menit, kecuali pengawas memberikan tambahan waktu.

## 11.6 Sinkronisasi jam client

- Setiap response HTTPS dan heartbeat ack menyertakan `server_time`.
- Client menghitung `offset = server_time − local_time` dan menampilkan sisa waktu memakai **monotonic clock + offset**, sehingga mengubah jam sistem tidak berpengaruh.
- Validasi `expires_at` pada command dan token menggunakan waktu server yang diestimasi, dengan toleransi ±30 detik.
- Jika client offline dan estimasi waktu melewati deadline, client membekukan tampilan ujian dengan pesan "Waktu habis — menunggu sinkronisasi dengan server". Lockdown **tidak** dilepas sampai server mengonfirmasi, emergency unlock dilakukan, atau safety valve berlaku (§22).

---

# 12. Candidate Launch, Login & Preflight

## 12.1 Cara meluncurkan ujian

MVP mendukung dua cara:

1. **Launch link**: `examguard://launch?t=<launch_token>` diberikan oleh Candidate Portal (§28) atau website ujian.
2. **Kode manual**: peserta memasukkan `exam_code` + `access_code` pribadi di layar awal client.

`launch_token` / `access_code` bersifat single-use, terikat ke satu attempt, dan berlaku singkat (default 15 menit untuk launch token). Menukar launch token dengan Signed Exam Config boleh diulang (aman bila koneksi putus); token baru dianggap terpakai saat registrasi device session.

## 12.2 Alur launch

```text
Client start
   ↓
Tukar launch token → dapatkan Signed Exam Config
   ↓
Verifikasi signature config (§19)
   ↓
Consent screen (§24)
   ↓
Preflight checks
   ↓
Generate device session key pair (§18)
   ↓
Registrasi device session (kirim public key + preflight report)
   ↓
Aktifkan lockdown
   ↓
Identity check (bila diwajibkan, §12.5) → menunggu window_start bila check-in lebih awal
   ↓
Server: NOT_STARTED/REOPENED/REINSTATED → ACTIVE
   ↓
Buka exam_url
```

## 12.3 Signed Exam Config

Berisi: `exam_id`, `attempt_id`, `exam_url`, `allowed_origins`, `policy`, `min_client_version`, `server_endpoints`, `integration_level`, `issued_at`, `expires_at`, `config_hash`. Ditandatangani server. Client menolak config yang tidak valid atau kedaluwarsa.

## 12.4 Preflight checks

| Check | Kondisi gagal | Default |
|---|---|---|
| Versi client | `< min_client_version` | Blocking |
| OS & tingkat lockdown | Tingkat jaminan di bawah `min_lockdown_level` policy (§13) | Blocking |
| Izin OS (macOS Accessibility / Screen Recording, dll.) | Belum diberikan | Blocking |
| Monitor | Lebih dari satu display aktif | Blocking bila policy single-monitor |
| Kamera | Tidak ada / tidak menghasilkan frame / wajah tidak terdeteksi saat uji | Blocking bila kamera wajib |
| Mikrofon | Tidak ada / tidak ada sinyal | Blocking bila mic wajib |
| Proses terlarang | Sedang berjalan | Blocking; client menawarkan untuk menutupnya |
| Remote access | Sesi RDP / tool remote desktop aktif | Blocking |
| Virtual machine | Terdeteksi | Warning (MVP; lihat §13.3) |
| Konektivitas | Server atau `exam_url` tidak terjangkau | Blocking |
| Penyimpanan lokal | Ruang untuk log & queue tidak cukup | Warning |

Hasil preflight dikirim ke server sebagai `preflight_report` dan terlihat di Candidate Detail.

Client juga menyediakan **practice mode** (System Check dari Candidate Portal) yang menjalankan preflight dan uji lockdown singkat tanpa ujian, supaya masalah perangkat diketahui sebelum hari ujian.

## 12.5 Identity Check

| Setting | Arti | Default |
|---|---|---|
| `NONE` | Tanpa pemeriksaan identitas | Ujian `PRIVATE` |
| `MANUAL` (MVP) | Pengawas mencocokkan selfie dan foto kartu identitas | Ujian `PUBLIC` |
| `AUTOMATED` | Pencocokan wajah otomatis | Roadmap, perlu review hukum |

Alur `MANUAL`:

1. Setelah lockdown aktif, client mengambil selfie dan foto kartu identitas (KTP, paspor, atau kartu pegawai) yang ditunjukkan ke kamera.
2. Foto diunggah terenkripsi dan masuk ke **Check-in Queue** di Admin Web.
3. Pengawas mencocokkan foto dengan nama terdaftar, lalu menyetujui atau menolak dengan alasan. Peserta yang ditolak dapat mengulang maksimal 3 kali sebelum harus ditangani pengawas secara langsung.
4. Check-in dibuka mulai `checkin_open` (default 30 menit sebelum `window_start`). Peserta yang sudah disetujui menunggu dalam lockdown dengan layar "Ujian dimulai pukul 09:00".

Waktu antre check-in tidak memotong durasi ujian karena attempt baru `ACTIVE` setelah disetujui. Dengan `FIXED_END`, kapasitas pengawas perlu direncanakan agar antrean selesai sebelum `window_start`.

Foto disimpan terenkripsi at rest (AES-256-GCM) dan hanya didekripsi saat dilihat pengawas yang ditugaskan; setiap akses foto tercatat di audit log.

Privasi: nomor identitas tidak diketik atau disimpan sebagai data terstruktur pada MVP, dan foto hanya dipakai untuk verifikasi ujian tersebut (retensi di §24.1). Pencocokan wajah otomatis mengolah data biometrik, yang termasuk data pribadi spesifik menurut UU PDP, sehingga baru dikerjakan setelah ada review hukum.

---

# 13. Client Lockdown

## 13.1 Kemampuan lockdown

Ketika attempt aktif: full screen, tidak dapat minimize, normal close disabled, application switching dibatasi, OS shortcut dibatasi sesuai kemampuan platform, proses terlarang dibatasi, URL browsing dibatasi ke `allowed_origins`, developer tools disabled, external navigation dibatasi, multiple monitor dapat dibatasi, clipboard dapat dibatasi, screen capture dapat dibatasi.

Lockdown diimplementasikan melalui OS-specific platform adapter dengan satu antarmuka Rust yang sama (trait `LockdownAdapter`).

## 13.2 Tingkat jaminan per OS

Legenda: **E** = Enforced, **B** = Best-effort, **D** = Detect-only (tidak bisa dicegah, tetapi dicatat sebagai event), **—** = tidak didukung.

| Kemampuan | Windows 10/11 | macOS 13+ | Linux X11 | Linux Wayland |
|---|:-:|:-:|:-:|:-:|
| Fullscreen & cegah minimize | E | E | B | B |
| Blok Alt+Tab / Cmd+Tab | E | E | B | D |
| Blok tombol Win / Mission Control | E | E | B | D |
| Ctrl+Alt+Del / secure attention | D | — | — | — |
| Force Quit (Cmd+Opt+Esc) | — | E | — | — |
| Deteksi kehilangan fokus | E | E | E | B |
| Blok screen capture pihak ketiga | B | B | — | — |
| Deteksi monitor tambahan | E | E | E | B |
| Process monitoring | E | E | E | E |
| Clipboard dibatasi (dalam CEF) | E | E | E | E |
| Clipboard dibatasi (sistem) | B | B | B | — |

Status tabel ini adalah **target awal** dan wajib divalidasi di Phase 6.

**Linux (keputusan v0.3).** MVP mendukung Linux X11. Dukungan Wayland adalah **requirement wajib di roadmap**, bukan opsional, karena banyak distro sudah memakai Wayland sebagai default. Konsekuensi desain yang berlaku sejak MVP:

- Build CEF memakai backend Ozone yang mendukung X11 **dan** Wayland, sehingga jalur Wayland tidak tertutup.
- Trait `LockdownAdapter` memisahkan adapter `linux-x11` dan `linux-wayland`.
- Pada MVP, client di sesi Wayland tetap berjalan pada level `RELAXED` (fullscreen, process monitoring, deteksi fokus best-effort). Jika ujian mensyaratkan level lebih tinggi, preflight menjelaskan cara beralih ke sesi Xorg di layar login.

Keterbatasan Wayland berasal dari desain protokolnya: aplikasi memang tidak diizinkan menahan shortcut global atau melihat jendela aplikasi lain. Karena itu roadmap Wayland menempuh jalur berikut:

1. Protokol **keyboard-shortcuts-inhibit** (didukung GNOME dan KDE; GNOME menampilkan dialog izin) untuk menahan shortcut saat fullscreen → target `STANDARD`.
2. **Sesi kiosk khusus** yang dipilih di layar login dan hanya menjalankan ExamGuard → target `STRICT`, berlaku lintas distro.
3. Integrasi spesifik desktop environment (ekstensi GNOME Shell, script KWin) dievaluasi bila dua jalur di atas tidak cukup.

Policy memiliki `min_lockdown_level` (`STRICT` / `STANDARD` / `RELAXED`). Kombinasi OS yang tidak memenuhi level tersebut gagal di preflight.

## 13.3 Deteksi remote access, VM, dan screen mirroring (MVP)

| Deteksi | Metode awal | Event |
|---|---|---|
| Sesi remote OS | Windows `SM_REMOTESESSION`; macOS screen sharing aktif | `REMOTE_ACCESS_DETECTED` |
| Tool remote desktop | Daftar proses/service yang dikenal (TeamViewer, AnyDesk, RustDesk, Chrome Remote Desktop, VNC server, dll.), dapat diperbarui lewat policy | `REMOTE_ACCESS_DETECTED` |
| Virtual machine | CPUID hypervisor bit, vendor string perangkat, driver VM | `VIRTUAL_MACHINE_DETECTED` |
| Display tambahan / mirroring | Jumlah display, perubahan konfigurasi display saat ujian | `ADDITIONAL_MONITOR` |

Semua deteksi ini heuristik dan dapat menghasilkan false positive; hasilnya tetap berupa event yang ditinjau manusia.

**Virtual machine (keputusan v0.3).** Pada MVP deteksi VM bersifat **warn-only** di semua template. Alasannya: di Windows yang mengaktifkan Hyper-V, WSL2, atau Virtualization-Based Security, CPUID hypervisor bit juga menyala di mesin host biasa, sehingga sinyal itu saja tidak boleh dipakai untuk memblokir.

Roadmap deteksi VM:

- Deteksi multi-sinyal yang tidak bergantung pada hypervisor bit: vendor SMBIOS/firmware, perangkat dan driver virtual, prefix MAC address adapter virtual, dan anomali timing.
- Mengukur tingkat false positive pada perangkat nyata sebelum opsi blokir diaktifkan di template Strict.
- Opsi policy **Block WSL** (deteksi `wsl.exe`, `wslhost.exe`, `vmmemWSL`) yang dapat diaktifkan per template; default nonaktif untuk Programming Exam.

## 13.4 Allowed Application Policy

Default yang diizinkan: ExamGuard dan system service yang dibutuhkan. Opsional sesuai jenis ujian: kalkulator, PDF viewer, IDE, spreadsheet.

Policy template bawaan: **Strict Exam**, **Programming Exam**, **Open Book Exam**, **Essay Exam**. Saat exam dibuat, template disalin menjadi `policy_snapshot` sehingga perubahan template di kemudian hari tidak mengubah ujian yang sedang berjalan.

Privasi: client hanya melaporkan proses yang **cocok** dengan daftar terlarang, bukan seluruh daftar proses peserta.

---

# 14. Proctoring

## 14.1 Prinsip

- Semua inferensi berjalan **lokal** di perangkat peserta.
- MVP tidak melakukan streaming atau perekaman video/audio berkelanjutan. Yang dikirim adalah event metadata dan snapshot opsional.
- AI hanya menghasilkan event. AI tidak pernah menyatakan `CHEATING_CONFIRMED`.

## 14.2 Camera

| Aturan (default, dapat diatur di policy) | Event |
|---|---|
| `face_count == 0` selama > 5 detik | `FACE_MISSING` |
| `face_count > 1` selama > 3 detik | `MULTIPLE_FACES` |
| `person_count > 1` selama > 3 detik | `MULTIPLE_PERSON` |
| Kamera tidak ditemukan saat ujian berjalan | `CAMERA_UNAVAILABLE` |
| Kamera terputus / tidak ada frame > 3 detik | `CAMERA_DISCONNECTED` |

Parameter inferensi default: 2 fps (dapat diatur 1–5 fps), resolusi input sesuai model (YuNet 320×320, YOLOX 416×416 atau 640×640).

## 14.3 Audio

| Aturan | Event |
|---|---|
| Probabilitas speech Silero VAD > 0.5 selama > 5 detik | `VOICE_ACTIVITY` |
| Mikrofon tidak ditemukan | `MICROPHONE_UNAVAILABLE` |
| Mikrofon terputus | `MICROPHONE_DISCONNECTED` |

Audio diproses pada 16 kHz dan tidak disimpan pada MVP.

## 14.4 Lifecycle event berdurasi

Event proctoring memiliki awal dan akhir:

1. Kondisi terpenuhi melewati ambang durasi → event **dibuka** dan langsung dikirim (`started_at`).
2. Kondisi berhenti (dengan hysteresis 1 detik) → event **ditutup** (`ended_at`, `duration`, `max_confidence`).

Ini memungkinkan pengawas melihat event yang sedang berlangsung sekaligus durasi finalnya.

## 14.5 Evidence snapshot (opsional per policy)

- Diambil saat event dibuka, diperkecil (mis. 640 px sisi terpanjang), JPEG.
- Diunggah via HTTPS, disimpan terenkripsi di server.
- Akses dan retensi mengikuti §24.

---

# 15. Event Dictionary

Severity default dapat di-override per policy. Severity hanya untuk sorting dan prioritas review; **tidak** berarti peserta bersalah.

| Kategori | Event | Severity default | Membuat incident? |
|---|---|:-:|:-:|
| Session | `EXAM_STARTED`, `EXAM_SUBMITTED`, `EXAM_EXPIRED`, `EXAM_PAUSED`, `EXAM_RESUMED`, `DEADLINE_UPDATED` | Info | |
| Session | `EXAM_TERMINATED` | Info | |
| Session | `REENTRY_REQUESTED`, `REENTRY_APPROVED`, `REENTRY_REJECTED` | Info | |
| Session | `CLIENT_CRASH_RECOVERED` | Low | |
| Session | `UNMONITORED_INTERRUPTION` | Medium | ✓ |
| Session | `EMERGENCY_UNLOCK_USED` | High | ✓ |
| Session | `OFFLINE_AUTO_RELEASE` | Medium | ✓ |
| Session | `IDENTITY_CHECK_SUBMITTED`, `IDENTITY_CHECK_APPROVED` | Info | |
| Session | `IDENTITY_CHECK_REJECTED` | Low | |
| Proctoring | `FACE_MISSING`, `VOICE_ACTIVITY` | Medium | ✓ |
| Proctoring | `MULTIPLE_FACES`, `MULTIPLE_PERSON` | High | ✓ |
| Device | `CAMERA_UNAVAILABLE`, `CAMERA_DISCONNECTED` | High (bila kamera wajib) | ✓ |
| Device | `MICROPHONE_UNAVAILABLE`, `MICROPHONE_DISCONNECTED` | Medium | ✓ |
| Security | `PROHIBITED_APP` | High | ✓ |
| Security | `REMOTE_ACCESS_DETECTED`, `VIRTUAL_MACHINE_DETECTED` | High | ✓ |
| Security | `ADDITIONAL_MONITOR` | High | ✓ |
| Security | `FOCUS_LOST` | Medium | ✓ |
| Security | `SCREEN_CAPTURE_ATTEMPT` | Medium | ✓ |
| Security | `NAVIGATION_BLOCKED`, `CLIPBOARD_BLOCKED` | Low | |
| Security | `TAMPER_DETECTED`, `CLIENT_INTEGRITY_FAILED` | High | ✓ |

Setiap event memiliki skema dasar:

```json
{
  "event_id": "uuid",
  "device_session_id": "uuid",
  "seq": 128,
  "type": "MULTIPLE_PERSON",
  "phase": "OPEN | CLOSE | INSTANT",
  "started_at": "2026-09-23T10:22:09.120+07:00",
  "ended_at": null,
  "confidence": 0.94,
  "metadata": {},
  "evidence_ref": null
}
```

---

# 16. Exam Website Integration

## 16.1 Level integrasi

| Level | Nama | Yang dibutuhkan dari LMS | Jaminan |
|---|---|---|---|
| 0 | Standalone | Tidak ada | Lockdown & proctoring berjalan. Peserta menyelesaikan via tombol **Selesai Ujian** di toolbar ExamGuard. LMS tidak tahu apakah peserta memakai ExamGuard. |
| 1 | Attestation | Memverifikasi Attestation Header | LMS dapat menolak akses dari browser selain ExamGuard. |
| 2 | Full | Attestation + Integration API + webhook | Completion token, LMS mematuhi status attempt (pause/terminate/expire), sinkron timer. |

MVP: Level 0 dan Level 2. Level 1 otomatis tersedia sebagai bagian dari Level 2.

Pada v0.3, website ujian yang dipakai adalah **Reference Exam Website** (§29), dibangun dalam proyek yang sama. Walaupun dikerjakan satu tim, Reference Exam Website **tetap** hanya berkomunikasi lewat Integration API dan Attestation Header, dan tidak mengakses database ExamGuard secara langsung. Dengan begitu, sistem web ujian dari tim lain nanti dapat menggantikannya tanpa perubahan pada client maupun server.

## 16.2 Attestation Header

Setiap request dari ExamGuard ke origin di `allowed_origins` menyertakan:

```text
X-ExamGuard-Attestation: <token>
```

Token adalah JWT (EdDSA/Ed25519) yang diterbitkan **ExamGuard Server** (bukan dibuat client sendiri), berlaku 5 menit, diperbarui otomatis oleh client, dan berisi:

```json
{
  "iss": "https://examguard.example.edu",
  "aud": "https://exam.example.edu",
  "exam_id": "…",
  "attempt_id": "…",
  "candidate_ref": "external-id-di-LMS",
  "device_session_id": "…",
  "attempt_status": "ACTIVE",
  "config_hash": "sha256:…",
  "iat": 1790000000,
  "exp": 1790000300
}
```

LMS memverifikasi dengan public key dari endpoint key set (§19). Keterbatasan yang diketahui: client yang dimodifikasi dapat mengekstrak token yang masih berlaku; mitigasinya adalah masa berlaku singkat, keterikatan ke device session, dan deteksi integritas client (Phase 8).

## 16.3 JavaScript Bridge

`window.examguard` **hanya** diinjeksikan ke frame yang origin-nya ada di `allowed_origins`.

```javascript
await window.examguard.getVersion()       // "0.2.0"
await window.examguard.getSessionInfo()   // { exam_id, attempt_id, status, deadline, server_time }
await window.examguard.complete(token)    // { ok: true } atau error
window.examguard.onStateChange(cb)        // cb({ status, deadline, state_version })
```

`getSessionInfo()` tidak mengembalikan data pribadi peserta selain yang sudah diketahui LMS. Website tidak mempunyai akses arbitrary ke sistem operasi.

## 16.4 Integration API (LMS → Server)

Autentikasi: client credentials per integrasi (API key + secret). Setiap integrasi terikat ke satu organisasi dan dikelola Org Admin.

| Endpoint | Fungsi |
|---|---|
| `POST /integration/v1/exams` | Membuat ujian dari LMS (opsional; alternatif dari Admin Web) |
| `POST /integration/v1/exams/{exam_id}/candidates` | Mendaftarkan peserta, mengembalikan launch link |
| `GET /integration/v1/attempts/{attempt_id}` | Status, deadline, `state_version` |
| `POST /integration/v1/attempts/{attempt_id}/completion` | Melaporkan submit; mengembalikan completion token |
| `POST /integration/v1/attempts/{attempt_id}/result` | Mengirim hasil/skor agar dapat ditampilkan di Candidate Portal (opsional, sesuai setting `show_result`) |

**LMS wajib menolak penyimpanan jawaban** jika status attempt bukan `ACTIVE` (dapat dicek dari attestation token atau API). Ini yang membuat pause/terminate/expire benar-benar berlaku di sisi website.

Tambahan hasil implementasi:

- Autentikasi Integration API memakai HTTP Basic (`client_id` sebagai username, `secret` sebagai password). Secret 256-bit hanya ditampilkan sekali, dapat dirotasi dan dicabut oleh Org Admin.
- `POST /integration/v1/attempts/{attempt_id}/launch` menerbitkan launch link baru. LMS memintanya saat peserta menekan "Mulai", karena launch link berlaku 15 menit.
- Pendaftaran peserta idempoten per `candidate_ref`.
- Memanggil `/completion` lagi untuk attempt yang sudah `SUBMITTED` (mis. respons pertama hilang) mengembalikan completion token baru tanpa transisi kedua. Untuk status lain, server menjawab `409 ATTEMPT_NOT_ACTIVE` beserta statusnya.
- `/result` hanya diterima setelah attempt final.

## 16.5 Normal completion (Level 2)

```text
Peserta klik "Submit Exam" di website
   ↓
Website backend menyimpan jawaban final
   ↓
Website backend → POST /integration/v1/attempts/{id}/completion
   ↓
ExamGuard Server: ACTIVE → SUBMITTED, menandatangani completion_token
   ↓
Website frontend → window.examguard.complete(completion_token)
   ↓
Client memverifikasi: signature, kid, exam_id, attempt_id, device_session_id, expiry, nonce belum dipakai
   ↓
EXIT_AUTHORIZED → stop monitoring → flush event queue → release lockdown → tutup aplikasi
```

Jalur cadangan: server juga mem-push state `SUBMITTED` via WSS, sehingga client tetap keluar walaupun pemanggilan `complete()` gagal di frontend.

## 16.6 Webhook (Server → LMS)

Event: `attempt.started`, `attempt.paused`, `attempt.resumed`, `attempt.deadline_updated`, `attempt.submitted`, `attempt.expired`, `attempt.terminated`, `attempt.reopened`, `attempt.reinstated`. Ditandatangani (header `X-ExamGuard-Signature`), dikirim ulang dengan backoff, dan idempoten berdasarkan `event_id`.

- Signature: `X-ExamGuard-Signature: kid=<kid use=token>, ts=<unix_ms>, sig=base64url(Ed25519(ts + "." + body))`. LMS memverifikasinya dengan key set yang sama dengan attestation token, sehingga tidak ada shared secret yang perlu disimpan.
- Webhook dicatat dalam transaksi yang sama dengan transisinya (outbox), lalu dikirim scheduler. Retry: 30 detik, 1, 2, 5, 10, 30 menit, lalu tiap jam; setelah 10 percobaan gagal statusnya `FAILED` dan terlihat di riwayat pengiriman integrasi.
- MVP mengirim ke semua integrasi aktif organisasi yang memiliki `webhook_url` (Q17).

---

# 17. ExamGuard Protocol (Client ↔ Server)

## 17.1 Transport

| Kanal | Fungsi |
|---|---|
| HTTPS (TLS 1.2+) | Launch, registrasi device session, **full state sync**, upload event, upload evidence, refresh attestation |
| WSS | Push command dari server, heartbeat dan ACK dari client |

WSS hanya untuk push. Sumber kebenaran tetap full state sync via HTTPS.

## 17.2 Signed envelope

Semua command dan response state sync dibungkus dalam envelope bertanda tangan. Signature dihitung atas **byte persis** dari `body` (string JSON), sehingga tidak ada masalah kanonikalisasi JSON antarbahasa.

```json
{
  "kid": "srv-cmd-2026-01",
  "body": "{\"v\":1,\"command_id\":\"…\",\"type\":\"UPDATE_DEADLINE\",…}",
  "sig": "base64url(Ed25519(body_bytes))"
}
```

Isi `body` untuk command:

```json
{
  "v": 1,
  "command_id": "0f6c…",
  "type": "UPDATE_DEADLINE",
  "exam_id": "…",
  "attempt_id": "…",
  "candidate_id": "…",
  "device_session_id": "…",
  "state_version": 18,
  "issued_at": "2026-09-23T10:32:04+07:00",
  "expires_at": "2026-09-23T10:37:04+07:00",
  "nonce": "base64url(16 bytes)",
  "payload": { "deadline": "2026-09-23T10:45:00+07:00", "reason": "Technical compensation" }
}
```

## 17.3 Aturan validasi di client

Client **menolak** command jika salah satu gagal:

1. `kid` dikenal, belum dicabut, dan `use` = `command`.
2. Signature valid.
3. `exam_id`, `attempt_id`, `candidate_id`, `device_session_id` cocok dengan sesi saat ini.
4. `expires_at` > estimasi waktu server (§11.6).
5. `command_id` belum pernah diterapkan (daftar disimpan di recovery state untuk attempt ini).

Jika `state_version` ≤ versi terakhir yang diterapkan, command dianggap **STALE**: tidak diterapkan, tetapi tetap di-ACK. Ini menangani pesan yang datang tidak berurutan tanpa merusak state.

Batasan aturan STALE (Q20):

- Aturan STALE hanya berlaku untuk command yang **mengubah status**: `PAUSE_EXAM`, `RESUME_EXAM`, `UPDATE_DEADLINE`, `ALLOW_REENTRY`, `REJECT_REENTRY`, `FORCE_SUBMIT`, `FORCE_TERMINATE`. Setiap command ini diterbitkan bersama transisi yang menaikkan `state_version`.
- `WARNING` dan `EMERGENCY_UNLOCK` tidak mengubah status attempt, sehingga diterbitkan dengan `state_version` saat ini tanpa kenaikan. Keduanya **tidak pernah** dianggap STALE; tanpa batasan ini, peringatan dari pengawas tidak akan pernah tampil.
- Command dengan `command_id` yang sudah pernah diterapkan (aturan 5) tidak diterapkan ulang, tetapi tetap di-ACK `APPLIED`. Dengan begitu, ACK yang hilang di jaringan tidak membuat server menganggap command itu belum diterima.
- Urutan pemeriksaan di client: kid/use/signature → kecocokan ID sesi → duplikat → kedaluwarsa → STALE. Duplikat diperiksa sebelum kedaluwarsa agar pengiriman ulang yang terlambat tetap mendapat ACK `APPLIED`, bukan `REJECTED`.

## 17.4 Daftar command (client-facing)

| Command | Payload | Efek di client |
|---|---|---|
| `WARNING` | `message` | Menampilkan dialog pesan; lockdown tetap |
| `PAUSE_EXAM` | `reason`, `timer_mode` | Membekukan tampilan ujian, overlay "Ujian dijeda" |
| `RESUME_EXAM` | `deadline` | Melepas overlay, memperbarui deadline |
| `UPDATE_DEADLINE` | `deadline`, `reason` | Memperbarui deadline (absolut, idempoten) |
| `ALLOW_REENTRY` | `deadline` | Keluar dari layar menunggu, lanjut ujian |
| `REJECT_REENTRY` | `reason` | Menampilkan pesan, lalu alur keluar seperti terminate |
| `FORCE_SUBMIT` | `reason` | Menghentikan input, sinkronisasi final, keluar |
| `FORCE_TERMINATE` | `reason` | Menghentikan input, sinkronisasi final, keluar |
| `EMERGENCY_UNLOCK` | `reason` | Unlock yang diotorisasi server secara online (§22) |

`REOPEN` dan `REINSTATE` **bukan** command ke client: pada saat itu client sudah tertutup. Keduanya adalah transisi server-side; peserta meluncurkan client kembali dan melalui alur launch (§12).

Semua command ditandatangani, termasuk `WARNING`, agar satu jalur verifikasi berlaku untuk semuanya.

## 17.5 ACK dan pengiriman ulang

Client mengirim `COMMAND_ACK { command_id, result: APPLIED | STALE | REJECTED, reason? }` via WSS. Server menyimpan `delivery_status`. Command yang belum di-ACK tidak dikirim ulang secara buta; setelah reconnect, full state sync mengambil alih.

## 17.6 Heartbeat

- Client → server setiap **10 detik** via WSS, ditandatangani dengan device session key.
- Isi: `device_session_id`, `seq`, `last_state_version`, ringkasan kesehatan (`lockdown_ok`, `camera_ok`, `mic_ok`, `queue_depth`).
- Server membalas dengan `server_time`.
- **Satu waktu untuk Offline dan Terputus** (Q25). Pengawas tidak boleh melihat peserta aktif yang Offline tetapi belum Terputus, atau sebaliknya:
  - Koneksi WSS ditutup tanpa server yang menutupnya (client crash, aplikasi ditutup, laptop mati): server langsung mencatat `OFFLINE` dan, bila attempt `ACTIVE`, transisi `INTERRUPTED`. Socket lama yang tertutup setelah client sudah mengirim heartbeat lewat socket yang lebih baru diabaikan.
  - Jaringan hilang tanpa penutupan koneksi: `OFFLINE` dan `INTERRUPTED` muncul bersamaan setelah `interruption_threshold` ujian tanpa heartbeat (default 30 detik = tiga heartbeat terlewat; batas 15–600 detik). Scheduler berjalan tiap 2 detik.
  - Attempt `PAUSED` hanya menjadi `OFFLINE`; statusnya tetap `PAUSED` (§10.1).
- Setiap request bertanda tangan dari device session aktif dihitung sebagai bukti hidup dan melanjutkan attempt `INTERRUPTED` seperti heartbeat (auto-resume atau menunggu persetujuan, §20.4). Dengan demikian `finish`, upload event, dan sync tetap berfungsi segera setelah koneksi WSS terputus.

## 17.7 Full State Synchronization

Dilakukan saat launch, setiap reconnect, dan saat client mendeteksi `state_version` server lebih tinggi dari miliknya.

```text
GET /client/v1/attempts/{attempt_id}/state
```

Response (di dalam signed envelope, `kid.use = state`):

```json
{
  "attempt_id": "…",
  "status": "ACTIVE",
  "state_version": 18,
  "deadline": "2026-09-23T10:45:00+07:00",
  "server_time": "2026-09-23T10:32:05+07:00",
  "resume_allowed": true,
  "pending_warning": null
}
```

Response state ditandatangani agar proxy lokal di mesin peserta tidak dapat memalsukan status (mis. memalsukan `SUBMITTED` untuk keluar dari lockdown).

## 17.8 Upload event

`POST /client/v1/attempts/{attempt_id}/events` secara batch. Idempoten berdasarkan `(device_session_id, seq)`. Selama offline, event disimpan di queue lokal terenkripsi dan dikirim saat tersambung kembali, berurutan menurut `seq`.

---

# 18. Device Session Identity & Client Authentication

1. Saat launch, client membuat key pair **Ed25519** ephemeral.
2. Private key disimpan di keystore OS (Windows DPAPI/CNG, macOS Keychain, Linux Secret Service; fallback file terenkripsi).
3. Client mengirim `public_key` + launch token ke `POST /client/v1/device-sessions`. Server mengikat public key ke **Candidate + Attempt + Device Session**.
4. Setiap request HTTPS dan heartbeat berikutnya ditandatangani:

```text
Authorization: EG-Sig sid=<device_session_id>, ts=<unix_ms>, sig=<base64url>
sig = Ed25519(method \n path \n ts \n sha256(body))
```

Server menolak request dengan `ts` di luar ±60 detik atau signature tidak valid. `sha256(body)` ditulis sebagai hex huruf kecil, dan path mencakup query string bila ada. Detail lengkap di `docs/PROTOCOL.md`.

Aturan satu perangkat:

- Satu attempt hanya memiliki **satu** device session aktif.
- Registrasi device session baru saat yang lama masih aktif (atau setelah private key hilang, mis. OS di-reinstall) selalu masuk `WAITING_FOR_INVIGILATOR`. Setelah disetujui, device session lama dicabut.
- Sebelum attempt dimulai (`NOT_STARTED`), device session baru langsung menggantikan yang lama tanpa persetujuan, karena belum ada pengerjaan yang perlu dilindungi.
- Saat attempt `PAUSED`, registrasi device session baru ditolak sampai pengawas melanjutkan ujian, agar mode timer pause tidak hilang.
- Client yang restart di perangkat yang sama memakai device session yang sama (key di keystore OS) dan cukup mengirim heartbeat; ini bukan pindah perangkat.
- Request start yang bertanda tangan dihitung sebagai heartbeat, sehingga waktu menunggu di layar check-in tidak dianggap jeda (Q18).
- Device session yang sudah dicabut tetap boleh mengunggah event dari queue lokalnya, karena event tersebut adalah bukti (Q19); endpoint lain menolaknya.

---

# 19. Key Management

| Kunci | Pemilik | Fungsi |
|---|---|---|
| **Root trust key** | Platform Admin (offline) | Menandatangani key set. Public key-nya di-embed di binary client. |
| Command signing key (`use=command`) | Server | Command WSS |
| State signing key (`use=state`) | Server | Response full state sync |
| Config signing key (`use=config`) | Server | Signed Exam Config |
| Token signing key (`use=token`) | Server | Attestation token & completion token |
| Device session key | Client (per attempt) | Request & heartbeat |

Pada MVP, satu private key server boleh dipakai untuk semua `use`, selama setiap penggunaan tetap berlabel `kid` + `use` agar pemisahan kunci di kemudian hari tidak mengubah protokol.

Distribusi dan rotasi:

- Server mempublikasikan `/.well-known/examguard-keys.json` berisi public key aktif, masing-masing dengan `kid`, `use`, `not_before`, `not_after`. Dokumen ini ditandatangani root trust key.
- Client memverifikasi key set dengan root trust key sebelum mempercayai `kid` apa pun.
- Kunci baru dipublikasikan sebelum dipakai; kunci lama tetap tersedia untuk verifikasi sampai semua token/command yang ditandatanganinya kedaluwarsa.
- Kunci yang dicabut dicantumkan di key set sebagai `revoked`.
- Produksi: private key server disimpan di KMS/HSM.
- `kid` server berbentuk `<base>.<use>` (mis. `srv-20260930-6vNhhQ.command`); key set memuat satu entri per `use`, dan client wajib mencocokkan `use`. `kid` root berbentuk `root-<16 hex pertama SHA-256 public key root>`.

---

# 20. Crash Recovery, Interruption & Re-entry

## 20.1 Local recovery state

Disimpan terenkripsi dengan kunci dari keystore OS. Isi:

```text
server_endpoint
exam_id, attempt_id, device_session_id
last_state_version
deadline (cache, bukan authoritative)
applied_command_ids
event_queue_pointer
lockdown_active flag
```

Jawaban ujian tidak disimpan; itu tanggung jawab website ujian (§23).

## 20.2 Alur setelah restart

```text
ExamGuard start
   ↓
Recovery state dengan lockdown_active = true ditemukan
   ↓
Langsung masuk lockdown (sebelum koneksi jaringan)
   ↓
Recovery Mode → connect server → full state sync
   ↓
┌─ ACTIVE/INTERRUPTED + syarat auto-resume terpenuhi → lanjut ujian
├─ WAITING_FOR_INVIGILATOR → layar menunggu persetujuan
├─ PAUSED → overlay dijeda
└─ status final → release lockdown, hapus recovery state, tutup
```

Masuk lockdown sebelum koneksi mencegah restart dipakai sebagai cara keluar. Pada MVP peserta meluncurkan ulang client secara manual; autostart saat attempt aktif masuk roadmap pasca-MVP.

## 20.3 Unmonitored gap

```text
09:37:07 heartbeat terakhir
09:44:25 heartbeat pertama setelah reconnect
→ UNMONITORED_INTERRUPTION, durasi 7m 18s
```

Klasifikasi penyebab (metadata, bila dapat diketahui): `NETWORK_FAILURE`, `UNEXPECTED_SHUTDOWN`, `CLIENT_CRASH`, `UNKNOWN`. Sistem tidak menyimpulkan peserta melakukan kecurangan. Karena request bertanda tangan apa pun melanjutkan attempt (§17.6), client mengirim penyebab pada request pertama setelah tersambung kembali, yaitu heartbeat dengan `recovery_cause`, sebelum full state sync; jika tidak, penyebab tercatat `UNKNOWN`.

Jeda kurang dari 10 detik (misalnya Wi-Fi berpindah access point, atau client dibuka ulang dengan cepat) tidak membuat incident `UNMONITORED_INTERRUPTION`, agar daftar incident tidak dibanjiri gangguan sesaat. Jeda tersebut tetap terlihat di riwayat transisi attempt (`INTERRUPTED → ACTIVE` beserta durasinya) (Q26).

## 20.4 Re-entry policy

| Pengaturan | Default |
|---|---|
| Allow automatic recovery | ON |
| `reentry_approval_threshold` | 10 menit |
| Device session berbeda | Selalu butuh persetujuan |

```text
gap < 10 menit, device sama, deadline belum lewat → auto resume
gap ≥ 10 menit atau device berbeda                  → WAITING_FOR_INVIGILATOR
deadline sudah lewat                                → EXPIRED
```

Layar client saat menunggu:

```text
┌──────────────────────────────────────┐
│ Pemulihan Ujian                      │
│                                      │
│ Sesi ujian Anda sebelumnya terputus. │
│ Menunggu persetujuan pengawas...     │
└──────────────────────────────────────┘
```

Tampilan pengawas:

```text
Student F meminta masuk kembali.
Terputus: 14 menit 18 detik
Penyebab: UNEXPECTED_SHUTDOWN
[Tolak]  [Izinkan Lanjut]
```

---

# 21. Network & Server Failure

**Koneksi internet terputus.** Client tetap lockdown, tetap melakukan monitoring lokal, menyimpan event di queue terenkripsi, dan mencoba reconnect dengan exponential backoff (maks. 30 detik). Saat tersambung: full state sync, lalu upload queue.

**Server tidak tersedia.** Client tidak otomatis keluar dan menampilkan:

```text
Server ujian tidak tersedia.
Ujian Anda tetap terkunci dengan aman.
Mencoba menghubungkan kembali...
```

Peserta tetap dapat mengerjakan jika website ujian masih dapat diakses. Emergency unlock (§22) tersedia untuk pengawas.

---

# 22. Emergency Unlock

Shortcut khusus membuka layar **Emergency Unlock** (bukan desktop). Metode:

| Metode | Kondisi | Mekanisme |
|---|---|---|
| Online | Client terhubung ke server | Pengawas menekan "Emergency Unlock" di Admin Web → server mengirim command `EMERGENCY_UNLOCK` bertanda tangan |
| Kode cadangan | Server dan Admin Web sama-sama tidak dapat diakses | Kode sekali pakai yang dicetak sebelum ujian, diverifikasi offline dengan hash (lihat di bawah) |
| Challenge–response | Client offline, pengawas dapat mengakses Admin Web | Client menampilkan challenge 8 karakter → pengawas memasukkannya di Admin Web → Admin Web menampilkan response 8 digit = `trunc(HMAC-SHA256(attempt_unlock_secret, challenge))` → dimasukkan di client |

- `attempt_unlock_secret` unik per attempt, dikirim ke client saat registrasi device session dan disimpan di recovery state terenkripsi. Kebocoran secret hanya berdampak pada attempt itu sendiri, dan pemakaiannya tetap tercatat.
- Challenge berlaku 10 menit; maksimal 5 percobaan salah, kemudian jeda bertahap.
- Setelah unlock: event `EMERGENCY_UNLOCK_USED` dicatat, event queue dipertahankan untuk diunggah pada peluncuran berikutnya, dan di server attempt menjadi `INTERRUPTED` sampai ada keputusan pengawas.

**Kode cadangan cetak (MVP).**

- Server membuat sejumlah kode sekali pakai per ujian atau per kelompok pengawasan (±10 karakter base32, entropi tinggi). Pengawas mengunduh atau mencetaknya sebelum ujian.
- Client hanya menerima **hash** kode tersebut di dalam Signed Exam Config, sehingga dapat memverifikasi secara offline tanpa mengetahui kodenya.
- Setiap kode hanya berlaku sekali per client, dan pemakaiannya dilaporkan saat client tersambung kembali.
- Pada tes publik, kode hanya dipegang pengawas sesi; peserta tidak pernah melihatnya.

**Detail implementasi.**

- Challenge: 8 karakter base32 (`A–Z`, `2–7`). Respons: 4 byte pertama HMAC-SHA256 (big-endian) modulo 10⁸, ditulis 8 digit.
- `attempt_unlock_secret` dikirim di respons registrasi device session dan sama untuk semua device session dalam satu attempt.
- Kode cadangan berformat `XXXXX-XXXXX`. Signed Exam Config memuat `sha256(exam_id + ":" + kode)` untuk kode yang belum terpakai, sehingga kode harus dibuat **sebelum** peserta meluncurkan client.
- Event `EMERGENCY_UNLOCK_USED` dengan `metadata.method` (`ONLINE`, `CHALLENGE`, `BACKUP_CODE`) menandai kode terpakai, membuat incident, dan memindahkan attempt `ACTIVE` ke `INTERRUPTED`.

**Safety valve (MVP).** Jika server tidak dapat dihubungi dan estimasi waktu server sudah melewati `deadline + offline_release_grace` (default 30 menit), client melepas lockdown secara otomatis, mencatat event `OFFLINE_AUTO_RELEASE`, dan menyimpan event queue untuk diunggah nanti. Tanpa mekanisme ini, peserta bisa terkunci tanpa batas ketika server mati total, termasuk setelah restart, karena recovery mode masuk lockdown sebelum mencoba koneksi (§20.2).

---

# 23. Autosave Requirement (tanggung jawab website ujian)

| Jenis soal | Perilaku |
|---|---|
| Pilihan ganda | Simpan segera setiap jawaban berubah |
| Essay | Debounce 1–2 detik, lalu autosave |

Website ujian harus mendukung pemulihan attempt (jawaban yang sudah tersimpan tampil kembali setelah reload) dan menolak penyimpanan saat attempt tidak `ACTIVE` (§16.4).

---

# 24. Privasi & Perlindungan Data

Bagian ini perlu direview oleh tim hukum institusi terkait **UU No. 27 Tahun 2022 tentang Pelindungan Data Pribadi (UU PDP)** dan regulasi institusi.

- **Consent:** sebelum preflight, client menampilkan apa saja yang dipantau (kamera, mikrofon, proses yang cocok daftar terlarang, konfigurasi display) dan apa yang dikirim ke server. Peserta harus menyetujui untuk melanjutkan.
- **Minimisasi data:** tidak ada streaming/perekaman video atau audio pada MVP; hanya event metadata. Daftar proses lengkap tidak dikirim.
- **Evidence snapshot:** nonaktif secara default; bila diaktifkan, disimpan terenkripsi.
- **Akses:** evidence hanya dapat dibuka oleh Exam Admin dan invigilator yang ditugaskan ke ujian tersebut. Setiap akses tercatat di audit log.
- **Retensi:** berjenjang dan dapat diatur (§24.1).
- **Peran pengendali data:** pada tes instansi, instansi bertindak sebagai pengendali data peserta yang diundangnya dan platform sebagai pemroses. Pada tes publik, platform operator adalah pengendali. Pembagian ini perlu dituangkan dalam perjanjian dengan setiap instansi.
- **Hak subjek data:** Admin dapat mengekspor dan menghapus data peserta tertentu sesuai prosedur institusi. Peserta dapat meminta penghapusan akun melalui Candidate Portal.

## 24.1 Retensi data

| Data | Default |
|---|---|
| Evidence & event proctoring dari incident `DISMISSED` | 30 hari setelah exam `FINALIZED` |
| Evidence & event proctoring lainnya | 90 hari setelah exam `FINALIZED` |
| Foto identity check | 90 hari setelah exam `FINALIZED` |
| Audit log administratif | Tidak dihapus otomatis; mengikuti kebijakan arsip organisasi |

- Pengaturan berjenjang: default platform → organisasi → ujian (§8.5). Platform Admin menetapkan batas minimum dan maksimum.
- Memperpendek retensi membutuhkan konfirmasi eksplisit karena dapat langsung memicu penghapusan.
- Perubahan pada ujian yang sudah `FINALIZED` hanya berlaku ke depan.
- Nilai default di atas adalah titik awal dan tetap perlu divalidasi tim hukum.

---

# 25. Non-Functional Requirements

| Kategori | Target |
|---|---|
| Skala | 1 instance server melayani ≥ 1.000 peserta bersamaan (≈ 100 heartbeat/detik); horizontal scaling via Redis pub/sub |
| Latensi command | p95 < 2 detik dari klik pengawas sampai `APPLIED` di client (online) |
| Live monitoring | Perubahan status tampil di Admin Web < 3 detik |
| Ketersediaan | 99,9% selama jendela ujian terjadwal |
| CPU client | Rata-rata < 25% pada perangkat referensi (4 core, 8 GB RAM, tanpa GPU) dengan proctoring aktif |
| RAM client | < 1,5 GB termasuk CEF |
| Startup client | < 10 detik sampai layar login |
| OS minimum (usulan) | Windows 10 22H2 / 11, macOS 13+, Ubuntu 22.04+ (X11 atau sesi kiosk) |
| Waktu server | Tersinkron NTP; drift > 1 detik memicu alert |
| Audit log | Append-only, setiap entri memuat hash entri sebelumnya (hash chain) untuk deteksi manipulasi |
| Keamanan transport | TLS 1.2+; certificate pinning opsional via Signed Exam Config |
| Bahasa UI | Indonesia dan Inggris |
| Isolasi tenant | Automated test memastikan tidak ada akses data lintas organisasi; RLS aktif di semua tabel milik organisasi |
| Registrasi publik | Menahan lonjakan pendaftaran (≥ 50 registrasi/detik) tanpa melebihi kuota sesi (pengurangan kuota atomik) |

---

# 26. Client Distribution & Update

- Installer ditandatangani (Windows Authenticode, macOS notarization, paket Linux bertanda tangan).
- Setiap exam memiliki `min_client_version`; client yang lebih lama gagal di preflight dengan tautan unduhan.
- Client **tidak** melakukan update selama attempt aktif.
- Platform Admin dapat menandai versi tertentu sebagai `blocked` (mis. karena celah keamanan).

---

# 27. ExamGuard Admin Web

## 27.1 Menu utama

Dashboard · Exams · Registrations · Check-in Queue · Live Monitoring · Candidates · Incidents · Interrupted Sessions · Audit Logs · Organization Settings · Platform Settings (khusus Platform Admin)

Semua halaman dibatasi pada organisasi aktif. Pengguna yang tergabung di beberapa organisasi berpindah melalui *organization switcher*.

## 27.2 Dashboard

```text
┌──────────────────────────────────────────────────────────┐
│ ExamGuard                                      Admin ▼   │
├──────────────────────────────────────────────────────────┤
│ Active Exams     Online Candidates     Open Incidents    │
│     4                  326                    18         │
│ Interrupted      Waiting Approval      Camera Problems   │
│     7                  2                      3          │
├──────────────────────────────────────────────────────────┤
│ Machine Learning Midterm   RUNNING   84 / 90 online      │
│ Cyber Security Final       RUNNING  116 / 120 online     │
│ Database Systems Quiz      READY     —                   │
└──────────────────────────────────────────────────────────┘
```

## 27.3 Exams & Create Exam

Daftar ujian menampilkan status exam (§9): DRAFT, READY, RUNNING, CLOSED, FINALIZED, CANCELLED.

Form Create/Edit Exam:

| Field | Keterangan |
|---|---|
| Exam Name, Exam Code | |
| Exam Website URL, Allowed Origins | Origin tambahan untuk SSO/CDN yang dipakai website ujian |
| Window Start, Latest Start, Window End | §11.1 |
| Duration (opsional), Late Start Policy | §11.2 |
| Integration Level | 0 atau 2 (§16.1) |
| Visibility | `PRIVATE` atau `PUBLIC` (hanya organisasi dengan izin publikasi publik) |
| Registration Open / Close, Capacity | Untuk ujian `PUBLIC` |
| Access / Voucher Code | Opsional, untuk membatasi pendaftaran |
| Identity Check | `NONE` / `MANUAL` (§12.5) |
| Check-in Open | Default 30 menit sebelum Window Start |
| Candidates | `PRIVATE`: undangan email, import CSV, atau Integration API. `PUBLIC`: dari pendaftaran mandiri. Akomodasi waktu diatur per enrollment |
| Invigilators | Penugasan pengawas |
| Security Policy | Dari template, dapat diubah |
| Proctoring Policy | Kamera/mic wajib, deteksi aktif, ambang, fps, evidence snapshot |
| Re-entry Policy | §20.4 |
| Minimum Client Version | |

Ujian tidak dapat dipublikasikan (DRAFT → READY) jika field wajib belum lengkap atau policy tidak konsisten (mis. face detection aktif tetapi kamera tidak wajib).

## 27.4 Security & Proctoring Policy

```text
Lockdown
 ☑ Fullscreen lockdown              Minimum lockdown level: [STANDARD ▼]
 ☑ Block application switching
 ☑ Disable clipboard
 ☑ Disable screenshots (best-effort)
 ☑ Block additional monitors
 ☑ Monitor running applications     Allowed apps: [Calculator, …]
 ☑ Block remote access
 ☐ Block virtual machines           (MVP: warn-only, opsi blokir menyusul)
 ☐ Block WSL                        (roadmap)

Proctoring
 ☑ Require camera      ☑ Person detection    ☑ Face detection
 ☑ Require microphone  ☑ Voice activity detection
 ☐ Evidence snapshot
 Inference rate: [2] fps
```

## 27.5 Live Monitoring

```text
┌───────────────────────────────────────────────────────────────────────┐
│ ML Midterm — LIVE                                         10:17:32   │
├───────────────────────────────────────────────────────────────────────┤
│ Online 84/90   Open incidents 7   Offline 2   Waiting 1   Ended 3    │
├───────────────────────────────────────────────────────────────────────┤
│ ☐ Candidate   Status       Conn.    Cam  Mic  Remaining  Incidents    │
│ ☐ Student A   ACTIVE       ONLINE   ●    ●    00:42:13   0            │
│ ☐ Student B   ACTIVE       ONLINE   ●    ●    00:42:13   2 ⚠          │
│ ☐ Student C   INTERRUPTED  OFFLINE  -    -    00:40:02   1 ⚠          │
│ ☐ Student D   PAUSED       ONLINE   ●    ●    00:39:50   3 ⚠          │
│ ☐ Student F   WAITING      ONLINE   ●    ●    00:31:11   1 ⚠          │
│                                                                       │
│ [Search]  [Filter: status / incident / connection]  [Bulk actions ▼] │
└───────────────────────────────────────────────────────────────────────┘
```

Pembaruan real-time: Admin Web memuat ulang daftar setiap 2 detik selama tab terlihat, dan sisa waktu berdetak di browser di antara pemuatan. Target §25 (perubahan status tampil < 3 detik) terpenuhi. WebSocket khusus staf dapat ditambahkan nanti bila jumlah pengawas bersamaan membuat pemuatan berkala terlalu berat (Q22).

Baris yang membutuhkan tindakan pengawas disorot: `INTERRUPTED`, `WAITING_FOR_INVIGILATOR`, ada incident terbuka, identity check menunggu, atau peserta yang masih berlangsung (misalnya dijeda) dan offline. Terputus dan Offline selalu muncul bersamaan (§17.6); client yang tertutup tampil dalam ≤ 2 detik, panel peserta juga dimuat ulang tiap 2 detik.

## 27.6 Candidate Detail

```text
┌───────────────────────────────────────────────────────────────┐
│ Student B                                                     │
├───────────────────────────────────────────────────────────────┤
│ Status        ACTIVE            Connection   ONLINE           │
│ Deadline      10:45 (sisa 00:42:13)                           │
│ Camera        Connected         Microphone   Connected        │
│ Client        ExamGuard 0.2.0 · Windows 11 · Lockdown STRICT  │
│ Preflight     Lulus (1 warning)                               │
│                                                               │
├───────────────────────────────────────────────────────────────┤
│ INCIDENT                              2 belum ditinjau dari 3 │
│ Waktu        Kejadian                    Durasi   Tinjauan    │
│ 10:22:09     Lebih dari satu orang  High  4 d     Belum       │
│              Kamera menangkap lebih dari satu orang.          │
│              keyakinan 86%                                    │
│ 10:15:21 –   Wajah tidak terlihat  Medium 8 d     Belum       │
│ 10:15:29     Kamera tidak menangkap wajah peserta. 2 event    │
│ 09:58:40 –   Tidak terpantau (terputus)  2 m 5 d  Diabaikan   │
│ 10:00:45     penyebab: jaringan terputus                      │
├───────────────────────────────────────────────────────────────┤
│ [Warning] [Pause] [Add Time] [Force Submit] [Terminate]       │
│ [Emergency Unlock]                                            │
├───────────────────────────────────────────────────────────────┤
│ EVENT TIMELINE                                                │
│ 10:02:14  EXAM_STARTED                                        │
│ 10:15:21  FACE_MISSING                       8 s    Medium    │
│ 10:22:09  MULTIPLE_PERSON                    4.2 s  High      │
│ 10:28:32  VOICE_ACTIVITY                     7 s    Medium    │
│ 10:32:04  DEADLINE_UPDATED  10:30 → 10:45   by Invigilator A  │
└───────────────────────────────────────────────────────────────┘
```

Tombol hanya tampil bila transisinya valid untuk status saat ini (§10.3) dan diizinkan untuk role pengguna (§7).

Bagian **Incident** menampilkan semua incident peserta, yang belum ditinjau di atas lalu yang terbaru. Setiap baris memuat waktu mulai dan selesai, nama kejadian yang dapat dibaca beserta penjelasan singkat, severity, durasi (incident sesaat ditulis "sesaat"; incident yang belum selesai ditulis "berlangsung" dengan durasi yang terus bertambah), rincian dari data incident (penyebab terputus untuk `UNMONITORED_INTERRUPTION`, tingkat keyakinan untuk deteksi AI, jumlah event yang digabung), catatan tinjauan, dan status tinjauan. Mengklik baris membuka dialog dengan event terkait dan formulir tinjauan (§27.8). Angka incident di Live Monitoring membuka panel ini langsung di bagian Incident. Severity tetap hanya untuk prioritas peninjauan, bukan bukti kecurangan (§15).

## 27.7 Dialog aksi

Semua dialog aksi wajib mengisi **Reason**.

**Add Time:** menampilkan deadline saat ini, input menit tambahan, dan deadline baru hasil perhitungan. Server mengirim `UPDATE_DEADLINE` berisi deadline absolut.

**Pause:** reason + pilihan timer (`Keep timer running` default / `Pause timer`).

**Terminate:** reason + teks konfirmasi bahwa aksi langsung mengakhiri sesi. Jawaban yang sudah tersimpan di LMS **selalu dipertahankan**; ExamGuard tidak menghapus jawaban. Keputusan apakah jawaban tersebut dinilai berada di tangan penyelenggara.

**Reopen (SUBMITTED/EXPIRED) & Reinstate (TERMINATED):** menampilkan status sebelumnya, input deadline baru (wajib di masa depan), dan reason. Hasil: `REOPENED`/`REINSTATED`, lalu `ACTIVE` saat peserta meluncurkan client.

## 27.8 Incidents

```text
┌─────────────────────────────────────────────────────────────────┐
│ Incidents                            [Filter: OPEN ▼] [Exam ▼]  │
├─────────────────────────────────────────────────────────────────┤
│ Severity │ Candidate │ Type               │ Time   │ Status     │
│ High     │ Student B │ MULTIPLE_PERSON    │ 10:22  │ OPEN       │
│ Medium   │ Student C │ VOICE_ACTIVITY     │ 10:24  │ REVIEWED   │
│ Medium   │ Student D │ FACE_MISSING       │ 10:25  │ DISMISSED  │
│ High     │ Student E │ PROHIBITED_APP     │ 10:27  │ OPEN       │
└─────────────────────────────────────────────────────────────────┘
```

Detail incident menampilkan event, waktu, durasi, confidence, evidence (bila ada), dan aksi: **Dismiss**, **Add Note**, **Send Warning**, **Pause Candidate**, **Terminate Candidate**. Severity tidak berarti peserta bersalah.

## 27.9 Interrupted Sessions & Re-entry Requests

```text
Candidate   Last Seen   Reconnected   Gap      Penyebab             Status
Student C   10:12:05    10:18:19      6m14s    NETWORK_FAILURE      Auto-resumed
Student F   10:20:11    10:34:29      14m18s   UNEXPECTED_SHUTDOWN  WAITING  [Tolak] [Izinkan]
```

## 27.10 Bulk & Whole-Exam Actions

- Bulk (peserta terpilih): Send Warning, Pause, Resume, Add Time.
- Bulk Terminate: hanya Exam Admin, dengan elevated confirmation (mengetik ulang kode ujian + reason).
- Extend Exam (seluruh ujian): hanya Exam Admin, menambah X menit ke semua attempt non-final (§11.3).
- Setiap bulk action menghasilkan satu entri audit induk dan satu entri per peserta.

## 27.11 Audit Log

Semua aksi administratif, perubahan konfigurasi, akses evidence, dan transisi state tercatat. Audit log **tidak dapat diedit atau dihapus** oleh siapa pun melalui aplikasi.

```text
10:14:22  WARNING_SENT       Actor: Invigilator A  Candidate: Student B
10:32:04  DEADLINE_UPDATED   Actor: Invigilator A  Candidate: Student B
          Old: 10:30  New: 10:45  Reason: Technical compensation
10:45:17  EXAM_TERMINATED    Actor: Invigilator A  Candidate: Student C
          Reason: Unauthorized assistance
10:51:03  EVIDENCE_VIEWED    Actor: Exam Admin X   Incident: #4821
```

## 27.12 Registrations

Daftar pendaftar per ujian: nama, email, sumber (`SELF_REGISTERED` / `INVITED` / `IMPORTED` / `API`), status, waktu daftar, dan status system check. Aksi: kirim undangan, batalkan pendaftaran, pindahkan ke sesi lain, atur akomodasi waktu. Untuk ujian publik ditampilkan indikator kuota terisi.

## 27.13 Check-in Queue

```text
┌───────────────────────────────────────────────────────────────────────┐
│ Check-in — English Proficiency Test · Sesi 12 Okt 09:00    Antre: 6  │
├───────────────────────────────────────────────────────────────────────┤
│ Peserta     Selfie   Foto ID   Nama terdaftar    Masuk   Aksi         │
│ Budi S.     [img]    [img]     Budi Santoso      08:41   [Tolak] [Setujui] │
│ Rina A.     [img]    [img]     Rina Amalia       08:43   [Tolak] [Setujui] │
└───────────────────────────────────────────────────────────────────────┘
```

## 27.14 Organization Settings (Org Admin)

Pengguna & role · Policy template · Re-entry policy default · Identity check default · Retensi data (dalam batas platform) · Integrasi (API credentials, webhook URL).

## 27.15 Platform Settings (Platform Admin)

Organisasi & izin publikasi tes publik · Signing keys (lihat, rotasi, cabut) · Versi client (minimum, blocked) · Default dan batas global (retensi, threshold).

---

# 28. ExamGuard Candidate Portal

## 28.1 Fungsi

- **Akun:** registrasi dengan verifikasi email, login, reset password, profil, permintaan penghapusan akun.
- **Katalog tes publik:** daftar sesi `PUBLIC` yang registrasinya terbuka, dengan filter tanggal dan jenis tes serta sisa kuota.
- **Pendaftaran:** mengisi data sesuai identitas, voucher bila diperlukan, pembatalan atau pindah sesi sampai `registration_close`.
- **Undangan instansi:** menerima undangan dan menautkannya ke akun.
- **Ujian Saya:** jadwal, status system check, tombol unduh client, System Check, dan **Mulai Ujian**.
- **Riwayat & hasil:** status akhir attempt dan hasil bila website ujian mengirimkannya dan ujian mengizinkan (`show_result`).
- **Notifikasi email:** konfirmasi pendaftaran, pengingat H-1 dan 1 jam sebelum ujian, perubahan atau pembatalan jadwal.

## 28.2 Alur tes perorangan (publik)

```text
Buat akun → verifikasi email
   ↓
Pilih sesi di katalog → isi data sesuai identitas → voucher (bila diperlukan)
   ↓
Pendaftaran terkonfirmasi (kuota berkurang atomik) → email konfirmasi
   ↓
Unduh client → System Check (practice mode)
   ↓
Hari H: check-in dibuka → Mulai Ujian → client diluncurkan (§12.2)
```

## 28.3 Alur tes instansi

```text
Instansi mengundang peserta → email undangan
   ↓
Peserta membuat akun baru atau klaim akun yang ada
   ↓
Ujian muncul di "Ujian Saya" → System Check → Mulai Ujian
```

## 28.4 Halaman "Ujian Saya"

```text
┌──────────────────────────────────────────────────────────────┐
│ Ujian Saya                                                   │
├──────────────────────────────────────────────────────────────┤
│ English Proficiency Test — Publik                            │
│ Sabtu, 12 Okt 2026 · 09:00 WIB · Check-in mulai 08:30        │
│ System check: ✓ Lulus (10 Okt)                               │
│ [Batalkan pendaftaran]                        [Mulai Ujian]  │
├──────────────────────────────────────────────────────────────┤
│ Tes Rekrutmen Engineer — PT Contoh Jaya                      │
│ Senin, 14 Okt 2026 · 13:00 WIB                               │
│ System check: belum dilakukan          [Jalankan System Check] │
└──────────────────────────────────────────────────────────────┘
```

Tombol **Mulai Ujian** hanya aktif dari `checkin_open` sampai `latest_start`, dan menerbitkan launch link sekali pakai. Selama attempt berjalan (termasuk `INTERRUPTED` dan `WAITING_FOR_INVIGILATOR`) dan untuk attempt `REOPENED`/`REINSTATED`, tombol tetap aktif dengan label "Buka kembali ExamGuard", agar peserta dapat meluncurkan ulang client setelah crash. Server menerapkan aturan yang sama (`LAUNCH_NOT_YET_OPEN`, `LATE_START_CLOSED`). Aturan jendela ini khusus untuk portal: launch link dari Integration API (LMS) dan alat pengembangan tidak dibatasi jendela, karena LMS mengatur sendiri kapan peserta diarahkan ke ujian (Q29).

Setiap kartu ujian menampilkan satu kalimat posisi peserta saat ini: hitung mundur ke check-in, "check-in sudah dibuka, mulai sebelum HH.MM", "ujian Anda sedang berjalan", atau "batas waktu mulai sudah lewat". Ujian yang selesai, pendaftaran yang dibatalkan (oleh peserta, penyelenggara, atau karena pindah sesi), dan ujian yang dibatalkan penyelenggara pindah ke bagian Riwayat.

## 28.5 Akses dan sesi

- Halaman `/` menampilkan dua pilihan: **Masuk sebagai peserta** (Candidate Portal, `/portal/`) dan **Masuk sebagai staf** (Admin Web, `/admin/`).
- Akun peserta dan akun staf disimpan terpisah, sehingga satu email dapat menjadi staf di satu organisasi dan peserta di organisasi lain. Masing-masing punya halaman login sendiri, dan sesinya disimpan terpisah di browser: masuk sebagai staf tidak mengeluarkan atau menggantikan sesi peserta di browser yang sama (Q28).
- Peserta diminta memakai laptop atau PC, karena ujian berjalan di client desktop. Portal dirancang untuk layar desktop dan tetap terbaca di layar kecil.
- Tautan di email (verifikasi, reset password, undangan) mengarah ke portal di server yang sama (`<public_base_url>/portal`), kecuali dikonfigurasi lain.

## 28.6 Cakupan MVP Phase 3b-1

Sudah tersedia: akun (registrasi, verifikasi email, login, reset dan ganti password, ubah nama), katalog publik dengan filter teks, jenis tes, dan tanggal, pendaftaran dengan kode akses (voucher), pembatalan dan pindah sesi sampai `registration_close`, undangan instansi, Ujian Saya dengan Mulai Ujian, dan riwayat status akhir.

Ditunda: **System Check dan unduh client** menunggu client desktop (Phase 5); sampai saat itu portal menampilkan daftar persiapan dan tombol unduh yang belum aktif, serta menyediakan launch link untuk simulator. **Pengingat email H-1 dan 1 jam** dikerjakan bersama Admin Web lanjutan (Phase 3b-2). **Hasil ujian** (`show_result`) menunggu website ujian mengirimkan hasil. **Permintaan penghapusan akun** dikerjakan bersama pengaturan platform (Phase 3b-2).

---

# 29. Reference Exam Website

## 29.1 Tujuan

Website ujian fungsional yang dipakai sampai sistem web ujian dari tim lain siap, sekaligus menjadi implementasi referensi integrasi Level 2 yang dapat ditiru.

## 29.2 Fitur MVP

- Bank soal sederhana per ujian: pilihan ganda dan essay, diimpor dari file JSON/CSV.
- Penyajian soal dengan navigasi nomor dan penanda "ragu-ragu"; opsi pengacakan urutan soal dan pilihan jawaban per peserta.
- Autosave sesuai §23.
- Timer diambil dari `window.examguard.getSessionInfo()` dan `onStateChange()`, **bukan** timer lokal sendiri.
- Verifikasi Attestation Header pada setiap request; akses tanpa header yang valid ditolak.
- Penyimpanan jawaban ditolak jika attempt tidak `ACTIVE`.
- Submit → `POST /integration/v1/attempts/{id}/completion` → `window.examguard.complete(token)`.
- Penilaian otomatis pilihan ganda; halaman penilaian manual sederhana untuk essay.
- Pengiriman hasil ke ExamGuard Server via endpoint `result` (§16.4).

## 29.3 Batas arsitektur

- Database terpisah dari ExamGuard Server.
- Komunikasi hanya melalui Integration API, webhook, Attestation Header, dan JS Bridge.
- Soal audio (listening), analisis butir soal, dan sertifikat masuk roadmap.

---

# 30. MVP Scope & Development Phases

## 30.1 MVP Scope

**ExamGuard Client:** Rust desktop client; CEF dengan backend Ozone (X11 dan Wayland); launch via link dan kode manual; signed config verification; preflight dan practice mode; consent screen; identity check capture; fullscreen lockdown (Windows, macOS, Linux X11; Wayland level `RELAXED`); URL restrictions; process monitoring; single-monitor policy; remote access detection; VM detection warn-only; camera & microphone capture; YOLOX, YuNet, Silero VAD; event lifecycle dan queue lokal terenkripsi; attestation header; JS Bridge; WSS control channel; signed command validation; heartbeat; full state sync; crash recovery; automatic dan approved re-entry; emergency unlock (online, challenge–response, kode cadangan); safety valve.

**ExamGuard Server:** autentikasi staf dan peserta; organisasi, membership, RBAC, dan isolasi RLS; pengaturan berjenjang; exam management termasuk visibility dan registrasi publik; enrollment, undangan, dan kuota atomik; identity check manual; policy snapshot; attempt state machine (§10); timing service dan scheduler (expire, no-show); signing service dan key set; client API (§17, §18); Integration API dan webhook (§16); WebSocket gateway; event ingestion & incident; retensi otomatis; audit log hash-chained; notifikasi email.

**Admin Web:** seluruh halaman §27.

**Candidate Portal:** seluruh fungsi §28.

**Reference Exam Website:** seluruh fitur §29.2.

**Di luar MVP (roadmap):** Wayland level `STANDARD`/`STRICT` (**wajib**), deteksi VM multi-signal beserta opsi blokir, opsi blokir WSL, pencocokan wajah otomatis, payment gateway, sertifikat dan verifikasinya, soal audio, live video streaming, perekaman audio, unfinalize override, autostart client, dukungan mobile.

## 30.2 Development Phases

Protokol dan server dibangun lebih dulu karena merupakan kontrak antarkomponen dan dapat diuji penuh tanpa perangkat fisik. Phase 1 dipecah menjadi tiga sub-fase agar protokol client (1c) dibangun di atas state engine yang sudah teruji (1b); exit criteria Phase 1 secara keseluruhan tetap: seluruh transisi §10.3, rumus §11, dan test isolasi tenant lulus.

| Phase | Fokus | Deliverable utama | Exit criteria |
|---|---|---|---|
| 1a | **Server Foundation** ✓ | Tenancy + RLS, akun staf & peserta, exam management (DRAFT/READY/CANCELLED), registrasi publik & kuota atomik, undangan, pengaturan berjenjang, audit log hash-chained | Test isolasi tenant, kuota konkuren, dan verifikasi audit chain lulus |
| 1b | **State & Timing Engine** ✓ | Attempt state machine, timing service (deadline, pause, add time, extend), scheduler (RUNNING, NO_SHOW, EXPIRED, INTERRUPTED, CLOSED), penugasan invigilator, API aksi staf, finalize | Seluruh transisi §10.3 dan rumus §11 lulus di level service; transisi yang dipicu client diuji melalui service internal |
| 1c | **Protocol & Integration** ✓ | Signing service & key set (§19), client API & device session (§17, §18), WebSocket gateway, event ingestion & incident, Integration API & webhook (§16), spesifikasi OpenAPI | Transisi yang dipicu client lulus ulang melalui protokol bertanda tangan; test replay, stale command, dan signature lulus |
| 2 | **Headless Client Simulator** ✓ | Client Rust tanpa UI: launch, heartbeat, command, sync, recovery | Skenario crash, reconnect, dan replay lulus terhadap server |
| 3a | **Admin Web (inti)** ✓ | Login & organisasi, Dashboard, ujian & kebijakan, Live Monitoring, Candidate Detail & dialog aksi, Check-in, Incidents, Re-entry, peserta & undangan, pengawas, aksi seluruh ujian | Test end-to-end di browser terhadap server dan peserta simulasi lulus |
| 3b-1 | **Candidate Portal** ✓ | Halaman masuk, akun peserta & reset password, katalog publik, pendaftaran/pindah/batal, undangan, Ujian Saya & Mulai Ujian, riwayat (§28) | Test end-to-end di browser: peserta baru dari pendaftaran sampai memulai ujian lewat launch link portal, terlihat di Admin Web |
| 3b-2 | **Admin Web (lanjutan)** | Pengaturan organisasi & anggota, integrasi LMS, audit log, pengaturan platform, pengingat email, permintaan penghapusan akun | Satu sesi tes publik dan satu tes instansi dapat dijalankan end-to-end memakai simulator |
| 3b-3 | **Terjemahan Inggris** | Admin Web dan Candidate Portal | Semua teks UI tersedia dalam dua bahasa |
| 4 | **Reference Exam Website** | Fitur §29.2 | Alur daftar → check-in → kerjakan → submit → hasil berjalan dengan simulator |
| 5 | **Client Foundation** | Rust + CEF, config, preflight, practice mode, identity check, JS Bridge, attestation | Ujian Level 0 dan Level 2 berjalan di Windows |
| 6 | **Lockdown Adapters** | Windows, macOS, Linux X11; Wayland `RELAXED` | Matriks §13.2 tervalidasi per OS |
| 7 | **Proctoring** | Kamera, mic, ONNX, evidence | Budget CPU §25 terpenuhi pada perangkat referensi |
| 8 | **Recovery & Hardening** | Keystore OS, kode cadangan, safety valve, anti-tampering, integrity check, signed installer, security testing | Tidak ada temuan kritis terbuka |
| Roadmap | **Pasca-MVP** | Wayland `STANDARD`/`STRICT`, deteksi VM multi-signal & blokir, blokir WSL, dan item roadmap lain di §30.1 | — |

---

# 31. Product Principles

1. **Server adalah authoritative source of truth.** Server menentukan ACTIVE, PAUSED, SUBMITTED, REOPENED, EXPIRED, TERMINATED, REINSTATED, dan FINALIZED. Client menjalankan command yang terverifikasi dan tidak pernah menyimpulkan status sendiri.
2. **AI mendeteksi, bukan menghakimi.** ExamGuard menghasilkan Security Event, Proctoring Event, Device Event, dan Session Event. Keputusan administratif dilakukan manusia.
3. **Gagal dengan aman, bukan gagal terbuka.** Kehilangan koneksi atau server tidak melepaskan lockdown; hanya server, emergency unlock yang terotorisasi, atau safety valve setelah waktu ujian habis yang dapat melakukannya.
4. **Setiap aksi dapat diaudit.** Tidak ada perubahan attempt tanpa aktor, alasan, dan jejak audit.
5. **Jujur soal batas jaminan.** Tingkat lockdown per OS dinyatakan eksplisit; ExamGuard tidak mengklaim perlindungan yang tidak dapat diberikan platform.
6. **Privasi secara default.** Data yang dikumpulkan seminimal mungkin untuk tujuan pengawasan.

---

# 32. Decision Log & Open Questions

## 32.1 Decision Log

| # | Topik | Keputusan | Referensi |
|---|---|---|---|
| Q1 | Late start | `FIXED_END` sebagai default; `latest_start` default `window_start` + 30 menit | §11 |
| Q2 | Reject re-entry | `TERMINATED` dengan `reason_category` wajib (TECHNICAL / ADMINISTRATIVE / DISCIPLINARY) | §10.3 |
| Q3 | Linux | X11 di MVP; Wayland wajib di roadmap, arsitektur disiapkan sejak MVP | §13.2 |
| Q4 | Emergency unlock saat semua sistem mati | Kode cadangan cetak (hash) dan safety valve setelah deadline, keduanya masuk MVP | §22 |
| Q5 | Retensi | Dapat diatur berjenjang platform → organisasi → ujian; default 30/90 hari | §24.1 |
| Q6 | Website ujian | Reference Exam Website dibangun dalam proyek; Integration API tetap menjadi batas arsitektur | §16, §29 |
| Q7 | Tenancy | Multi-organisasi sejak awal, isolasi RLS; mendukung tes instansi dan tes perorangan publik | §8 |
| Q8 | Virtual machine | Warn-only di MVP; roadmap deteksi tanpa hypervisor bit dan opsi blokir WSL | §13.3 |
| Q9 | Force submit | Boleh dilakukan invigilator | §7 |
| Q10 | Pindah perangkat | Boleh, selalu dengan persetujuan pengawas | §18 |
| Q11 | Ruang lingkup pekerjaan | Seluruh sistem (client, server, Admin Web, Candidate Portal, Reference Exam Website) dikerjakan dalam proyek ini; integrasi dengan sistem tim web lain ditunda | §16, §29 |
| Q12 | Akomodasi waktu setelah attempt dimulai | Tidak menggeser deadline otomatis; tambahan waktu melalui Add Time agar tercatat dengan aktor dan alasan | §11.3 |
| Q13 | Enrollment setelah ujian berjalan | Undangan, import, dan pendaftaran API ditolak sejak exam `RUNNING`, untuk ujian `PUBLIC` maupun `PRIVATE` | §8.4, §9 |
| Q14 | Pembagian Phase 1 | Phase 1a (fondasi server), 1b (state & timing engine), 1c (protokol & integrasi) | §30.2 |
| Q15 | Pindah perangkat saat ujian berjalan | `ACTIVE → WAITING_FOR_INVIGILATOR`; ditolak saat `PAUSED`; bebas sebelum mulai | §10.3, §18 |
| Q16 | Extend dan peserta yang mulai belakangan | Tambahan waktu extend juga berlaku untuk peserta yang mulai setelahnya | §11.3 |
| Q17 | Penerima webhook | Semua integrasi aktif organisasi yang punya `webhook_url`; filter per ujian dapat ditambah kemudian | §16.6 |
| Q18 | Waktu tunggu check-in | Request start bertanda tangan dihitung sebagai heartbeat | §18 |
| Q19 | Event dari perangkat yang dicabut | Tetap diterima sebagai bukti | §18 |
| Q20 | Cakupan aturan STALE dan command duplikat | STALE hanya untuk command yang mengubah status; duplikat tidak diterapkan ulang tetapi di-ACK `APPLIED` | §17.3, §17.5 |
| Q21 | Teknologi Admin Web | React + Vite + TypeScript, build disajikan oleh server di `/admin/`; bahasa Indonesia dulu dengan struktur i18n | §27, §25 |
| Q22 | Pembaruan Live Monitoring | Pemuatan ulang berkala 2 detik; WebSocket staf ditunda | §27.5 |
| Q23 | Status review incident | OPEN / REVIEWED / DISMISSED / ESCALATED | §8.6, §27.8 |
| Q24 | Pembagian Phase 3 | 3a Admin Web inti, 3b Admin Web lanjutan + Candidate Portal + terjemahan Inggris | §30.2 |
| Q25 | Waktu Offline vs Terputus | Selalu bersamaan: koneksi WSS tertutup → langsung; hilang diam-diam → `interruption_threshold` (default 30 detik) | §10.2, §17.6, §27.5 |
| Q26 | Incident untuk jeda singkat | `UNMONITORED_INTERRUPTION` hanya untuk jeda ≥ 10 detik | §20.3 |
| Q27 | Rincian incident per peserta | Ditampilkan di Candidate Detail: waktu, kejadian, durasi, rincian, status tinjauan; dapat dibuka dari angka incident | §27.5, §27.6 |
| Q28 | Login peserta dan staf | Satu halaman masuk dengan dua pilihan; login, akun, dan sesi tetap terpisah | §28.5 |
| Q29 | Cakupan jendela Mulai Ujian | Berlaku untuk portal; Integration API dan alat pengembangan tidak dibatasi; buka ulang diizinkan selama attempt berjalan | §28.4 |

## 32.2 Keputusan Sementara (dapat ditinjau ulang)

Pertanyaan berikut sudah diputuskan untuk sementara mengikuti usulan awal. Keputusan ini dapat ditinjau kembali ketika kebutuhannya menjadi lebih jelas.

| # | Topik | Keputusan sementara | Referensi |
|---|---|---|---|
| N1 | Pendaftaran tes publik berbayar | MVP: gratis atau memakai voucher code; payment gateway di roadmap | §8.3, §30.1 |
| N2 | Pencocokan wajah otomatis | Roadmap, setelah review hukum terkait data biometrik; MVP memakai identity check manual | §12.5 |
| N3 | Sertifikat dan verifikasinya | Roadmap | §29.3, §30.1 |
| N4 | Pindah sesi dan pembatalan tes publik | Bebas sampai `registration_close`; kebijakan refund mengikuti N1 | §8.4 |
| N5 | Rasio pengawas per peserta | Ditentukan per ujian; angka acuan ditetapkan setelah uji coba | §12.5, §27.13 |
| N6 | Soal audio (listening) | Roadmap Reference Exam Website | §29.3 |
| N7 | Login bersama (SSO/OIDC) dengan sistem tim web | Ditunda sampai konsep tim web siap | §16 |

Saat ini tidak ada open question yang menghalangi dimulainya Phase 3b-2.
