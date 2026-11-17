Claude saya ingin melanjutkan membuat ExamGuard, sebuah aplikasi untuk test online. Saya sudah diskusi mengenai ini di sesi percakapan sebelumnya. Saya akan berikan file PRD untuk sistem ini dan phase 1a nya. Nanti kita akan lanjutkan untuk phase 1b setelah kamu baca filenya.


Ran 5 commands, read memory, read a file
Ran 5 commands, read memory, read a file
Now the Phase 1a code.


Ran 6 commands
Ran 6 commands
Saya sudah membaca PRD v0.3 dan seluruh kode Phase 1a. Ringkasnya, ini posisi kita sekarang.

Yang sudah ada di Phase 1a. Fondasinya solid: skema dengan dua role database (owner vs runtime) sehingga RLS selalu berlaku, konteks app.ctx/org_id/user_id/candidate_id per transaksi, trigger yang menurunkan org_id dari parent, audit log hash-chained yang hanya bisa ditulis lewat eg_audit_append(), kuota atomik via eg_reserve_seat(), pengaturan berjenjang dengan bounds, serta alur akun, publish/unpublish/cancel ujian, katalog publik, registrasi, pindah sesi, dan undangan. Status ujian baru sampai DRAFT → READY → CANCELLED, dan tabel attempts masih minimal (hanya status dan state_version).

Yang masih kurang untuk memenuhi exit criteria Phase 1 di PRD (seluruh transisi §10.3, rumus §11, dan test isolasi tenant):

Migrasi 0002: kolom attempt (started_at, deadline, paused_at, timer_mode, reopen_count, reinstate_count, termination_reason_category), plus tabel state_transitions, invigilator_assignments, device_sessions, commands, events, incidents, semuanya dengan RLS.
Attempt state engine: satu tabel transisi sebagai sumber tunggal, validasi atomik dengan row lock atau optimistic concurrency pada state_version, INVALID_TRANSITION untuk yang tidak terdaftar, reason_category wajib untuk TERMINATED.
Timing service: rumus deadline FIXED_END/FULL_DURATION, pause dengan KEEP_RUNNING/PAUSE_TIMER, add time individu, extend seluruh ujian.
Scheduler: READY → RUNNING, NO_SHOW, EXPIRED, INTERRUPTED dari heartbeat, RUNNING → CLOSED, aman bila server lebih dari satu instance (FOR UPDATE SKIP LOCKED atau advisory lock).
Izin invigilator yang terbatas pada ujian yang ditugaskan, dan endpoint aksi staf (pause, resume, add time, force submit, terminate, reopen, reinstate, re-entry, finalize).
Signing Ed25519 dan key set /.well-known/examguard-keys.json, client API (device session, EG-Sig, full state sync, upload event), WebSocket gateway, Integration API, dan webhook.
Karena ruang lingkupnya besar, usul saya Phase 1 dilanjutkan dalam dua tahap. Phase 1b mencakup butir 1–5, yaitu inti state machine dan timing yang bisa diuji penuh lewat API staf dan jam yang dibekukan. Phase 1c mencakup butir 6, yaitu protokol client, signing, WebSocket, dan Integration API. Dengan urutan ini, Phase 1c tinggal memanggil state engine yang sudah teruji, dan simulator headless di Phase 2 punya kontrak yang stabil.

Ada beberapa hal di kode 1a yang perlu diputuskan saat mengerjakan 1b:

Akomodasi waktu setelah attempt mulai. org_patch_enrollment saat ini bisa mengubah akomodasi kapan saja. Usul saya: setelah attempt ACTIVE, perubahan akomodasi tidak menggeser deadline secara otomatis. Tambahan waktu dilakukan eksplisit lewat Add Time agar tercatat sebagai UPDATE_DEADLINE.
Pembatalan enrollment oleh organisasi. org_cancel_enrollment sudah menolak attempt yang sudah mulai, jadi aman. Tapi undangan dan enrollment baru perlu ditolak juga saat exam sudah RUNNING.
Lingkungan pengujian. Sandbox saya tidak punya PostgreSQL bawaan. Untuk 1b saya akan memasang PostgreSQL di sandbox supaya seluruh test (termasuk test 1a) benar-benar dijalankan sebelum saya serahkan, bukan hanya ditulis.
Apakah pembagian 1b (state machine, timing, scheduler, invigilator, aksi staf) dan 1c (signing, client protocol, WebSocket, Integration API) ini sesuai dengan yang Anda bayangkan, atau Anda ingin Phase 1b langsung mencakup semuanya?

Oke saya ikut saran kamu saja sementara, tapi apakah perlu mengubah PRD agar keputusan ini terdokumentasikan?

Perlu, tapi cukup perubahan kecil. Tidak semua yang kita bahas termasuk keputusan produk, jadi yang masuk PRD hanya yang mengubah perilaku sistem atau rencana fase.

Yang sebaiknya masuk PRD:

§30.2 Development Phases. Baris Phase 1 dipecah menjadi 1a (tenancy, akun, ujian, registrasi, audit log, sudah selesai), 1b (state machine, timing, scheduler, penugasan invigilator, aksi staf), dan 1c (signing dan key set, client API, WebSocket, Integration API, webhook). Exit criteria Phase 1 secara keseluruhan tetap sama, hanya dibagi per sub-fase.
§32.1 Decision Log, dua entri baru:
Perubahan akomodasi waktu setelah attempt ACTIVE tidak menggeser deadline otomatis. Tambahan waktu dilakukan eksplisit lewat Add Time (UPDATE_DEADLINE) agar tercatat dengan aktor dan alasan. Ini juga perlu satu kalimat di §11.3.
Undangan dan enrollment baru ditolak setelah ujian RUNNING. §9 baru mengatur ini untuk ujian PUBLIC, belum untuk PRIVATE.
§0 Riwayat Perubahan. Tambah tabel singkat untuk revisi ini.
Yang tidak perlu masuk PRD: detail teknis seperti FOR UPDATE SKIP LOCKED untuk scheduler, struktur tabel migrasi 0002, atau cara test dijalankan. Itu cukup di README dan komentar kode.

Saran saya, beri nomor v0.3.1, bukan v0.4, karena tidak ada perubahan pada model produk, hanya klarifikasi dan pembagian fase. Nanti kalau Phase 1c memunculkan perubahan protokol yang lebih besar, baru naik ke v0.4.

Mau saya buatkan PRD v0.3.1 sekarang sebelum mulai Phase 1b, atau dikerjakan bersamaan dengan kode 1b supaya keputusan yang muncul saat implementasi bisa ikut dicatat sekalian?

Oke tolong ubah file PRD nya dulu


Ran a command
Ran a command
Now applying the edits.


Ran a command, shared files
Ran a command, shared files
PRD v0.3.1 sudah siap. Ada enam bagian yang berubah:

Header dan §0: versi naik ke 0.3.1. Ada tabel riwayat baru “v0.3 → v0.3.1”, dan riwayat lama dinomori ulang menjadi §0.2 dan §0.3.
§8.4: undangan hanya bisa dibuat saat exam DRAFT atau READY, dan hanya bisa diterima saat READY. Sejak RUNNING, undangan, import, dan pendaftaran via API ditolak. Aturan ini sesuai dengan perilaku kode 1a.
§9: ada tambahan kalimat untuk ujian PRIVATE sebagai pasangan aturan registrasi PUBLIC yang sudah ada.
§11.3: mengubah akomodasi setelah attempt dimulai tidak menggeser deadline. Nilai baru baru dipakai saat reopen atau reinstate berikutnya. Untuk attempt yang sedang berjalan, tambahan waktu diberikan lewat Add Time.
§30.2: Phase 1 dipecah menjadi 1a (ditandai ✓), 1b, dan 1c, masing-masing dengan deliverable dan exit criteria. Exit criteria Phase 1 secara keseluruhan tetap sama.
§32.1: ada tiga keputusan baru. Q12 tentang akomodasi, Q13 tentang enrollment setelah ujian berjalan, dan Q14 tentang pembagian Phase 1.
Ada satu detail di §11.3 yang saya tambahkan di luar pembahasan kita: akomodasi yang diubah tetap dipakai saat attempt di-reopen atau di-reinstate, karena kedua aksi itu menghitung deadline baru. Kalau Anda lebih suka reopen/reinstate selalu memakai deadline yang diinput manual oleh admin (sesuai §27.7), kalimat itu bisa saya hapus.

Kalau sudah oke, kita lanjut ke Phase 1b.

ExamGuard PRD v0 3 1
Document
·MD
Oke mari kita lanjutkan phase 1b


Ran a command
Ran a command
Now let me set up PostgreSQL in the sandbox and confirm the Phase 1a tests pass as a baseline.


Ran 4 commands
Ran 4 commands
Baseline: 52 tests Phase 1a lulus. Sekarang migrasi 0002.


Ran 3 commands, created 2 files
Ran 3 commands, created 2 files
Now the state engine core — the transition table as single source of truth.


Created 7 files, ran 7 commands
Created 7 files, ran 7 commands
1a tests still green on the new migration. Now the test harness for 1b.


Ran 3 commands
Ran 3 commands
Matrix of all 12×18 status/trigger pairs passes against the real DB. Now the client-flow tests.


Ran 4 commands
Ran 4 commands
The logic is right; the test itself went silent for 10 minutes before its “last” heartbeat, which correctly produced WAITING. Fixing the test.


Ran 3 commands
Ran 3 commands
Three test mistakes (a too-short reason, my own arithmetic, UUIDs in JSON). Fixing them:


Ran a command
Ran a command
Now access control and tenant isolation for the new tables.


Ran 2 commands
Ran 2 commands
Semua test 1b lulus. Sekarang CLI: scheduler, serve --with-scheduler, simulator sim, dan data demo yang bisa langsung dicoba.


Ran a command
Ran a command
Removing a leftover dead line I wrote in sim attempts:


Ran 2 commands
Ran 2 commands
Now an end-to-end manual run through the CLI, like you would on Windows: bootstrap → migrate → seed → serve with scheduler → simulated candidates.


Ran 2 commands
Ran 2 commands
Berjalan. Tapi error di CLI tampil sebagai traceback; saya rapikan jadi pesan satu baris.


Ran 2 commands
Ran 2 commands
The background server didn’t survive between my tool calls (sandbox limitation). First, a UX fix: sim launch on an already active attempt should not silently act as a device change.


Ran 5 commands
Ran 5 commands
113 test lulus (52 dari 1a + 61 baru). Sekarang OpenAPI, README, dan PRD.


Ran a command
Ran a command
Phase 1b sudah selesai diimplementasikan dan diuji, tetapi belum saya kemas menjadi zip. Saya kehabisan batas langkah untuk respons ini sebelum sempat membuat zip, memperbarui README dan PRD, lalu menyerahkan file. Balas “lanjut” dan saya kerjakan tiga hal itu di respons berikutnya. Kodenya masih ada di sandbox.

Status pengujian. Ada 113 test yang lulus di PostgreSQL 16 sungguhan: 52 test lama dari 1a ditambah 61 test baru. Saya juga menjalankan skenario manual lewat CLI dan HTTP di port 8080, dengan urutan: bootstrap, migrasi, seed, server dengan scheduler, launch peserta simulasi, pause/add-time/extend oleh pengawas dan exam admin, lalu peserta terputus. Hasilnya: scheduler menandai INTERRUPTED setelah 60 detik, heartbeat berikutnya memicu auto-resume, dan audit chain tetap valid.

Yang dibangun di Phase 1b:

Migrasi 0002. Kolom timing di attempt dan tabel state_transitions (append-only), device_sessions, commands (outbox untuk 1c), dan invigilator_assignments, semuanya dengan RLS. Trigger database menolak perubahan status atau deadline yang tidak menaikkan state_version tepat satu.
State engine. Tabel transisi di state.py jadi satu-satunya sumber kebenaran. Test mencocokkannya dengan tabel §10.3 yang saya tulis ulang terpisah, lalu mencoba seluruh 12 status × 18 trigger langsung ke database.
Timing. Rumus §11.2, pause dengan KEEP_RUNNING/PAUSE_TIMER, add time, dan extend seluruh ujian.
Scheduler. Menangani READY→RUNNING, NO_SHOW, EXPIRED, INTERRUPTED (dengan threshold per ujian), dan RUNNING→CLOSED. Aman dijalankan multi-instance karena memakai SKIP LOCKED, dan ini ada test-nya.
Invigilator. Izin terbatas pada ujian yang ditugaskan. Terminate massal, extend, reopen/reinstate, dan finalize hanya untuk Exam Admin.
API staf. 20 endpoint baru: live monitoring, detail peserta dengan tombol aksi yang valid, re-entry, identity approve/reject, bulk, extend, dan finalize. Opsi expected_state_version mencegah dua pengawas bertindak atas status yang sudah berubah. Ada test konkurensi dengan 4 thread yang hasilnya tepat satu berhasil.
CLI. Perintah examguard scheduler run, serve --with-scheduler, dan grup examguard sim (launch, heartbeat, submit, identity) untuk mencoba alur client sebelum simulator Phase 2. seed demo sekarang juga membuat ujian DEMO-LIVE yang mulai beberapa menit lagi, dengan satu pengawas dan tiga peserta.
Tiga keputusan implementasi yang belum tertulis di PRD. Ketiganya akan saya catat di PRD.

Transisi ACTIVE → WAITING_FOR_INVIGILATOR saat pindah perangkat. §18 mewajibkan persetujuan untuk perangkat baru, tetapi tabel §10.3 hanya punya jalur dari INTERRUPTED. Saya menambahkan jalur dari ACTIVE. Pendaftaran perangkat baru saat attempt PAUSED ditolak sampai pengawas melanjutkan ujian.
Extend seluruh ujian juga berlaku untuk peserta yang baru mulai setelahnya. Tambahan waktunya disimpan sebagai extension_minutes di ujian.
Perubahan deadline tanpa perubahan status tetap menaikkan state_version. Tanpa ini, client tidak bisa mengurutkan UPDATE_DEADLINE.
Ada juga satu koreksi atas kalimat yang saya tambahkan sendiri di §11.3 v0.3.1. Deadline reopen/reinstate diinput eksplisit oleh admin sesuai §27.7, jadi tidak dihitung dari akomodasi. Kalimat itu akan saya perbaiki.

Catatan untuk laptop Windows Anda: instal ulang paketnya (pip install -e ".[dev]") karena entry point CLI berubah, lalu jalankan examguard db upgrade untuk menerapkan migrasi 0002 ke database Docker yang sudah ada.

Continue


Ran a command
Ran a command
Kode masih utuh. Sekarang README:


Ran a command
Ran a command
Sekarang PRD v0.3.1 (masih draft dari sesi ini, jadi saya perbarui file yang sama dan catat di riwayatnya), lalu kemas zip:


Ran a command
Ran a command
Verifikasi terakhir: ekstrak zip ke folder bersih, instal, lalu jalankan seluruh test dari isi zip.


Ran 2 commands
Ran 2 commands
Bukan masalah kode: PostgreSQL di sandbox berhenti sejak sesi sebelumnya. Nyalakan ulang dan uji lagi dari isi zip:


Ran a command, shared files
Ran a command, shared files
Phase 1b sudah dikemas dalam zip. Saya mengekstrak zip itu ke folder kosong, menginstalnya, lalu menjalankan seluruh test dari sana: 113 passed.

Menerapkan di laptop Anda (Docker Postgres dan venv yang sudah ada):

bash
pip install -e ".[dev]"      # wajib, karena entry point CLI berubah
examguard db upgrade         # menerapkan migrasi 0002; data 1a tetap utuh
examguard serve --port 8080 --with-scheduler
Untuk mencoba alur 1b dengan data demo baru, reset dulu databasenya dengan db bootstrap --drop-existing, lalu jalankan db upgrade dan seed demo. Setelah itu:

bash
examguard sim launch    --exam DEMO-LIVE --email peserta1@demo.example.com
examguard sim heartbeat --exam DEMO-LIVE --email peserta1@demo.example.com --count 0
Ujian DEMO-LIVE dimulai 5 menit setelah seed. Semua jam di CLI ditampilkan dalam UTC, jadi tambahkan 7 jam untuk WIB. Aksi pengawas bisa dicoba lewat /docs dengan login pengawas@pt-contoh-jaya.demo.example.com. Langkah lengkapnya ada di README bagian “Mencoba Phase 1b tanpa client”.

Perubahan di README: ada bagian upgrade dari 1a, tabel isi 1b, tabel 20 endpoint baru beserta izinnya, panduan sim, dan daftar batasan yang sudah disadari. Batasan yang terpenting: command masih berstatus PENDING dan foto identity check belum disimpan. Keduanya menunggu Phase 1c.

Perubahan di PRD v0.3.1. File ini masih draft dari sesi ini, jadi saya perbarui file yang sama dan semua perubahannya tercatat di tabel riwayat §0.1:

§10.3: tambah baris transisi ACTIVE → WAITING_FOR_INVIGILATOR untuk pindah perangkat. Ada juga aturan baru bahwa perubahan deadline tetap menaikkan state_version.
§11.3: kalimat soal reopen/reinstate diperbaiki. Deadline-nya diinput admin sesuai §27.7, tidak dihitung dari akomodasi. Ditambah aturan bahwa extend juga berlaku untuk peserta yang mulai belakangan.
§18: tiga aturan device session baru. Sebelum mulai, perangkat bebas diganti. Saat PAUSED, pendaftaran perangkat baru ditolak. Restart di perangkat yang sama tidak dihitung sebagai pindah perangkat.
§30.2 dan §32.1: Phase 1b ditandai selesai (✓), dan ada keputusan baru Q15 dan Q16.
Langkah berikutnya adalah Phase 1c: signing Ed25519 dan key set, endpoint client bertanda tangan yang membungkus client_flow, WebSocket untuk mengirim command dari outbox, event dan incident, serta Integration API dan webhook.

Examguard server phase1b
ZIP
ExamGuard PRD v0 3 1
Document
·MD
Pada fase ini berarti berarti masih mengenai web nya ya? Belum aplikasi browsernya ya?

Betul, belum menyentuh aplikasi browsernya. Bahkan lebih sempit lagi: Phase 1a sampai 1c semuanya server backend, yaitu API dan database saja, belum ada halaman web. Yang bisa Anda lihat sekarang hanya halaman /docs bawaan FastAPI untuk mencoba API, ditambah CLI.

Urutan lengkapnya di PRD §30.2:

Phase	Komponen	Bentuknya
1a–1c	ExamGuard Server	API, database, scheduler, protokol (sedang dikerjakan, tinggal 1c)
2	Headless Client Simulator	Kode Rust pertama, tanpa tampilan: launch, heartbeat, command, recovery
3	Admin Web & Candidate Portal	Halaman web pertama (dashboard pengawas, portal peserta)
4	Reference Exam Website	Website soal ujian
5	Client Foundation	Aplikasi browser Rust + CEF mulai dibangun
6	Lockdown Adapters	Penguncian per OS (Windows, macOS, Linux)
7	Proctoring	Kamera, mikrofon, model ONNX
8	Recovery & Hardening	Keystore OS, anti-tampering, installer bertanda tangan
Server dikerjakan lebih dulu karena ia adalah kontrak yang dipakai semua komponen lain. Client, Admin Web, dan website ujian sama-sama bergantung pada aturan status, waktu, dan protokol yang ditetapkan server. Kalau aplikasi browser dibangun duluan, aturan itu harus ditebak di sisi client lalu diubah lagi saat server jadi. Selain itu, server bisa diuji penuh tanpa perangkat fisik, sedangkan lockdown dan proctoring butuh pengujian di tiap OS.

Phase 2 menjadi jembatannya. Simulator Rust tanpa tampilan itu bukan kode buangan. Modul protokol, verifikasi signature, heartbeat, dan recovery-nya nanti dipakai langsung oleh aplikasi browser di Phase 5, sehingga Phase 5 tinggal fokus pada CEF, tampilan, dan lockdown.

Urutan ini tidak harus kaku. Kalau Anda ingin segera melihat sesuatu yang bisa diklik, misalnya untuk demo ke atasan atau tim, Phase 3 (Admin Web) bisa dikerjakan sebelum Phase 2, karena API-nya sudah cukup lengkap setelah 1c. Yang tidak saya sarankan adalah memulai aplikasi browser (Phase 5) sebelum 1c selesai, karena protokol client ↔ server baru ditetapkan di 1c.

Oh baik. Kemudian untuk phase 1b ini kan perlu perintah "pip install -e ".[dev]"", ini perlu uninstall examguard yang sebelumnya dulu atau tidak?

Tidak perlu uninstall. pip install -e akan menimpa instalasi lama dengan versi baru (0.1.0a2), termasuk entry point examguard yang berubah.

Ada tiga hal yang perlu diperhatikan di Windows:

Hentikan server dulu. Kalau examguard serve masih jalan, file examguard.exe di venv sedang dipakai, dan pip di Windows gagal menimpanya dengan error “Access is denied”. Tekan Ctrl+C di terminal server sebelum menginstal.
Salin file .env Anda. File .env tidak ada di dalam zip. Kalau zip diekstrak ke folder baru, salin .env dari folder Phase 1a ke folder baru. Isinya pengaturan password database Docker Anda. Tanpa file itu, CLI memakai nilai default dan bisa gagal konek.
Pakai venv yang sama. Aktifkan venv lama, lalu jalankan pip dari dalam folder baru. pip otomatis mengarahkan instalasi ke folder baru, dan folder lama boleh dihapus setelahnya.
Urutannya:

bash
# (hentikan server dulu dengan Ctrl+C)
cd path\ke\examguard-server        # folder hasil ekstrak zip Phase 1b
copy ..\folder-lama\.env .env      # jika diekstrak ke folder baru
path\ke\venv\Scripts\activate
pip install -e ".[dev]"
examguard db upgrade
Untuk memastikan yang terpasang sudah versi baru:

bash
pip show examguard-server   # Version: 0.1.0a2, Location mengarah ke folder baru
examguard --help            # harus muncul perintah "scheduler" dan "sim"
Kalau scheduler dan sim sudah muncul di --help, instalasi sudah benar dan Anda bisa lanjut ke examguard serve --port 8080 --with-scheduler.

Waduh saya salah delete environment saya yang tadi, langkahnya seperti apa kalau install dari awal lagi tapi dari phase 1b langsung

Tenang, kemungkinan besar datanya aman. Database Anda ada di container Docker, bukan di venv. Yang hilang hanya instalasi Python-nya, dan itu tinggal dibuat ulang.

Langkah di bawah memakai PowerShell. Jalankan dari folder hasil ekstrak zip Phase 1b.

1. Pastikan PostgreSQL di Docker masih jalan

powershell
docker ps -a
Kalau container Postgres ada tapi statusnya Exited, nyalakan dengan docker start <nama-container>. Kalau container-nya ikut terhapus, lihat bagian terakhir.

2. Buat venv baru dan instal

powershell
cd path\ke\examguard-server
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
Kalau PowerShell menolak menjalankan Activate.ps1, jalankan sekali Set-ExecutionPolicy -Scope CurrentUser RemoteSigned lalu ulangi aktivasinya.

3. Siapkan file .env

Kalau file .env lama masih ada, salin ke folder ini. Kalau ikut terhapus, buat dari contohnya:

powershell
copy .env.example .env
Buka .env lalu isi password untuk examguard_owner dan examguard_app. Boleh password baru, karena langkah 4 akan menyetelnya ulang.

4. Hubungkan ke database

Jalankan bootstrap, lalu upgrade:

powershell
examguard db bootstrap --superuser-url postgresql://postgres:PASSWORD_POSTGRES@127.0.0.1:5432/postgres
examguard db upgrade
PASSWORD_POSTGRES adalah password superuser yang Anda pakai saat membuat container Docker (POSTGRES_PASSWORD).
bootstrap aman dijalankan ulang. Perintah ini menyetel password kedua role sesuai .env dan tidak menghapus data. Jadi kalau .env Anda baru, role lama ikut menyesuaikan.
upgrade menerapkan migrasi 0002 dari Phase 1b ke database lama Anda.
Kalau ingin mulai dari database kosong supaya bisa mencoba ujian DEMO-LIVE, gunakan ini sebagai pengganti:

powershell
examguard db bootstrap --superuser-url postgresql://postgres:PASSWORD_POSTGRES@127.0.0.1:5432/postgres --drop-existing
examguard db upgrade
examguard seed demo
5. Cek dan jalankan

powershell
examguard --help        # harus ada perintah "scheduler" dan "sim"
examguard serve --port 8080 --with-scheduler
Opsional, untuk memastikan semuanya benar di laptop Anda (makan waktu sekitar 2–3 menit):

powershell
$env:EXAMGUARD_TEST_SUPERUSER_URL = "postgresql://postgres:PASSWORD_POSTGRES@127.0.0.1:5432/postgres"
pytest
Hasilnya harus 113 passed. Test memakai database terpisah (examguard_test), jadi data Anda tidak tersentuh.

Kalau container Docker ikut terhapus, buat ulang dulu sebelum langkah 4:

powershell
docker run -d --name examguard-pg -e POSTGRES_PASSWORD=PASSWORD_POSTGRES -p 5432:5432 postgres:16
Setelah itu pakai versi --drop-existing dan seed demo di langkah 4, karena databasenya memang baru.

Kok muncul error ya:

(examguard_env) C:\Users\User\Downloads\ExamGuard\examguard-server>examguard db bootstrap --superuser-url postgresql://postgres:PASSWORD_POSTGRES@127.0.0.1:5432/postgres
╭───────────────────────────────────────── Traceback (most recent call last) ──────────────────────────────────────────╮
│ C:\Users\User\Downloads\ExamGuard\examguard-server\src\examguard\cli.py:77 in db_bootstrap                           │
│                                                                                                                      │
│    74 │   if app_["user"] != s.app_role:                                                                             │
│    75 │   │   _fail("EXAMGUARD_APP_ROLE must match the user in EXAMGUARD_DATABASE_URL")                              │
│    76 │   dbname = owner["dbname"]                                                                                   │
│ ❱  77 │   with psycopg.connect(superuser_url.replace("+psycopg", ""), autocommit=True) as c:                         │
│    78 │   │   if drop_existing:                                                                                      │
│    79 │   │   │   if not s.is_dev:                                                                                   │
│    80 │   │   │   │   _fail("--drop-existing is only allowed with EXAMGUARD_ENV=dev")                                │
│                                                                                                                      │
│ C:\Users\User\Downloads\ExamGuard\examguard-server\examguard_env\Lib\site-packages\psycopg\connection.py:126 in      │
│ connect                                                                                                              │
│                                                                                                                      │
│   123 │   │   if not rv:                                                                                             │
│   124 │   │   │   last_ex = conn_errors[-1][0]                                                                       │
│   125 │   │   │   if len(conn_errors) == 1:                                                                          │
│ ❱ 126 │   │   │   │   raise last_ex.with_traceback(None)                                                             │
│   127 │   │   │                                                                                                      │
│   128 │   │   │   # Create a new exception with the same type as the last one, containing                            │
│   129 │   │   │   # all attempt errors while preserving backward compatibility.                                      │
╰──────────────────────────────────────────────────────────────────────────────────────────────────────────────────────╯
OperationalError: connection failed: connection to server at "127.0.0.1", port 5432 failed: FATAL:  password
authentication failed for user "postgres"

Penyebabnya: PASSWORD_POSTGRES di perintah saya hanya contoh. Perintah itu harus diisi password superuser postgres yang Anda set saat membuat container Docker. Postgres menolak karena menerima tulisan “PASSWORD_POSTGRES” apa adanya sebagai password.

1. Cari password dan port container Anda. Di Command Prompt:

bat
docker ps
Catat nama container Postgres (kolom NAMES) dan port-nya (kolom PORTS, misalnya 0.0.0.0:5432->5432/tcp). Setelah itu tampilkan environment container tersebut:

bat
docker inspect NAMA_CONTAINER --format "{{range .Config.Env}}{{println .}}{{end}}"
Cari baris POSTGRES_PASSWORD=.... Nilai setelah tanda = itulah password-nya.

2. Jalankan ulang dengan password asli:

bat
examguard db bootstrap --superuser-url postgresql://postgres:PASSWORD_ASLI@127.0.0.1:5432/postgres
examguard db upgrade
Kalau port di docker ps bukan 5432 (misalnya 5433->5432), ganti 5432 di URL dengan port sebelah kiri tanda panah. Ganti juga port di kedua URL dalam .env.

Dua kemungkinan lain kalau masih gagal:

Password mengandung karakter khusus seperti @ : / # %. Karakter itu merusak URL, jadi harus di-encode: @ → %40, : → %3A, / → %2F, # → %23, % → %25. Contoh: password rahasia@123 ditulis rahasia%40123.
Password di POSTGRES_PASSWORD sudah pernah diganti setelah container pertama kali dibuat. Postgres hanya membaca variabel itu saat database diinisialisasi pertama kali. Kalau Anda tidak ingat password yang sekarang, reset langsung dari dalam container:
bat
docker exec -it NAMA_CONTAINER psql -U postgres -c "ALTER USER postgres PASSWORD 'passwordbaru'"
Perintah ini bisa jalan tanpa password karena koneksi dari dalam container biasanya dipercaya. Setelah itu pakai passwordbaru di --superuser-url.

Error koneksi database memang masih tampil sebagai traceback panjang, karena CLI baru merapikan error bisnis. Di Phase 1c akan saya ubah menjadi satu baris, misalnya “tidak bisa terhubung ke database: password salah untuk user postgres”.

Oke sudah bisa jalan. Rupanya masalahnya di passwordnya yang salah. Sekarang saya coba perintah ini :

examguard sim launch --exam DEMO-LIVE --email peserta1@demo.example.com

Dapat error seperti ini: "no matching attempt". Itu solusinya apa ya?

Kemungkinan besar ujian DEMO-LIVE belum ada di database Anda. Ujian itu baru ditambahkan ke seed demo di Phase 1b. Database Anda adalah database lama dari Phase 1a yang sudah berisi data demo 1a, jadi:

bootstrap + upgrade tadi hanya menambah tabel baru, tidak menambah data.
Kalau Anda menjalankan seed demo, perintahnya berhenti dengan pesan demo data already present karena organisasi demo dari 1a sudah ada. Akibatnya DEMO-LIVE tidak pernah dibuat.
Untuk memastikannya:

bat
examguard sim attempts --exam DEMO-LIVE
Kalau tidak keluar apa-apa, berarti memang belum ada.

Solusinya, reset database lalu seed ulang:

bat
examguard db bootstrap --superuser-url postgresql://postgres:PASSWORD_ASLI@127.0.0.1:5432/postgres --drop-existing
examguard db upgrade
examguard seed demo --live-in-minutes 2
--drop-existing menghapus seluruh isi database examguard. Kalau isinya hanya data demo dari 1a, ini aman.

Sesudah seed, baris terakhir outputnya menampilkan jadwal, misalnya:

DEMO-LIVE: check-in 02:10, start 02:40 UTC (latest start 03:10)
Jamnya dalam UTC, jadi tambahkan 7 jam untuk WIB. Setelah itu:

Jalankan server dengan scheduler: examguard serve --port 8080 --with-scheduler
Di terminal lain (aktifkan venv dulu), tunggu sampai jam start lewat, lalu:
bat
examguard sim launch --exam DEMO-LIVE --email peserta1@demo.example.com
Dua error yang mungkin muncul:

START_NOT_YET_ALLOWED: jam mulai belum tiba. Tunggu sebentar lalu ulangi.
LATE_START_CLOSED: sudah lewat 30 menit dari jam mulai. Peserta dianggap tidak hadir (NO_SHOW) dan DEMO-LIVE tidak bisa dipakai lagi. Jalankan ulang ketiga perintah reset di atas untuk mendapat jadwal baru.
Karena DEMO-LIVE cepat kedaluwarsa, reset berulang untuk mencoba lagi memang agak repot. Kalau Anda mau, di Phase 1c saya bisa menambahkan perintah examguard seed live-exam yang membuat ujian demo baru kapan saja tanpa menghapus database.

Setelah mengikuti arahan kamu sekarang sudah bisa jalan:

(examguard_env) C:\Users\User\Downloads\ExamGuard\examguard-server>examguard seed demo --live-in-minutes 2
demo data created; all accounts use the given password
  platform@demo.example.com
  admin@public.demo.example.com
  exams@examguard-public.demo.example.com
  hr@contohjaya.demo.example.com
  exams@pt-contoh-jaya.demo.example.com
  pengawas@pt-contoh-jaya.demo.example.com  (INVIGILATOR, assigned to DEMO-LIVE)
  peserta1..3@demo.example.com  (candidates enrolled in DEMO-LIVE)
DEMO-LIVE: check-in 19:45, start 20:15 UTC (latest start 20:45)

Seed sudah berhasil. Jadwalnya dalam WIB: check-in 02:45, mulai 03:15, batas mulai terakhir 03:45. Sampai 03:15 peserta hanya bisa check-in, belum bisa start.

Berikut skenario uji singkat yang mencakup fitur utama Phase 1b.

Persiapan: dua terminal, keduanya dengan venv aktif.

Terminal A (server + scheduler): examguard serve --port 8080 --with-scheduler
Terminal B: untuk perintah examguard sim
1. Peserta mulai ujian (setelah 03:15 WIB, di terminal B)

bat
examguard sim launch --exam DEMO-LIVE --email peserta1@demo.example.com
examguard sim launch --exam DEMO-LIVE --email peserta2@demo.example.com
examguard sim attempts --exam DEMO-LIVE
Perintah terakhir menampilkan attempt_id tiap peserta. Catat, karena dipakai di /docs.

2. Buka tampilan pengawas di http://127.0.0.1:8080/docs

POST /api/v1/staff/auth/login dengan email pengawas@pt-contoh-jaya.demo.example.com dan password demo-password-123. Salin nilai token dari hasilnya.
GET /api/v1/staff/me: isi kolom authorization dengan Bearer TOKEN_TADI, lalu catat org_id dari hasilnya.
GET /api/v1/org/exams: isi authorization dan X-Org-Id, lalu catat id ujian DEMO-LIVE.
GET /api/v1/org/exams/{exam_id}/attempts: ini tampilan Live Monitoring.
Setiap endpoint di /docs meminta kolom authorization dan X-Org-Id diisi ulang. Agak repot, tapi cukup untuk menguji. Admin Web di Phase 3 yang nanti mengurus ini otomatis.

3. Pause dengan timer berhenti

POST /api/v1/org/attempts/{attempt_id}/pause untuk peserta2, dengan body:

json
{"reason": "cek ruangan", "timer_mode": "PAUSE_TIMER"}
Tunggu 2–3 menit, lalu POST .../resume dengan body {"reason": "lanjut"}. Deadline peserta2 di hasil resume akan mundur sebesar lama pause.

4. Peserta terputus lalu tersambung lagi

Di terminal B, jalankan heartbeat terus-menerus untuk peserta1:

bat
examguard sim heartbeat --exam DEMO-LIVE --email peserta1@demo.example.com --count 0
Lalu hentikan dengan Ctrl+C dan tunggu lebih dari 60 detik. Live Monitoring akan menampilkan peserta1 sebagai INTERRUPTED / OFFLINE. Jalankan perintah heartbeat itu lagi: statusnya kembali ACTIVE otomatis, karena jedanya di bawah 10 menit. Riwayatnya bisa dilihat di GET /api/v1/org/exams/{exam_id}/reentry.

5. Pindah perangkat

bat
examguard sim launch --exam DEMO-LIVE --email peserta1@demo.example.com --new-device
Status peserta1 menjadi WAITING_FOR_INVIGILATOR. Setujui lewat POST .../attempts/{attempt_id}/reentry/allow dengan body {"reason": "laptop rusak"}.

6. Selesai dan tidak hadir

bat
examguard sim submit --exam DEMO-LIVE --email peserta1@demo.example.com
peserta3 sengaja tidak di-launch. Setelah 03:45 WIB, scheduler otomatis mengubahnya menjadi NO_SHOW.

7. Cek izin per role

Coba POST /api/v1/org/exams/{exam_id}/extend memakai token pengawas. Hasilnya harus 403, karena hanya Exam Admin yang boleh. Ulangi dengan token exams@pt-contoh-jaya.demo.example.com dan hasilnya berhasil.

Riwayat lengkap tiap peserta (semua transisi, device session, dan command) bisa dilihat di GET /api/v1/org/attempts/{attempt_id}.

Untuk api/v1/staff/auth/login, saya dapat hasil seperti ini:

{
  "token": "3cb9nNYcHKyn3TxeqPFBfBVsBR7SIijbIdaf6ufXVzU",
  "kind": "STAFF",
  "expires_at": "2026-09-29T08:22:00.097784Z"
}

Kemudian, saya coba ke api/v1/staff/me, di isian authorization saya isi dengan "Bearer 3cb9nNYcHKyn3TxeqPFBfBVsBR7SIijbIdaf6ufXVzU", tapi responnya kok:

{
  "error": {
    "code": "UNAUTHORIZED",
    "message": "missing, invalid or expired session"
  }
}

dengan kode 401

Ini kesalahan dari sisi saya, bukan dari cara Anda mengisi. Swagger UI (halaman /docs) sengaja tidak mengirim header bernama Authorization yang diisi lewat kolom parameter biasa. Ini aturan spesifikasi OpenAPI. Jadi token Anda tidak pernah sampai ke server. Test otomatis saya tidak menangkap ini karena memanggil API langsung, bukan lewat /docs.

Perbaikannya: API perlu mendeklarasikan skema keamanan, supaya /docs menampilkan tombol Authorize dan mengirim header dengan benar. Saya perbaiki sekarang.


Ran 3 commands
Ran 3 commands
Semua 115 test lulus (113 lama + 2 baru), dan pemanggilan HTTP sungguhan berhasil. Sekarang saya kemas ulang:


Ran a command, shared files
Ran a command, shared files
Perbaikannya sudah selesai. Karena yang berubah hanya satu file, cara paling cepat adalah mengganti file itu saja. Tidak perlu pip install ulang, dan database tidak tersentuh.

Menerapkan perbaikan:

Hentikan server (Ctrl+C di terminal A).
Timpa src\examguard\api\deps.py di folder proyek Anda dengan file deps.py di bawah.
Jalankan lagi: examguard serve --port 8080 --with-scheduler
Zip lengkapnya juga saya perbarui, untuk dipakai sebagai salinan utuh di sesi berikutnya. Isinya perbaikan ini, 2 test baru (total 115 lulus), dan README yang sudah menjelaskan cara memakai /docs.

Cara memakai /docs sekarang:

POST /api/v1/staff/auth/login, lalu salin token dari hasilnya.
Klik tombol Authorize (ikon gembok) di kanan atas halaman.
Di kotak SessionToken, tempel token saja, tanpa kata Bearer. Klik Authorize.
Jalankan GET /api/v1/staff/me, lalu salin org_id dari hasilnya.
Buka Authorize lagi, isi kotak OrgId dengan org_id tadi, lalu klik Authorize.
Setelah itu token dan organisasi terkirim otomatis ke semua endpoint. Kolom authorization dan X-Org-Id per endpoint juga sudah tidak ada. Langkah uji dari pesan saya sebelumnya tetap berlaku, cukup lewati bagian “isi kolom authorization dan X-Org-Id”.

Token Anda yang tadi masih berlaku sampai 08:22 UTC (15:22 WIB), jadi setelah server dijalankan ulang bisa langsung dipakai di Authorize tanpa login ulang.

Deps
PY
Examguard server phase1b
ZIP
Oke sudah bisa. Kemudian untuk menggunakan api ini bagaimana?

GET /api/v1/org/exams/{exam_id}/attempts

Dari mana saya dapat exam_id dan ini rupanya butuh "status" juga. Isiannya dari mana?

exam_id didapat dari endpoint daftar ujian:

Jalankan GET /api/v1/org/exams. Tidak perlu isian apa pun, karena token dan organisasi sudah dikirim lewat Authorize.
Di hasilnya, cari ujian dengan "code": "DEMO-LIVE", lalu salin nilai "id"-nya:
json
[
  {
    "id": "2ffd29b6-039a-494e-9520-2cd6ceef6578",   ← ini exam_id
    "code": "DEMO-LIVE",
    "name": "Demo Ujian Langsung",
    "status": "RUNNING",
    ...
  }
]
Login sebagai pengawas hanya menampilkan DEMO-LIVE, karena pengawas hanya melihat ujian yang ditugaskan kepadanya. Kalau login sebagai Exam Admin, semua ujian organisasi ikut muncul.

status boleh dikosongkan. Kolom ini hanya filter opsional; Swagger memang menampilkan semua kolom, tapi yang wajib hanya yang bertanda * required. Kalau dikosongkan, semua peserta ditampilkan, dan itu tampilan Live Monitoring yang biasa dipakai.

Kalau diisi, hanya peserta dengan status itu yang tampil. Contoh yang berguna:

Isi status	Kegunaan
WAITING_FOR_INVIGILATOR	Peserta yang menunggu persetujuan masuk kembali
INTERRUPTED	Peserta yang sedang terputus
PAUSED	Peserta yang sedang dijeda
NOT_STARTED	Peserta yang belum mulai
Pilihan lainnya: ACTIVE, SUBMITTED, EXPIRED, TERMINATED, NO_SHOW, REOPENED, REINSTATED, FINALIZED. Penulisannya harus persis dengan huruf besar.

Membaca hasilnya:

summary berisi jumlah peserta per status, ditambah ONLINE/OFFLINE. Ini angka ringkasan di bagian atas layar Live Monitoring.
attempts berisi satu baris per peserta. Yang paling sering dipakai:
attempt_id: dipakai untuk aksi seperti pause, add-time, atau detail.
status dan connection_status.
remaining_seconds: sisa waktu dalam detik. Angkanya berhenti berkurang saat peserta di-pause dengan PAUSE_TIMER.
state_version: bisa diisikan ke expected_state_version saat melakukan aksi, supaya aksi ditolak kalau status peserta sudah berubah sejak Anda melihatnya.
Jadi attempt_id untuk langkah pause, resume, dan reentry di skenario uji bisa diambil dari sini. Tidak perlu lagi lewat examguard sim attempts.

Menurut saya sudah oke. Lanjut ke selanjutnya.

Phase 1c adalah fase terbesar di server, jadi saya kerjakan bertahap. Setiap tahap diakhiri zip yang sudah teruji, supaya tidak terulang kejadian Phase 1b yang terpotong sebelum sempat dikemas. Pertama, saya baca ulang bagian protokol di PRD.


Ran 6 commands
Ran 6 commands
Sekarang migrasi 0003.


Ran a command
Ran a command
Sekarang modul kriptografi dan manajemen kunci (§19).


Ran 2 commands, created a file
Ran 2 commands, created a file
Sekarang layanan protokol inti: launch token, Signed Exam Config, autentikasi EG-Sig, state bertanda tangan, command, event/incident, dan attestation.


Ran 3 commands, created 2 files
Ran 3 commands, created 2 files
Sekarang CLI untuk kunci (examguard keys ...), dan seed demo otomatis menyiapkan kunci dev.


Ran a command
Ran a command
Sekarang harness test: referensi client Python kecil yang menandatangani request persis seperti client Rust nanti. Ini sekaligus menjadi dokumentasi protokol yang bisa dieksekusi.


Ran 3 commands
Ran 3 commands
Postgres di sandbox berhenti lagi di antara sesi. Nyalakan ulang, lalu jalankan:


Ran 2 commands
Ran 2 commands
Semua lulus, termasuk test regresi untuk kasus check-in tadi. Jalankan seluruh suite dan lint:


Ran a command
Ran a command
131 test lulus. Rapikan dua catatan lint, lalu uji end-to-end lewat server sungguhan (uvicorn + WebSocket asli), memakai referensi client terhadap seed demo yang kini otomatis membuat kunci:


Ran 2 commands
Ran 2 commands
Kemas zip, lalu verifikasi dari hasil ekstrak ke folder bersih:


Ran a command, shared files
Ran a command, shared files
Phase 1c-1 sudah selesai dan dikemas. Saya mengekstrak zip ke folder bersih lalu menjalankan seluruh test dari sana: 131 passed. Saya juga menguji lewat server sungguhan (uvicorn dan WebSocket asli): perintah pause dari pengawas sampai ke client dalam 0,8 detik, bertanda tangan dan terverifikasi.

Isi Phase 1c-1:

Kunci (§19): kunci server Ed25519 dengan satu kid per kegunaan (command, state, config, token). Daftar kunci publik di /.well-known/examguard-keys.json ditandatangani root key. Root key tidak pernah disimpan di server; rotasi dan pencabutan lewat examguard keys.
Launch (§12): Candidate Portal mendapat endpoint untuk membuat link examguard://launch?t=… (sekali pakai, 15 menit). Client menukarnya dengan Signed Exam Config.
Autentikasi client (§18): client mendaftarkan public key-nya, lalu setiap request berikutnya ditandatangani (EG-Sig). Server menolak tanda tangan salah, jam meleset lebih dari 60 detik, body yang diubah, dan sesi yang sudah dicabut.
State dan command (§17): status attempt dikirim dalam bentuk bertanda tangan. Command dari outbox Phase 1b kini ditandatangani dan dikirim lewat WebSocket, atau lewat HTTPS sebagai cadangan. ACK tercatat.
Event dan incident (§15): upload event per batch, aman diulang. Incident dibuat otomatis sesuai Event Dictionary, dan event OPEN/CLOSE digabung menjadi satu incident. Reconnect setelah jeda mencatat UNMONITORED_INTERRUPTION.
Attestation (§16.2): token JWT 5 menit untuk website ujian.
Satu bug nyata yang tertangkap test dan sudah diperbaiki. Peserta yang check-in 30 menit lebih awal lalu menekan mulai langsung masuk WAITING, karena server masih mengukur jeda dari waktu registrasi. Sekarang request start yang bertanda tangan dihitung sebagai tanda client masih hidup, dan ada test regresinya.

Dokumen baru docs/PROTOCOL.md berisi detail teknis protokol yang tidak ada di PRD: format tanda tangan, penamaan kid, dan tipe pesan WebSocket. Dokumen ini menjadi acuan client Rust di Phase 2. tests/refclient.py adalah client referensi Python yang benar-benar menjalankan protokol tersebut. Detail ini akan saya ringkas ke PRD setelah Phase 1c-2, supaya PRD cukup diperbarui sekali.

Menerapkan di laptop Anda: hentikan server dulu, lalu dari folder hasil ekstrak (dengan .env disalin dan venv aktif):

bat
pip install -e ".[dev]"
examguard db upgrade
examguard keys dev-init
examguard serve --port 8080 --with-scheduler
pip install wajib dijalankan karena ada dependency baru (cryptography, websockets).
keys dev-init membuat root key dev di folder .examguard\ di dalam proyek. Kalau Anda mereset database dan menjalankan seed demo, langkah ini dijalankan otomatis.
Di /docs sekarang ada bagian client protocol. Bagian ini tidak bisa dicoba langsung dari browser karena setiap request harus ditandatangani dengan kunci perangkat; yang menjalankannya adalah client Rust di Phase 2 (dan tests/refclient.py di test). Yang bisa Anda coba: examguard sim link --exam DEMO-LIVE --email peserta1@demo.example.com untuk melihat launch link, dan http://127.0.0.1:8080/.well-known/examguard-keys.json untuk melihat key set.
Berikutnya Phase 1c-2: Integration API untuk LMS dengan API key per organisasi, webhook bertanda tangan dengan retry, completion token (§16.5), penyimpanan foto identity check terenkripsi, emergency unlock (§22), dan API incident untuk Admin Web.

Examguard server phase1c1
ZIP
Muncul error seperti ini:

(examguard_env) C:\Users\User\Downloads\ExamGuard\examguard-server>examguard sim link --exam DEMO-LIVE --email peserta1@demo.example.com
ATTEMPT_ENDED: this exam can no longer be launched

Ini bukan error program. Server menolak dengan benar karena attempt peserta1 di DEMO-LIVE sudah berakhir. Ujian itu dari sesi uji Phase 1b tadi, dan ada dua kemungkinan penyebabnya:

Di skenario uji, peserta1 sudah menjalankan sim submit, jadi statusnya SUBMITTED.
Batas mulai terakhir (03:45 WIB) sudah lewat. Semua peserta yang belum mulai otomatis menjadi NO_SHOW oleh scheduler.
Launch link memang hanya diberikan untuk attempt yang masih bisa dikerjakan. Anda bisa mengeceknya dengan:

bat
examguard sim attempts --exam DEMO-LIVE
Solusinya, reset database dan buat DEMO-LIVE baru:

bat
examguard db bootstrap --superuser-url postgresql://postgres:PASSWORD_ASLI@127.0.0.1:5432/postgres --drop-existing
examguard db upgrade
examguard seed demo --live-in-minutes 2
seed demo sekarang juga otomatis membuat kunci server baru dengan root key dev yang sudah ada di .examguard\, jadi keys dev-init tidak perlu dijalankan lagi. Setelah itu:

bat
examguard sim link --exam DEMO-LIVE --email peserta1@demo.example.com
Perintah ini langsung bisa dipakai tanpa menunggu jam mulai, karena launch link sudah boleh dibuat sejak check-in dibuka (30 menit sebelum mulai).

Alternatif tanpa reset: kalau statusnya SUBMITTED atau EXPIRED, Exam Admin bisa membuka ulang lewat /docs dengan POST /api/v1/org/attempts/{attempt_id}/reopen dan body:

json
{"reason": "uji ulang", "deadline": "2026-09-30T10:00:00Z"}
Deadline harus di masa depan dan ditulis dalam UTC. Cara ini tidak berlaku untuk NO_SHOW, karena peserta yang tidak hadir memang tidak bisa dibuka ulang.

Karena DEMO-LIVE cepat kedaluwarsa, di Phase 1c-2 saya tambahkan perintah examguard seed live-exam. Perintah ini membuat ujian demo baru kapan saja tanpa menghapus database.

Sudah berhasil:

(examguard_env) C:\Users\User\Downloads\ExamGuard\examguard-server>examguard sim link --exam DEMO-LIVE --email peserta1@demo.example.com
examguard://launch?t=GbEgS-nNBPDpvQNiRU-PciKqdFqEm5TKDKZj8yJ2pRQ
expires 07:31:21 UTC

Untuk yang di link .well-known/examguard-keys.json, juga sudah bisa:
{"body":"{\"issued_at\":\"2026-09-30T07:16:10.670243Z\",\"issuer\":\"http://127.0.0.1:8080\",\"keys\":[{\"alg\":\"EdDSA\",\"crv\":\"Ed25519\",\"kid\":\"srv-20260930-6vNhhQ.command\",\"not_after\":\"2026-12-29T07:16:10.666349Z\",\"not_before\":\"2026-09-30T07:16:10.666349Z\",\"status\":\"active\",\"use\":\"command\",\"x\":\"W1kC-zIius1wb35FdGNMl9nQUjoETvr8Cl7Rnye_Wf4\"},{\"alg\":\"EdDSA\",\"crv\":\"Ed25519\",\"kid\":\"srv-20260930-6vNhhQ.state\",\"not_after\":\"2026-12-29T07:16:10.666349Z\",\"not_before\":\"2026-09-30T07:16:10.666349Z\",\"status\":\"active\",\"use\":\"state\",\"x\":\"W1kC-zIius1wb35FdGNMl9nQUjoETvr8Cl7Rnye_Wf4\"},{\"alg\":\"EdDSA\",\"crv\":\"Ed25519\",\"kid\":\"srv-20260930-6vNhhQ.config\",\"not_after\":\"2026-12-29T07:16:10.666349Z\",\"not_before\":\"2026-09-30T07:16:10.666349Z\",\"status\":\"active\",\"use\":\"config\",\"x\":\"W1kC-zIius1wb35FdGNMl9nQUjoETvr8Cl7Rnye_Wf4\"},{\"alg\":\"EdDSA\",\"crv\":\"Ed25519\",\"kid\":\"srv-20260930-6vNhhQ.token\",\"not_after\":\"2026-12-29T07:16:10.666349Z\",\"not_before\":\"2026-09-30T07:16:10.666349Z\",\"status\":\"active\",\"use\":\"token\",\"x\":\"W1kC-zIius1wb35FdGNMl9nQUjoETvr8Cl7Rnye_Wf4\"}],\"v\":1}","kid":"root-c83b3c54ccb0b064","sig":"3dguoj4idWOG7P6iZjPsuE1PmxpYnRNssVYwnefB9iWo6iWwc-duZLXZzkw5tVZw9-zfqXPHh2RU6-isHGqfCw"}

Berarti bisa dilanjutkan ke fase 1c-2?

Ya, bisa lanjut ke Phase 1c-2. Kedua output itu sudah sesuai harapan.

Launch link: token berlaku 15 menit (kedaluwarsa 07:31 UTC = 14:31 WIB) dan hanya bisa dipakai sekali untuk registrasi perangkat.

Key set:

kid: "root-c83b3c54ccb0b064" di luar menunjukkan dokumen ini ditandatangani root key dev Anda (.examguard\dev-root.key). Client nanti menyimpan public key root ini di dalam aplikasinya dan menolak key set yang tanda tangannya tidak cocok.
Ada empat entri, satu per kegunaan (command, state, config, token), dengan nilai x yang sama. Itu disengaja untuk MVP: satu pasang kunci dipakai untuk empat kegunaan, tetapi masing-masing punya kid sendiri. Kalau kelak kuncinya dipisah, format ini tidak perlu diubah.
not_after 29 Desember 2026: kunci server berlaku 90 hari. Sebelum habis, jalankan examguard keys rotate.
Satu catatan untuk nanti: root key di .examguard\ hanya untuk development. Untuk server produksi, root key dibuat di komputer terpisah yang offline (examguard keys init-root) dan tidak pernah disalin ke server.

Rencana Phase 1c-2:

Integration API (§16.4): kredensial API per organisasi yang dikelola Org Admin. Endpoint untuk mendaftarkan peserta dan mengembalikan launch link, membaca status attempt, melaporkan submit, dan mengirim hasil.
Completion token (§16.5): jalur selesai Level 2. LMS melaporkan submit, server menerbitkan token bertanda tangan, dan client memverifikasinya sebelum keluar dari lockdown.
Webhook (§16.6): event attempt dikirim ke LMS, ditandatangani, dikirim ulang dengan jeda bertahap bila gagal, dan aman diterima dua kali.
Foto identity check (§12.5): selfie dan foto kartu identitas disimpan terenkripsi, dan pengawas bisa melihatnya di Check-in Queue.
Emergency unlock (§22): unlock online lewat command, challenge–response, dan kode cadangan cetak.
API incident untuk Admin Web (§27.8): daftar dan review incident.
examguard seed live-exam: membuat ujian demo baru tanpa reset database, seperti yang saya janjikan.
Pesan error koneksi database di CLI menjadi satu baris, juga seperti yang saya janjikan.
Cakupannya hampir sebesar 1c-1, jadi mungkin kembali dibagi dua zip (misalnya butir 1–3 lalu 4–8). Setiap zip tetap diverifikasi penuh sebelum saya serahkan.

Untuk foto identity check, saya akan menyimpannya sebagai file terenkripsi di folder lokal server, di belakang lapisan penyimpanan yang nanti bisa diganti ke object storage seperti S3 tanpa mengubah API. Kalau Anda sudah punya rencana penyimpanan lain untuk produksi, sampaikan sebelum saya mulai. Kalau tidak, balas “lanjut”.

Oke silahkan dikerjakan untuk fase selanjutnya

Saya mulai dengan bagian A (Integration API, completion token, webhook, seed live-exam, error DB satu baris), lalu bagian B (foto identity check, emergency unlock, API incident). Setiap bagian diakhiri zip terverifikasi. Cek dulu beberapa detail skema:


Ran a command
Ran a command
Skema sudah punya enrollments.external_ref dan source = 'API', jadi migrasi 0004 cukup menambah tabel integrasi, pengiriman webhook, dan hasil ujian.


Ran 2 commands
Ran 2 commands
Sekarang layanan Integration API (autentikasi client credentials, pendaftaran peserta, completion token, hasil) dan pengelolaan integrasi oleh Org Admin:


Created a file, ran a command
Created a file, ran a command
Sekarang dua janji kecil tadi: examguard seed live-exam dan error koneksi database satu baris.


Ran a command
Ran a command
Keduanya jalan. Pesan kedua mengambil baris yang kurang informatif; saya ganti ke baris pertama. Lalu test Integration API dan webhook:


Ran a command
Ran a command
Semua test Integration API dan webhook lulus. Jalankan seluruh suite, lalu kemas bagian A lebih dulu supaya aman:


Ran 2 commands
Ran 2 commands
140 lulus. Kemas bagian A sekarang (README diperbarui):


Ran a command
Ran a command
Bagian A sudah dikemas sebagai titik aman. Lanjut ke bagian B: foto identity check terenkripsi, emergency unlock, dan API incident. Mulai dari migrasi 0005 dan lapisan penyimpanan file:


Ran a command
Ran a command
Sekarang layanan identity check, emergency unlock, dan incident:


Proctoring services: identity photos, emergency unlock, incidents
Proctoring services: identity photos, emergency unlock, incidents
Sambungkan ke protokol, router, dan skema:


Ran a command
Ran a command
Test untuk bagian B:


Ran a command
Ran a command
Semua test bagian B lulus. Jalankan seluruh suite dan lint:


Ran a command
Ran a command
146 lulus. Sekarang dokumentasi: README, docs/PROTOCOL.md, dan PRD. PRD saya naikkan ke v0.3.2 karena v0.3.1 sudah Anda terima.


Ran a command
Ran a command
Sekarang PRD v0.3.2, untuk mencatat keputusan Phase 1c yang mengubah atau memperjelas perilaku:


Ran 2 commands
Ran 2 commands
Kemas zip final Phase 1c-2 dan verifikasi dari hasil ekstrak:


Ran a command, shared files
Ran a command, shared files
Phase 1c-2 selesai, dan dengan itu seluruh Phase 1 (server) selesai. Saya mengekstrak zip ke folder bersih, menginstalnya, dan menjalankan seluruh test dari sana: 146 passed.

Yang ditambahkan di Phase 1c-2:

Integration API untuk LMS (§16.4): Org Admin membuat kredensial (client_id + secret yang hanya tampil sekali), dan bisa merotasi atau mencabutnya. LMS bisa mendaftarkan peserta (aman diulang per candidate_ref), meminta launch link baru, membaca status attempt, dan mengirim hasil.
Completion token (§16.5): saat LMS melaporkan jawaban final tersimpan, attempt menjadi SUBMITTED dan server menerbitkan token bertanda tangan untuk client. Kalau LMS mengulang panggilan karena respons hilang, server memberi token baru tanpa transisi kedua. Kalau attempt tidak ACTIVE, server menjawab 409 sehingga LMS tahu harus menolak jawaban.
Webhook (§16.6): ditandatangani dengan kunci server, jadi LMS memverifikasinya dengan key set yang sama tanpa shared secret. Dicatat dalam transaksi yang sama dengan transisinya, dicoba ulang bertahap sampai 10 kali, dan riwayat pengirimannya bisa dilihat Org Admin.
Foto identity check (§12.5): disimpan terenkripsi di disk, hanya bisa dibuka pengawas yang ditugaskan, dan setiap akses tercatat di audit log. Ada juga endpoint Check-in Queue.
Emergency unlock (§22): ketiga metode tersedia: online lewat command, challenge–response 8 digit, dan kode cadangan cetak yang diverifikasi client secara offline lewat hash.
API incident (§27.8): daftar incident (yang terbuka dan paling berat tampil duluan), detail beserta event-nya, dan review.
examguard seed live-exam dan pesan error koneksi database satu baris, sesuai janji.
Bug yang tertangkap di tengah jalan. Saat mengunci attempt, server bisa memvalidasi status lama yang sudah tersimpan di memori sesi, bukan status terbaru setelah lock. Celah ini sudah ada sejak 1b dan jarang terjadi, tapi nyata. Sudah diperbaiki di satu tempat sehingga berlaku untuk semua aksi.

PRD v0.3.2 mencatat detail protokol yang ditetapkan saat implementasi (launch token, webhook, emergency unlock, format kid) dan tiga keputusan baru (Q17–Q19). Phase 1c ditandai selesai. Detail teknis lengkapnya ada di docs/PROTOCOL.md, termasuk bagian baru untuk emergency unlock, completion token, dan webhook.

Menerapkan di laptop Anda (hentikan server dulu, salin .env, aktifkan venv):

bat
pip install -e ".[dev]"
examguard db upgrade
examguard seed live-exam --in-minutes 3
examguard serve --port 8080 --with-scheduler
Zip ini sudah berisi semuanya, jadi zip bagian A yang sempat saya buat tidak diperlukan dan sudah saya hapus.

Yang bisa dicoba di /docs:

Login sebagai hr@contohjaya.demo.example.com (Org Admin), lalu POST /api/v1/org/integrations untuk membuat integrasi.
Klik Authorize, lalu isi IntegrationCredentials dengan client_id sebagai username dan secret sebagai password.
Coba GET /integration/v1/exams dan POST /integration/v1/exams/{exam_id}/candidates.
Langkah berikutnya, ada dua pilihan:

Phase 2, Headless Client Simulator (Rust): kode Rust pertama. Protokolnya sudah lengkap dan terdokumentasi, jadi simulator bisa dibangun dan diuji langsung terhadap server ini.
Phase 3, Admin Web & Candidate Portal: halaman web pertama yang bisa diklik. Semua API yang dibutuhkan sudah ada.
Urutan PRD adalah Phase 2 dulu. Tapi kalau Anda butuh sesuatu yang bisa didemokan secara visual, Phase 3 bisa didahulukan tanpa masalah teknis.

Examguard server phase1c2
ZIP
ExamGuard PRD v0 3 2
Document
·MD
Login sebagai hr@contohjaya.demo.example.com itu gimana caranya?

Caranya sama seperti login pengawas sebelumnya, hanya email-nya berbeda. Password semua akun demo adalah demo-password-123, kecuali Anda mengubahnya dengan --password saat menjalankan seed demo.

1. Login

Di http://127.0.0.1:8080/docs, buka POST /api/v1/staff/auth/login, klik Try it out, lalu isi body:

json
{
  "email": "hr@contohjaya.demo.example.com",
  "password": "demo-password-123"
}
Klik Execute, lalu salin nilai token dari respons.

2. Pasang token di Authorize

Klik tombol Authorize di kanan atas. Kalau kotak SessionToken masih berisi token pengawas dari sesi sebelumnya, klik Logout di kotak itu dulu. Setelah itu tempel token baru (tanpa kata Bearer) dan klik Authorize.

3. Ambil org_id

Jalankan GET /api/v1/staff/me dan salin org_id dari memberships. Isinya sama dengan org PT Contoh Jaya yang Anda pakai untuk pengawas, jadi kalau kotak OrgId di Authorize sudah terisi, biarkan saja.

4. Buat integrasi

Jalankan POST /api/v1/org/integrations dengan body:

json
{
  "name": "LMS Uji Coba",
  "webhook_url": "http://127.0.0.1:9000/hooks"
}
Simpan client_id dan secret dari respons, karena secret hanya ditampilkan sekali. Kalau terlewat, buat secret baru lewat POST /api/v1/org/integrations/{integration_id}/rotate-secret.

Alamat webhook di atas hanya contoh dan belum ada yang menerimanya. Pengiriman akan gagal lalu dicoba ulang, dan Anda bisa melihat percobaannya di GET /api/v1/org/integrations/{integration_id}/deliveries. Itu tidak mengganggu apa pun.

5. Mencoba sebagai LMS

Buka Authorize lagi, lalu di kotak IntegrationCredentials isi client_id sebagai username dan secret sebagai password. Setelah itu endpoint di bagian integration (LMS) bisa dicoba, misalnya GET /integration/v1/exams.

Kalau muncul 403 missing permission org.integrations, berarti yang aktif masih token pengawas atau Exam Admin. Hanya Org Admin (hr@...) yang boleh mengelola integrasi, jadi ulangi langkah 2.

Yang poin 4 saya kok tidak bisa masukkan body nya ya? Dimana saya bisa masukkaan bodynya seperti itu?

Kemungkinan besar tombol Try it out belum diklik. Di Swagger UI, kotak body masih terkunci (hanya contoh abu-abu) sampai tombol itu ditekan.

Langkahnya:

Di bagian integration management, cari baris hijau bertuliskan POST /api/v1/org/integrations. Pastikan yang POST, bukan yang biru (GET) dengan alamat yang sama, karena GET memang tidak punya body.
Klik baris itu sampai terbuka.
Klik tombol Try it out di kanan atas bagian yang terbuka.
Kotak Request body sekarang bisa diedit. Isinya contoh seperti ini:
json
{
  "name": "string",
  "webhook_url": "string"
}
Hapus semua isinya, lalu tempel body dari langkah 4 sebelumnya.
5. Klik tombol biru Execute di bawahnya. Hasilnya muncul di bagian Responses, di bawah tulisan Server response.

Kalau setelah Try it out kotaknya tetap tidak bisa diketik, pastikan pilihan di sebelah kanan judul Request body adalah application/json.

Oke sudah bisa semua akhirnya. Sekarang berarti melanjutkan ke bagian B.

Bagian B sebenarnya sudah selesai dan ikut di zip examguard-server-phase1c2.zip yang Anda pasang. Awalnya memang saya rencanakan dua zip terpisah, tapi karena bagian B selesai di sesi yang sama, keduanya saya gabung jadi satu zip dan zip bagian A saya hapus. Jadi setelah examguard db upgrade (migrasi 0004 dan 0005), fitur bagian B sudah aktif di laptop Anda.

Kalau ingin mencobanya di /docs, ada di kelompok check-in, unlock & incidents. Login sebagai pengawas atau Exam Admin, dengan exam_id diambil dari GET /api/v1/org/exams:

Kode cadangan emergency unlock: POST /api/v1/org/exams/{exam_id}/backup-codes dengan body {"count": 5}. Hasilnya lima kode berformat XXXXX-XXXXX, dan hanya ditampilkan sekali.
Respons challenge–response: POST /api/v1/org/attempts/{attempt_id}/unlock-response dengan body {"challenge": "ABCD2345", "reason": "uji coba"}. Hasilnya 8 digit angka. Ini hanya bisa untuk peserta yang sudah pernah di-launch (sim launch), karena secret-nya dibuat saat registrasi perangkat.
Incident: GET /api/v1/org/exams/{exam_id}/incidents. Setelah skenario terputus-lalu-tersambung dengan sim heartbeat, di sini muncul incident UNMONITORED_INTERRUPTION.
Satu yang belum bisa dicoba dari /docs adalah upload foto identity check, karena request-nya harus ditandatangani kunci perangkat. Fitur itu nanti dijalankan oleh client (Phase 2); di server, test otomatisnya sudah lulus.

Dengan ini Phase 1 (server) sudah lengkap. Langkah berikutnya salah satu dari dua ini:

Phase 2, Headless Client Simulator (Rust): kode Rust pertama, sesuai urutan PRD. Simulator ini menjalankan protokol client sungguhan (launch, tanda tangan, WebSocket, upload foto dan event) terhadap server Anda, dan modulnya dipakai ulang oleh aplikasi browser di Phase 5. Untuk ini Anda perlu memasang Rust di laptop.
Phase 3, Admin Web & Candidate Portal: halaman web pertama yang bisa diklik, cocok bila Anda butuh sesuatu yang bisa didemokan.
Mana yang ingin dikerjakan lebih dulu?

Mungkin bisa dilanjutkan saja ke phase 2. Tapi di phase 2 ini saya belum punya Rust. Bagaimana cara menginstallnya di komputer saya?

Instalasi Rust di Windows cukup lewat satu installer resmi, rustup. Satu hal yang perlu disiapkan: Rust di Windows butuh Microsoft C++ Build Tools (linker dari Visual Studio). Installer rustup bisa memasangnya sekaligus.

1. Unduh installer

Buka https://rustup.rs lalu unduh rustup-init.exe versi 64-bit.

2. Jalankan rustup-init.exe

Kalau Build Tools belum ada, installer akan menampilkan pilihan kurang lebih seperti ini:

1) Quick install via the Visual Studio Community installer
2) Manually install the prerequisites
3) Don't install the prerequisites
Pilih 1. Installer Visual Studio akan terbuka dengan komponen yang dibutuhkan (MSVC dan Windows SDK) sudah tercentang, jadi cukup klik Install dan tunggu selesai. Unduhannya beberapa GB, jadi butuh waktu.

Setelah itu kembali ke jendela rustup. Saat ditanya pilihan instalasi, pilih:

1) Proceed with standard installation (default - just press enter)
Ini memasang Rust versi stable untuk Windows 64-bit (x86_64-pc-windows-msvc).

3. Tutup lalu buka lagi Command Prompt

Langkah ini penting, karena PATH baru hanya terbaca di terminal yang baru dibuka. Setelah itu cek:

bat
rustc --version
cargo --version
Keduanya harus menampilkan nomor versi, misalnya rustc 1.9x.x.

4. Uji coba kompilasi

bat
cd %USERPROFILE%\Downloads
cargo new halo
cd halo
cargo run
Kalau muncul Hello, world!, Rust dan linker-nya sudah bekerja. Folder halo boleh dihapus setelahnya.

5. Editor (opsional, tapi sangat membantu)

Kalau Anda memakai VS Code, pasang ekstensi rust-analyzer untuk autocompletion dan penanda error langsung di editor.

Kalau ada masalah:

link.exe not found saat cargo run: Build Tools belum terpasang lengkap. Buka Visual Studio Installer dan pastikan workload Desktop development with C++ tercentang.
Unduhan gagal di jaringan kantor: biasanya karena proxy. Set dulu di Command Prompt, lalu jalankan ulang installer:
bat
set HTTPS_PROXY=http://alamat-proxy:port
Untuk Phase 2 tidak ada lagi yang perlu dipasang. Saya akan memilih library Rust yang tidak butuh OpenSSL atau library sistem lain (misalnya rustls untuk HTTPS), supaya proyeknya langsung bisa dikompilasi dengan cargo build.

Kirimkan hasil rustc --version setelah selesai, lalu kita mulai Phase 2.

Ini hasilnya:

C:\Users\User>rustc --version
rustc 1.98.1 (48a229cea 2026-09-01)

C:\Users\User>cargo --version
cargo 1.98.1 (797e8a9bc 2026-08-05)

C:\Users\User>cd Downloads

C:\Users\User\Downloads>cargo new halo
    Creating binary (application) halo package
note: see more Cargo.toml keys and their definitions at https://doc.rust-lang.org/cargo/reference/manifest.html

C:\Users\User\Downloads>cd halo

C:\Users\User\Downloads\halo>cargo run
   Compiling halo v0.1.0 (C:\Users\User\Downloads\halo)
    Finished dev profile [unoptimized + debuginfo] target(s) in 1.02s
     Running target\debug\halo.exe
Hello, world!

Rust sudah terpasang dengan benar. rustc 1.98.1 dan cargo run menghasilkan Hello, world!, artinya compiler dan linker MSVC-nya bekerja.

Sebelum mulai menulis kode, saya cek dulu isi Phase 2 di PRD dan apakah sandbox saya bisa mengompilasi Rust. Setiap kode Rust akan saya uji langsung terhadap server ExamGuard yang sama dengan milik Anda.


Ran a command
Ran a command
Sandbox bisa memasang Rust 1.91 dari repositori Ubuntu. Versinya sedikit lebih lama dari milik Anda (1.98), jadi kode yang lolos di sini juga akan terkompilasi di laptop Anda.


Ran 2 commands
Ran 2 commands
/bin/sh di sandbox tidak mendukung brace expansion, jadi foldernya tidak terbuat. Buat satu per satu:


Ran 4 commands
Ran 4 commands
Sekarang test Rust yang wajib mereproduksi vector tersebut:


Ran 2 commands
Ran 2 commands
Sekarang inti logika client, session.rs: launch, recovery setelah restart (§20.2), full state sync, penerapan command, antrean event offline, completion token, dan emergency unlock.


Ran 3 commands, created a file
Ran 3 commands, created a file
Batas minimumnya 15 detik, jadi skenario crash bisa selesai dalam kurang dari setengah menit. Sekarang CLI eg-sim:


Ran 3 commands
Ran 3 commands
pkill -f kembali menghentikan shell saya sendiri, karena pola yang dicari ikut muncul di baris perintahnya. Kali ini saya hentikan server lama lewat port-nya saja:


Ran 7 commands
Ran 7 commands
Uji cepat ini menemukan bug nyata di server: start sebelum jam mulai seharusnya dijawab 409 START_NOT_YET_ALLOWED, tetapi server mengembalikan 500. Saya cek log server:


Ran 6 commands
Ran 6 commands
Verifikasi zip client: ekstrak ke folder bersih, build, lalu test:


Ran a command, shared files
Ran a command, shared files
Phase 2 selesai. Saya mengekstrak zip client ke folder bersih, lalu build release dan menjalankan test di sana; semuanya lulus. Kedua zip juga diuji bersama-sama.

Hasil pengujian

Konformitas client–server: 6 test Rust mereproduksi byte-per-byte tanda tangan EG-Sig, envelope, JWT completion, dan emergency unlock yang dihasilkan kode server Python.
Skenario end-to-end terhadap server sungguhan: 20 dari 20 pemeriksaan lulus. Skenario crash, reconnect, dan replay (exit criteria Phase 2 di PRD) ditambah alur normal.
Recovery state: isinya terenkripsi di disk, dan file yang dimanipulasi atau disalin ke perangkat lain ditolak.
Server: 147 test lulus.
Dua temuan dari Phase 2

Bug server, sudah diperbaiki. start sebelum jam mulai menghasilkan error 500, bukan 409 START_NOT_YET_ALLOWED. Penyebabnya, detail error berisi waktu (window_start) yang gagal diubah ke JSON. Bug ini sudah ada sejak 1b; test lama tidak menangkapnya karena memanggil service langsung, bukan lewat HTTP. Perbaikannya ada di penangan error pusat, dan ada test regresinya. Perbaikan ini ada di examguard-server-phase2.zip.
Klarifikasi protokol. Aturan STALE di §17.3 akan membuat WARNING dan EMERGENCY_UNLOCK tidak pernah diterapkan, karena keduanya tidak menaikkan state_version. Di client, aturan STALE hanya berlaku untuk command yang mengubah status. Klarifikasi ini sudah dicatat di docs/PROTOCOL.md dan akan masuk revisi PRD berikutnya.
Memasang di laptop Anda

Letakkan kedua folder bersebelahan, misalnya Downloads\ExamGuard\examguard-server dan Downloads\ExamGuard\examguard-client.

Server: hentikan server dulu. Ekstrak zip server, salin .env dan folder .examguard\ dari folder lama (folder itu berisi root key dev), lalu:
bat
pip install -e ".[dev]"
Tidak ada migrasi baru.
2. Client:

bat
cd ..\examguard-client
cargo build --release
cargo test
Build pertama makan beberapa menit.

Menjalankan skenario

Di folder server:

bat
examguard serve --port 8080 --with-scheduler
examguard seed live-exam --in-minutes 1 --candidates 4
Setelah jam start yang dicetak (UTC) lewat, di folder client:

bat
set EG_ROOT_KEY_FILE=..\examguard-server\.examguard\dev-root.key
target\release\eg-sim scenario all --exam LIVE-MMDD-HHMM
Baris terakhir harus menunjukkan 20 checks, 20 passed, 0 failed. Setiap peserta hanya bisa dipakai satu kali, jadi untuk mengulang buat ujian baru dengan seed live-exam. Perintah manual (launch, run, event, recover, unlock, dan lainnya) dijelaskan di README client.

Langkah berikutnya

Phase 3, Admin Web & Candidate Portal: halaman web pertama untuk pengawas dan peserta, memakai API yang sudah lengkap.
Phase 5, Client Foundation (Rust + CEF): aplikasi browser sungguhan, dibangun di atas eg-protocol dan eg-client yang baru saja diuji.
Urutan PRD adalah Phase 3 lebih dulu.

Examguard client phase2
ZIP
Examguard server phase2
ZIP
Untuk menjalankan kode diatas apakah butuh 2 PC, sebagai server dan client?

Tidak perlu. Satu laptop cukup. Server dan client berkomunikasi lewat 127.0.0.1 (alamat laptop itu sendiri), jadi keduanya berjalan berdampingan di komputer yang sama. Anda hanya butuh beberapa jendela Command Prompt:

Jendela	Folder	Perintah
1	examguard-server	examguard serve --port 8080 --with-scheduler (biarkan tetap terbuka)
2	examguard-server	examguard seed live-exam ..., examguard sim link ...
3	examguard-client	eg-sim scenario ... atau perintah eg-sim lainnya
PostgreSQL di Docker juga berjalan di laptop yang sama. Untuk mensimulasikan banyak peserta sekaligus pun tetap cukup satu laptop: jalankan beberapa eg-sim dengan --state-dir berbeda, dan masing-masing berperilaku seperti perangkat terpisah dengan kunci sendiri.

Kapan dua komputer berguna

Untuk Phase 2, dua komputer hanya berguna kalau Anda ingin menguji lewat jaringan sungguhan, misalnya mencabut Wi-Fi laptop peserta untuk melihat skenario terputus. Kalau ingin mencobanya, ada tiga hal yang perlu diubah:

Server mendengarkan di jaringan, bukan hanya di laptop sendiri:
bat
examguard serve --host 0.0.0.0 --port 8080 --with-scheduler
Izinkan port 8080 di Windows Firewall bila diminta.
2. Alamat publik server di .env. Tambahkan:

EXAMGUARD_PUBLIC_BASE_URL=http://192.168.1.10:8080
Ganti dengan IP laptop server (lihat lewat ipconfig). Ini penting: server memberi tahu client alamat API dan WebSocket-nya lewat Signed Exam Config. Kalau masih 127.0.0.1, client di komputer lain akan mencoba menghubungi dirinya sendiri.
3. Di komputer client: salin folder examguard-client beserta root key dev, lalu:

bat
set EG_SERVER=http://192.168.1.10:8080
set EG_ROOT_KEY_FILE=C:\path\ke\dev-root.key
Menyalin root key privat ke komputer lain hanya boleh di development. Di produksi, client hanya memegang public key-nya.

Kebutuhan komputer kedua baru benar-benar terasa di Phase 5–6. Saat itu aplikasi browser mengunci layar dan keyboard (lockdown), jadi mengujinya di laptop yang sama dengan tempat Anda bekerja akan merepotkan. Untuk tahap itu, mesin kedua atau virtual machine (misalnya Hyper-V atau VirtualBox) akan sangat membantu.

Apakah kamu bisa memberikan examguard phase 2 lagi untuk server dan client nya? Saya lupa belum download waktu itu.


Ran 2 commands, shared files
Ran 2 commands, shared files
Kedua file Phase 2 sudah saya kirim ulang, isinya sama persis dengan yang dulu dan sudah saya cek utuh:

examguard-server-phase2.zip: server versi 0.1.0a6. Isinya sama dengan Phase 1c-2 ditambah perbaikan error 500 pada START_NOT_YET_ALLOWED.
examguard-client-phase2.zip: client Rust (eg-protocol, eg-client, eg-sim).
Ringkasan pemasangan. Letakkan kedua folder bersebelahan, misalnya di Downloads\ExamGuard\.

Server (hentikan server yang sedang jalan dulu):

Ekstrak zip server.
Salin .env dan folder .examguard\ dari folder server lama ke folder baru. Folder .examguard\ berisi root key dev.
Aktifkan venv, lalu jalankan:
bat
pip install -e ".[dev]"
Tidak ada migrasi baru dibanding Phase 1c-2.

Client:

bat
cd ..\examguard-client
cargo build --release
cargo test
Menjalankan skenario uji:

bat
:: jendela 1, folder server
examguard serve --port 8080 --with-scheduler

:: jendela 2, folder server
examguard seed live-exam --in-minutes 1 --candidates 4

:: jendela 3, folder client (setelah jam start yang dicetak lewat)
set EG_ROOT_KEY_FILE=..\examguard-server\.examguard\dev-root.key
target\release\eg-sim scenario all --exam LIVE-MMDD-HHMM
Hasil yang diharapkan: 20 checks, 20 passed, 0 failed. Langkah lengkapnya ada di README masing-masing zip.

Di folder lama adanya ".examguard". Untuk ".env" nya tidak ada. Adanya ".env.example".


Ran a command
Ran a command
Tidak apa-apa, itu berarti selama ini server Anda berjalan dengan nilai default yang tertanam di kode, dan nilai default itu sama persis dengan isi .env.example:

user runtime examguard_app dengan password app-password
user migrasi examguard_owner dengan password owner-password
database examguard di 127.0.0.1:5432, mode dev
Jadi di folder baru Anda cukup menyalin folder .examguard\ saja. .env tidak perlu dibuat, dan semua perintah (examguard serve, db upgrade, seed live-exam) akan memakai koneksi yang sama seperti sebelumnya.

Kalau Anda ingin lebih rapi atau suatu saat mau mengganti password, buat .env dari contohnya:

bat
copy .env.example .env
Isinya identik dengan default, jadi tidak mengubah perilaku apa pun. Kalau nanti password di .env diubah, jalankan examguard db bootstrap --superuser-url ... sekali agar password role di PostgreSQL ikut menyesuaikan.

Setelah folder .examguard\ disalin, lanjutkan dengan pip install -e ".[dev]" lalu langkah-langkah sebelumnya.

Oke saya sudah meng-copy ".env.example" menjadi ".env". Kemudian sudah menyalin folder ".examguard". Kemudian saya harus melakukan perintah 'pip install -e ".[dev]"'' ini di folder yang server atau client?

Di folder server (examguard-server), dengan venv yang aktif:

bat
cd C:\Users\User\Downloads\ExamGuard\examguard-server
examguard_env\Scripts\activate
pip install -e ".[dev]"
Sesuaikan perintah activate dengan lokasi venv Anda. Kalau venv-nya ada di folder server lama, aktifkan dari sana saja; pip akan mengarahkan instalasi ke folder baru tempat Anda menjalankan perintah. Tanda venv aktif adalah (examguard_env) di awal baris prompt.

Folder client tidak memakai pip sama sekali, karena isinya Rust. Di sana perintahnya:

bat
cd ..\examguard-client
cargo build --release
cargo test
Untuk memastikan server yang terpasang sudah versi baru:

bat
pip show examguard-server
Baris Version harus 0.1.0a6 dan Location mengarah ke folder server yang baru.

Files hidden when shared
Ini hasilnya

Semua hasilnya sesuai harapan:

Build client: cargo build --release selesai dalam 2 menit 20 detik tanpa error, jadi target\release\eg-sim.exe sudah ada.
Test client: 8 test lulus. Dua test recovery state lulus, begitu juga keenam test konformitas yang mencocokkan tanda tangan client dengan server byte-per-byte.
Server: versi 0.1.0a6, dan Editable project location sudah mengarah ke folder server yang baru.
Satu hal kecil: Location menunjuk ke site-packages WinPython (WPy64-31230\...), bukan ke folder venv examguard_env. Artinya perintah pip yang terpanggil adalah milik WinPython, meskipun prompt menampilkan (examguard_env). Ini tidak masalah selama perintah examguard juga memakai Python yang sama, dan biasanya memang begitu. Kalau nanti examguard menampilkan versi lama atau tidak dikenali, instal ulang dengan python -m pip install -e ".[dev]" supaya pasti masuk ke Python yang aktif.

Langkah berikutnya adalah menjalankan skenario Phase 2.

Jendela 1 (folder server), biarkan tetap berjalan:

bat
cd C:\Users\User\Downloads\ExamGuard\examguard-server
examguard serve --port 8080 --with-scheduler
Jendela 2 (folder server):

bat
examguard seed live-exam --in-minutes 1 --candidates 4
Catat kode ujiannya (misalnya LIVE-1021-0610) dan jam start-nya. Jam itu dalam UTC, jadi tambahkan 7 jam untuk WIB.

Jendela 3 (folder client), setelah jam start lewat:

bat
cd C:\Users\User\Downloads\ExamGuard\examguard-client
set EG_ROOT_KEY_FILE=..\examguard-server\.examguard\dev-root.key
target\release\eg-sim scenario all --exam LIVE-1021-0610
Ganti kode ujian sesuai hasil di jendela 2. Skenario berjalan sekitar satu menit, termasuk jeda kurang lebih 25 detik di skenario crash. Baris terakhir harus 20 checks, 20 passed, 0 failed. Kalau ada yang FAIL, kirimkan outputnya.

Ini saya coba pakai perintah ini kok tidak keluar apa-apa ya:
(examguard_env) C:\Users\User\Downloads\ExamGuard>examguard seed live-exam --in-minutes 1 --candidates 4

Ada satu hal yang terlihat dari prompt Anda: perintah itu dijalankan dari folder C:\Users\User\Downloads\ExamGuard, padahal seharusnya dari examguard-server. Perintah examguard membaca .env dan folder .examguard\ (tempat root key dev) dari folder tempat ia dijalankan, jadi jalankan selalu dari folder server:

bat
cd C:\Users\User\Downloads\ExamGuard\examguard-server
examguard seed live-exam --in-minutes 1 --candidates 4
Kalau berhasil, outputnya tiga baris seperti ini:

LIVE-1021-0616 created in pt-contoh-jaya: 4 candidates, invigilators assigned
check-in 05:46, start 06:16 UTC, latest start 06:46 UTC
try: examguard sim launch --exam LIVE-1021-0616 --email peserta1@demo.example.com
Tapi folder yang salah biasanya tidak membuat perintah diam sama sekali; minimal ada pesan sukses atau error. Kalau dari folder server pun tetap tidak keluar apa-apa, tolong jalankan ini dan kirimkan hasilnya:

bat
echo %errorlevel%
where examguard
examguard --version
examguard seed --help
echo %errorlevel% (langsung setelah perintah yang diam tadi): 0 berarti perintah selesai tanpa error, angka lain berarti gagal diam-diam.
where examguard: menunjukkan examguard.exe mana yang terpanggil. Karena tadi pip menginstal ke WinPython, mungkin ada dua examguard.exe: satu baru di WinPython, satu lama di venv examguard_env.
examguard seed --help: harus ada demo dan live-exam di daftar perintahnya. Kalau live-exam tidak muncul, berarti yang terpanggil adalah versi lama.
Satu lagi: apakah setelah menekan Enter prompt langsung kembali, atau kursornya diam tanpa kembali ke prompt? Kalau diam, perintahnya masih berjalan atau tertahan, dan itu masalah yang berbeda.

Oh ya sudah bisa:
(examguard_env) C:\Users\User\Downloads\ExamGuard\examguard-server>examguard seed live-exam --in-minutes 1 --candidates 4
LIVE-1021-0618 created in pt-contoh-jaya: 4 candidates, invigilators assigned
check-in 05:48, start 06:18 UTC, latest start 06:48 UTC
try: examguard sim launch --exam LIVE-1021-0618 --email peserta1@demo.example.com

Ujian LIVE-1021-0618 sudah terbuat. Jam mulainya 13:18 WIB (06:18 UTC), dan pesan Anda terkirim pukul 13:18, jadi kemungkinan besar jam mulainya sudah lewat. Batas mulai terakhir 13:48 WIB, jadi skenario harus dijalankan sebelum jam itu.

Sekarang jalankan skenario di jendela 3 (folder client). Server di jendela 1 harus tetap berjalan dengan --with-scheduler:

bat
cd C:\Users\User\Downloads\ExamGuard\examguard-client
set EG_ROOT_KEY_FILE=..\examguard-server\.examguard\dev-root.key
target\release\eg-sim scenario all --exam LIVE-1021-0618
Prosesnya sekitar satu menit; ada jeda kurang lebih 25 detik di skenario crash saat client sengaja “mati”. Hasil yang diharapkan di akhir:

20 checks, 20 passed, 0 failed
Kalau ada error:

START_NOT_YET_ALLOWED: jam mulai belum tiba. Tunggu sebentar lalu ulangi.
attempt is ACTIVE/SUBMITTED; seed a new exam: skenario sudah pernah dijalankan untuk ujian ini, dan setiap peserta hanya bisa dipakai sekali. Buat ujian baru dengan seed live-exam.
FAIL server marked the attempt INTERRUPTED: server di jendela 1 kemungkinan berjalan tanpa --with-scheduler.
Kirimkan output lengkapnya kalau ada yang FAIL.

Files hidden when shared
Hasilnya seperti ini:

Semua 20 pemeriksaan lulus di laptop Anda. Phase 2 selesai. Exit criteria dari PRD (skenario crash, reconnect, dan replay terhadap server) terpenuhi di mesin Anda sendiri, bukan hanya di sandbox saya.

Beberapa hal yang terbukti dari log:

happy: perintah pengawas sampai ke client lewat WebSocket dalam kurang dari 2 detik (UPDATE_DEADLINE diterapkan pukul 06:20:11), dan ACK tercatat di server.
crash: setelah client “mati”, server menandai INTERRUPTED dalam batas 15 detik. Saat restart, lockdown aktif dulu sebelum konek, lalu attempt lanjut otomatis dengan kunci perangkat yang sama, dan incident UNMONITORED_INTERRUPTION tercatat.
reconnect: pause yang dikirim saat client terputus tetap berlaku setelah sambung ulang. Command lama yang datang belakangan ditandai STALE dan tidak diterapkan dua kali.
replay: command yang diulang dikenali sebagai duplikat, command yang dimanipulasi ditolak karena tanda tangannya tidak valid, request lama ditolak (CLOCK_SKEW), dan launch token tidak bisa dipakai ulang.
Satu catatan untuk nanti: kunci server Anda (srv-20260930-6vNhhQ) berlaku sampai 29 Desember 2026. Sebelum tanggal itu, jalankan dari folder server:

bat
examguard keys rotate --root-key .examguard\dev-root.key
Kalau kunci kedaluwarsa, server akan menolak menandatangani apa pun (NO_SIGNING_KEY).

Ada juga satu klarifikasi protokol dari Phase 2 yang belum masuk PRD: aturan STALE hanya berlaku untuk command yang mengubah status. Saat ini baru tercatat di docs/PROTOCOL.md, dan akan saya masukkan ke revisi PRD berikutnya.

Langkah berikutnya sesuai urutan PRD adalah Phase 3, Admin Web & Candidate Portal: halaman web pertama untuk pengawas (Live Monitoring, Candidate Detail, Check-in Queue, Incidents) dan peserta (katalog, pendaftaran, Ujian Saya). Semua API-nya sudah tersedia. Kabari saya kalau ingin mulai.

Untuk deskripsi ini kira-kira kapan akan dieksekusi ya rencananya?

"Ada juga satu klarifikasi protokol dari Phase 2 yang belum masuk PRD: aturan STALE hanya berlaku untuk command yang mengubah status. Saat ini baru tercatat di docs/PROTOCOL.md, dan akan saya masukkan ke revisi PRD berikutnya."

Belum ada jadwal pastinya. Rencananya, klarifikasi itu ikut revisi PRD berikutnya, dan revisi itu baru akan terjadi kalau Phase 3 memunculkan keputusan baru yang perlu dicatat. Kalau dibiarkan menunggu, catatan ini bisa tertunda cukup lama, sementara isinya hanya beberapa baris:

§17.3: aturan “state_version ≤ versi terakhir → STALE” diberi batasan, hanya untuk command yang mengubah status (PAUSE_EXAM, RESUME_EXAM, UPDATE_DEADLINE, ALLOW_REENTRY, REJECT_REENTRY, FORCE_SUBMIT, FORCE_TERMINATE). WARNING dan EMERGENCY_UNLOCK tidak menaikkan versi, sehingga tidak pernah dianggap STALE. Command yang sudah pernah diterapkan tidak diterapkan ulang, tetapi tetap di-ACK APPLIED.
§30.2: Phase 2 ditandai selesai (✓).
§32.1 dan §0: keputusan baru Q20 dan satu baris di riwayat perubahan, sebagai v0.3.3.
Revisinya bisa saya kerjakan sekarang, cukup beberapa menit, supaya PRD selalu sejalan dengan kode sebelum Phase 3 dimulai. Mau saya buatkan v0.3.3 sekarang?

Menurut saya masukkan saja sekalian sebelum masuk ke phase 3


Ran 2 commands, shared files
Ran 2 commands, shared files
PRD v0.3.3 sudah jadi, jadi PRD dan kode kembali sejalan sebelum Phase 3. Ada lima perubahan:

§0.1: tabel riwayat baru “v0.3.2 → v0.3.3”. Riwayat lama dinomori ulang jadi §0.2 sampai §0.5.
§17.3: paragraf STALE yang lama tetap ada, ditambah empat butir batasan:
STALE hanya berlaku untuk tujuh command yang mengubah status.
WARNING dan EMERGENCY_UNLOCK tidak pernah STALE, beserta alasannya.
Command duplikat tidak diterapkan ulang, tetapi tetap di-ACK APPLIED.
Urutan pemeriksaan di client ditetapkan. Duplikat diperiksa sebelum kedaluwarsa supaya pengiriman ulang yang terlambat tetap mendapat ACK APPLIED, bukan REJECTED. Urutan ini sama dengan yang sudah berjalan di eg-protocol.
§30.2: Phase 2 ditandai ✓.
§32.1: keputusan Q20.
§32.2: kalimat penutup kini menyebut tidak ada open question yang menghalangi Phase 3.
Kalau Anda sudah siap, kita mulai Phase 3: Admin Web & Candidate Portal.

Oke setelah PRD itu dibuat, apakah perlu ada revisi untuk kode program phase 2 nya?


Ran a command
Ran a command
Tidak perlu. PRD v0.3.3 memang ditulis dari perilaku kode Phase 2 yang sudah berjalan, bukan sebaliknya, jadi kodenya sudah sesuai. Saya cek ulang langsung di zip yang Anda pasang:

Aturan di PRD v0.3.3	Di kode
STALE hanya untuk 7 command yang mengubah status	STATE_CHANGING di eg-protocol/src/rules.rs berisi tepat tujuh command itu, dan pemeriksaan STALE hanya berlaku untuk daftar tersebut
WARNING dan EMERGENCY_UNLOCK tidak pernah STALE	Keduanya tidak ada di STATE_CHANGING, dan ada test-nya (command_rules_17_3: “warnings are never stale”)
Duplikat tidak diterapkan ulang, tetap di-ACK APPLIED	eg-client/src/session.rs mengembalikan APPLIED untuk Duplicate
Urutan: kid/use/signature → ID sesi → duplikat → kedaluwarsa → STALE	Urutan di rules.rs sama persis, dengan komentar 1–2, 3, 5, 4, lalu STALE
Bukti dari laptop Anda sendiri ada di skenario tadi. Command duplikat di-ACK tanpa diterapkan ulang (duplicate command ...: not applied again), WARNING v2 tetap tampil walaupun versinya sama dengan state, dan PAUSE yang datang terlambat ditandai STALE.

Di sisi server juga tidak ada yang perlu diubah: server tidak menjalankan aturan ini, ia hanya menerima ACK APPLIED, STALE, atau REJECTED. docs/PROTOCOL.md di zip server juga sudah memuat klarifikasi yang sama. Satu-satunya yang belum ada di sana adalah kalimat soal urutan pemeriksaan. Itu murni dokumentasi, jadi akan saya tambahkan saat zip server berikutnya dibuat di Phase 3, tanpa perlu instal ulang sekarang.

Jadi Phase 2 bisa dianggap final, dan kita bisa langsung masuk Phase 3.

Oke mari kita masuk ke phase 3

Phase 3 adalah frontend pertama, jadi ada satu keputusan teknologi yang menentukan seluruh struktur kode dan sulit diubah belakangan. Sebelum menanyakannya, saya cek dulu kondisi sandbox:


Ran a command
Ran a command
Teknologi apa yang dipakai untuk Admin Web dan Candidate Portal?
React + Vite + TS (Recommended)
Bagian mana yang dikerjakan lebih dulu? Phase 3 cukup besar (PRD §27 berisi 15 halaman, §28 portal peserta), jadi saya bagi menjadi dua zip.
Admin Web dulu (Recommended)
Bahasa UI apa yang disiapkan? PRD §25 mensyaratkan Indonesia dan Inggris.
Indonesia dulu, siap i18n (Recommended)
Pilihan Anda: React + Vite + TypeScript, Admin Web dulu, dan Bahasa Indonesia dengan struktur i18n. Saya pulihkan dulu server dari zip Phase 2 dan menyiapkan database di sandbox:


Ran 5 commands, loaded a skill
Ran 5 commands, loaded a skill
Penyajian Admin Web oleh server. Hasil build React diletakkan di dalam paket server, jadi di laptop cukup examguard serve tanpa Node.js:


Ran 2 commands, read a file
Ran 2 commands, read a file
Baseline server lulus (exit 0). Test untuk tambahan server:


Ran a command
Ran a command
Hasil 404 di sana memang benar: klien HTTP sudah menormalkan .. sebelum request dikirim. Test saya ubah supaya memakai .. yang di-encode, karena bentuk itulah yang benar-benar sampai ke server:


Ran a command
Ran a command
Sekarang proyek frontend examguard-web. Saya pasang dependency-nya terlebih dulu:


Ran a command
Ran a command
Dependency terpasang dengan versi yang dikunci. Konfigurasi proyek, termasuk proxy dev ke server dan script yang menyalin hasil build ke paket server:


Ran a command
Ran a command
Token desain dan stylesheet:


Created a file
Created a file
Lapisan dasar: i18n, klien API, sesi login, dan utilitas waktu:


Ran 2 commands
Ran 2 commands
Utilitas, konteks sesi, dan komponen bersama:


Ran 2 commands
Ran 2 commands
Layout dengan sidebar dan pemilih organisasi, halaman login, dan routing:


Ran a command
Ran a command
Dashboard dan daftar ujian:


Ran a command
Ran a command
Formulir buat/ubah ujian (§27.3 dan kebijakan keamanan §27.4):


Created a file, ran a command
Created a file, ran a command
Halaman detail ujian: header, aksi tingkat ujian, mistar waktu, dan tab:


Created a file, ran a command
Created a file, ran a command
Komponen dialog aksi. Setiap aksi pada peserta wajib disertai alasan (§27.7) dan mengirim expected_state_version, sehingga dua pengawas tidak saling menimpa:


Created a file
Created a file
Sekarang inti Phase 3a: register Live Monitoring dan panel Candidate Detail.


Created a file, ran a command
Created a file, ran a command
Panel Candidate Detail (§27.6): fakta, aksi, timeline event, riwayat status, perangkat, dan perintah ke client:


Created a file
Created a file
Tab sisanya: Check-in, Incident, Re-entry, Peserta, dan Pengawas:


Ran 4 commands
Ran 4 commands
Typecheck bersih. Build produksi, lalu salin ke paket server:


Ran 2 commands
Ran 2 commands
Server melayani /admin/. Script simulasi peserta, memakai client referensi dari test server lewat HTTP sungguhan:


Ran a command
Ran a command
Peserta simulasi berjalan: aktif, dijeda, menunggu persetujuan perangkat baru, dan satu yang sengaja diam. Saya ambil screenshot lewat Playwright:


Read 6 files, ran 2 commands, created a file
Read 6 files, ran 2 commands, created a file
Ada beberapa baris ceroboh di script itu (to_have_class(lambda ...) tidak valid, dan ada sisa variabel). Saya rapikan dulu sebelum dijalankan:


Ran 3 commands
Ran 3 commands
Typecheck bersih. Build ulang lalu jalankan e2e dengan ujian baru, karena peserta di ujian sebelumnya sudah terpakai:


Ran 4 commands
Ran 4 commands
PNG yang saya ketik manual ternyata rusak, jadi saya buat ulang dengan Pillow. Selain itu, ujian check-in perlu mulai paling lambat 30 menit lagi agar check-in sudah terbuka:


Ran 9 commands, read 2 files
Ran 9 commands, read 2 files
Server: 151 test lulus. Frontend: 15 unit test dan e2e 11/11. Sekarang dokumentasi dan pengemasan:


Ran 3 commands
Ran 3 commands
PRD v0.3.4 siap. Sekarang pengemasan dua zip, lalu verifikasi masing-masing dari folder bersih:


Ran 3 commands, shared files
Ran 3 commands, shared files
Phase 3a selesai: Admin Web sudah bisa dibuka di browser. Semua yang saya kirim sudah diverifikasi dari hasil ekstrak zip di folder bersih:

Server: 151 test lulus.
Frontend: 15 unit test, typecheck, dan build berhasil.
End-to-end di Chromium: 11 dari 11 pemeriksaan lulus terhadap server sungguhan dengan peserta simulasi. Setiap klik di UI dicek hasilnya lewat API, misalnya deadline bergeser tepat 5 menit, persetujuan perangkat baru, review incident, peringatan massal, buat → perbaiki → publikasikan ujian, persetujuan foto check-in, dan pengawas hanya melihat ujian yang ditugaskan.
Isi Admin Web

Login dan pemilih organisasi, Dashboard, daftar ujian, dan formulir ujian beserta kebijakan keamanan.
Pemantauan, berbentuk register peserta bernomor. Peserta yang perlu ditangani (terputus, menunggu persetujuan, incident terbuka, offline, menunggu check-in) disorot kuning. Data diperbarui tiap 2 detik, dan sisa waktu berdetak langsung di browser. Ada juga filter, pencarian, dan aksi massal.
Panel peserta: semua aksi sesuai status dan peran, dialog yang mewajibkan alasan, emergency unlock, timeline event, dan riwayat status.
Tab Check-in (foto), Incident, Terputus & masuk kembali, Peserta (undangan, akomodasi), dan Pengawas, serta aksi Perpanjang, Finalisasi, dan Kode cadangan yang bisa dicetak.
Memasang di laptop Anda

Cukup zip server, karena hasil build UI sudah ada di dalamnya, jadi tidak perlu Node.js. Seperti biasa, hentikan server lalu salin .env dan folder .examguard\ ke folder baru, kemudian:

bat
pip install -e ".[dev]"
examguard serve --port 8080 --with-scheduler
Buka http://127.0.0.1:8080/admin/ dan masuk sebagai exams@pt-contoh-jaya.demo.example.com atau pengawas@pt-contoh-jaya.demo.example.com (password demo-password-123). Supaya Pemantauan langsung terisi, buat ujian baru dengan examguard seed live-exam --in-minutes 1 --candidates 4, lalu jalankan eg-sim scenario atau eg-sim launch dari folder client.

Zip examguard-web hanya perlu kalau Anda ingin mengubah tampilan; langkahnya ada di README-nya.

Temuan selama pengerjaan

Test e2e menemukan masalah aksesibilitas: teks petunjuk field ikut terbaca sebagai bagian label field lain oleh pembaca layar. Sudah diperbaiki untuk semua field.
PRD v0.3.4 mencatat empat keputusan:
Teknologi frontend.
Live Monitoring memakai pemuatan ulang 2 detik, bukan WebSocket seperti di §27.5. Target <3 detik di §25 tetap terpenuhi.
Status review incident disamakan dengan server (REVIEWED/ESCALATED). Ketidaksesuaian ini sudah ada sejak Phase 1c dan baru ketahuan saat membuat halaman Incident.
Pembagian Phase 3a dan 3b.
Phase 3b berikutnya berisi pengaturan organisasi dan anggota, integrasi LMS, audit log, pengaturan platform, Candidate Portal, dan terjemahan Inggris. Exit criteria Phase 3 di PRD (satu tes publik dan satu tes instansi berjalan end-to-end) baru bisa dipenuhi setelah Candidate Portal selesai.

Setelah login, saya perlu menjalankan perintah ini:
examguard seed live-exam --in-minutes 1 --candidates 4 ?

Tidak wajib. Login dan semua halaman sudah bisa dipakai tanpa perintah itu, karena data dari seed demo sudah tersedia: tiga organisasi demo, ujian DEMO-LIVE, EPT-2026-10-A/B, dan REKRUT-ENG-01. Anda bisa langsung mencoba Dashboard, daftar ujian, formulir buat ujian, tab Peserta, dan tab Pengawas.

seed live-exam gunanya supaya halaman Pemantauan ada isinya. Pemantauan baru muncul untuk ujian yang sudah dipublikasikan, dan baru ramai kalau ada peserta yang sedang mengerjakan. Ujian demo lama kemungkinan sudah lewat jam mulainya, jadi pesertanya sudah NO_SHOW.

Kalau ingin melihat Pemantauan “hidup”, urutannya begini. Perintah ini bisa dijalankan kapan saja, sebelum atau sesudah login, karena halaman Admin Web akan memperbarui diri sendiri:

Jendela 2, folder server: buat ujian yang mulai 1 menit lagi.
bat
examguard seed live-exam --in-minutes 1 --candidates 4
Ujian baru langsung muncul di Dashboard dengan status Siap. Keempat peserta masih Belum mulai.

Jendela 3, folder client: setelah jam mulai lewat, jalankan peserta simulasi.
bat
set EG_ROOT_KEY_FILE=..\examguard-server\.examguard\dev-root.key
target\release\eg-sim scenario all --exam LIVE-MMDD-HHMM
Selama sekitar satu menit, Pemantauan akan menampilkan peserta mulai, dijeda, terputus (tersorot kuning), lalu selesai.

Kalau ingin peserta yang tetap online supaya bisa dicoba aksi pengawas dari panel (Jeda, Tambah waktu, Kirim peringatan), jalankan satu peserta secara manual:

bat
:: folder server
examguard sim link --exam LIVE-MMDD-HHMM --email peserta1@demo.example.com

:: folder client, tempel link tadi
target\release\eg-sim launch "examguard://launch?t=..." --start --run 0
--run 0 membuat peserta tetap terhubung sampai ujian selesai atau Anda menekan Ctrl+C. Setiap aksi dari Admin Web akan terlihat langsung di jendela eg-sim, misalnya APPLY PAUSE_EXAM.

Ganti LIVE-MMDD-HHMM dengan kode yang dicetak di langkah 1.

Keluar error seperti ini:

(examguard_env) C:\Users\User\Downloads\ExamGuard\examguard-server> examguard seed live-exam --in-minutes 1 --candidates 4
EXAM_CODE_TAKEN: exam code 'LIVE-1024-1507' already exists

Error ini muncul karena kode ujian dari seed live-exam dibentuk dari tanggal dan jam mulai (LIVE-MMDD-HHMM). Kalau perintah dijalankan dua kali dalam menit yang sama, keduanya menghasilkan kode yang sama, dan server menolak kode ganda.

Jam mulai yang diminta adalah 22:07 WIB (15:07 UTC), sedangkan pesan Anda terkirim pukul 22:06. Kemungkinan besar perintah itu sudah berhasil sekali sebelumnya di menit yang sama, jadi ujian LIVE-1024-1507 sudah ada, dan Anda bisa langsung memakainya. Cek dengan:

bat
examguard sim attempts --exam LIVE-1024-1507
Kalau muncul 4 peserta berstatus NOT_STARTED, lanjutkan ke langkah eg-sim dengan kode LIVE-1024-1507. Ujian ini juga sudah terlihat di Dashboard Admin Web.

Kalau ingin ujian baru, tunggu satu menit, atau ubah waktunya supaya kodenya berbeda:

bat
examguard seed live-exam --in-minutes 2 --candidates 4
Perilaku ini memang merepotkan, dan seharusnya perintah demo tidak gagal hanya karena dijalankan dua kali. Di zip Phase 3b akan saya perbaiki: kalau kode sudah dipakai, perintah otomatis menambah akhiran seperti LIVE-1024-1507-2, dan kode yang dipakai tetap dicetak di layar.

Keluar begini:

(examguard_env) C:\Users\User\Downloads\ExamGuard\examguard-server>examguard sim attempts --exam LIVE-1024-1507
c6ec4be2-b4ba-4014-b333-456ec308eb62  peserta1@demo.example.com        NOT_STARTED              v0   deadline=-
64a7ce83-ed4e-45ac-8126-ba684032fd96  peserta2@demo.example.com        NOT_STARTED              v0   deadline=-
09635772-5308-484f-85b1-aa3050298067  peserta3@demo.example.com        NOT_STARTED              v0   deadline=-
f75e4bee-b451-4d85-8368-ffb4e97ab24d  peserta4@demo.example.com        NOT_STARTED              v0   deadline=-

Ujiannya sudah ada dengan empat peserta yang belum mulai, jadi perintah pertama tadi memang sudah berhasil. Jam mulainya 22:07 WIB, sama dengan pesan Anda, jadi jendela mulai sudah terbuka. Batas mulai terakhir 22:37 WIB.

Sekarang di jendela folder client (server tetap berjalan dengan --with-scheduler), Anda bisa memilih salah satu dari dua cara berikut.

Pilihan A: skenario otomatis (sekitar satu menit, peserta muncul lalu selesai):

bat
cd C:\Users\User\Downloads\ExamGuard\examguard-client
set EG_ROOT_KEY_FILE=..\examguard-server\.examguard\dev-root.key
target\release\eg-sim scenario all --exam LIVE-1024-1507
Sambil berjalan, buka ujian LIVE-1024-1507 di Admin Web, tab Pemantauan. Anda akan melihat peserta berpindah status, termasuk peserta2 yang tersorot kuning saat “crash”.

Pilihan B: satu peserta tetap online (untuk mencoba aksi pengawas sendiri dari panel):

bat
:: folder server
examguard sim link --exam LIVE-1024-1507 --email peserta1@demo.example.com

:: folder client, tempel link hasil perintah di atas
set EG_ROOT_KEY_FILE=..\examguard-server\.examguard\dev-root.key
target\release\eg-sim launch "examguard://launch?t=..." --start --run 0
Lalu di Admin Web klik Peserta Demo 1 dan coba Jeda, Tambah waktu, atau Kirim peringatan. Setiap aksi langsung terlihat di jendela eg-sim sebagai APPLY PAUSE_EXAM, APPLY UPDATE_DEADLINE, dan seterusnya. Tekan Ctrl+C untuk menghentikan peserta; sekitar satu menit kemudian ia tersorot kuning sebagai Terputus.

Kedua pilihan bisa dipakai bersamaan, asalkan peserta yang dipakai Pilihan B tidak sama dengan yang dipakai skenario. Skenario memakai peserta1 sampai peserta4, jadi kalau ingin keduanya, buat dulu ujian baru dengan --candidates 5 dan pakai peserta5 untuk Pilihan B.

Untuk yang scenario A jika di coba ke satu peserta saja apakah bisa?

Bisa. Ganti all dengan nama satu skenario, dan perintah itu hanya memakai satu peserta:

bat
target\release\eg-sim scenario happy --exam LIVE-1024-1507
Kalau hanya satu skenario yang dijalankan, peserta yang dipakai adalah email pertama di --emails (default peserta1@demo.example.com). Untuk memilih peserta lain:

bat
target\release\eg-sim scenario crash --exam LIVE-1024-1507 --emails peserta2@demo.example.com
Pilihan skenarionya:

Skenario	Yang terlihat di Pemantauan
happy	Peserta mulai, deadline bertambah 5 menit, menerima peringatan, satu incident FOCUS_LOST, lalu selesai
crash	Peserta mulai lalu “mati” sekitar 25 detik: offline, Terputus (tersorot kuning), lalu kembali Mengerjakan otomatis dan selesai
reconnect	Peserta dijeda saat terputus, tersambung lagi dalam keadaan Dijeda, dilanjutkan, lalu selesai
replay	Uji keamanan (command diulang, dimanipulasi, request lama); di Pemantauan hanya terlihat mulai, tambah waktu 1 menit, lalu selesai
Dua hal yang perlu diingat:

Setiap peserta hanya bisa dipakai sekali. Setelah skenario selesai, attempt peserta itu SUBMITTED. Kalau menjalankan skenario lain, pakai peserta berikutnya lewat --emails.
Skenario crash mengubah batas waktu terputus seluruh ujian itu menjadi 15 detik supaya prosesnya cepat. Jadi kalau setelahnya Anda mencoba Pilihan B di ujian yang sama, peserta yang dihentikan dengan Ctrl+C akan tersorot Terputus setelah sekitar 15 detik, bukan 60.
Oke kalau ingin mencoba scenario B bagaimana?

Pilihan B memakai satu peserta yang tetap terhubung, lalu Anda bertindak sebagai pengawas di Admin Web. Batas mulai terakhir LIVE-1024-1507 adalah 22:37 WIB, jadi masih ada waktu.

1. Pilih peserta yang belum dipakai

Di folder server:

bat
examguard sim attempts --exam LIVE-1024-1507
Pakai peserta yang masih NOT_STARTED. Peserta yang sudah dipakai skenario A berstatus SUBMITTED dan tidak bisa dipakai lagi. Contoh di bawah memakai peserta3; ganti sesuai hasil Anda.

2. Buat launch link (masih di folder server)

bat
examguard sim link --exam LIVE-1024-1507 --email peserta3@demo.example.com
Salin baris examguard://launch?t=.... Link ini berlaku 15 menit dan hanya sekali pakai.

3. Jalankan peserta (folder client)

bat
cd C:\Users\User\Downloads\ExamGuard\examguard-client
set EG_ROOT_KEY_FILE=..\examguard-server\.examguard\dev-root.key
target\release\eg-sim --state-dir .eg-sim\peserta3 launch "examguard://launch?t=..." --start --run 0
Tanda kutip di sekitar link wajib, karena link berisi karakter ? dan =.
--state-dir .eg-sim\peserta3 memberi peserta ini folder sendiri, supaya tidak bentrok dengan sisa percobaan sebelumnya.
--run 0 membuat peserta tetap online. Biarkan jendela ini terbuka; di sinilah Anda melihat perintah dari pengawas tiba.
Kalau berhasil, akan muncul state ACTIVE v1 lalu WSS connected.

4. Bertindak sebagai pengawas di Admin Web

Buka ujian LIVE-1024-1507, tab Pemantauan, lalu klik Peserta Demo 3. Coba aksi di panel dan perhatikan jendela eg-sim:

Aksi di Admin Web	Yang muncul di jendela eg-sim
Kirim peringatan	WARNING dialog: ...
Tambah waktu	APPLY UPDATE_DEADLINE ... dengan deadline baru
Jeda, lalu Lanjutkan	APPLY PAUSE_EXAM ..., lalu APPLY RESUME_EXAM ...
Kumpulkan paksa / Hentikan attempt	EXIT (...): peserta keluar dan eg-sim berhenti
Aksi yang mengakhiri attempt sebaiknya dicoba paling akhir, karena setelah itu peserta tidak bisa dipakai lagi.

5. (Opsional) Simulasi terputus dan masuk kembali

Tekan Ctrl+C di jendela eg-sim. Setelah sekitar 60 detik (atau 15 detik kalau skenario crash sudah pernah dijalankan di ujian ini), Peserta Demo 3 tersorot kuning sebagai Terputus.
Sambungkan kembali seperti client yang restart:
bat
target\release\eg-sim --state-dir .eg-sim\peserta3 recover --run 0
Kalau jedanya kurang dari 10 menit, peserta otomatis kembali Mengerjakan, dan tab Terputus & masuk kembali mencatat jeda serta penyebabnya (CLIENT_CRASH).

Oke simulasi dapat berjalan dengan baik. Tapi saya mendapatkan temuan, yaitu ketika saya "Ctrl-C" untuk simulasi putus, informasi terputus itu lama sekali terdeteksi. Tapi ketika saya jalankan lagi, informasi mengerjakannya lebih cepat daripada terputus (walaupun sebenarnya juga masih lambat, harusnya bisa cepat juga). Apakah itu bisa diperbaiki?

Bisa. Asimetri yang Anda lihat memang nyata, dan penyebabnya bisa dijelaskan. Rincian waktunya dengan pengaturan saat ini:

Saat Ctrl+C (terputus):

Tahap	Aturan	Waktu setelah Ctrl+C
Heartbeat terakhir	Client mengirim heartbeat tiap 10 detik (PRD §17.6)	0–10 detik sebelumnya
Tampil Offline + sorotan kuning	30 detik tanpa heartbeat	sekitar 20–30 detik
Status Terputus	60 detik tanpa heartbeat (interruption_threshold), dicek scheduler tiap 5 detik	sekitar 50–65 detik
Muncul di Admin Web	Pemantauan memuat ulang tiap 2 detik	+0–2 detik
Saat dijalankan lagi (recover): heartbeat pertama langsung membuat server mengubah status ke Mengerjakan pada saat itu juga. Yang tersisa hanya jeda pemuatan ulang UI: maksimal 2 detik di register dan 3 detik di panel peserta. Karena itu sambung ulang terasa jauh lebih cepat daripada terputus.

Kenapa deteksi terputus sengaja dibuat lambat. Di ruang ujian, Wi-Fi sering putus sambung beberapa detik. Kalau setiap putus 3 detik langsung menjadi “Terputus”, pengawas akan dibanjiri peringatan palsu dan incident UNMONITORED_INTERRUPTION yang tidak berarti. Angka 30 dan 60 detik di PRD adalah kompromi untuk itu.

Tapi ada yang memang bisa diperbaiki tanpa menambah peringatan palsu. Saat Anda menekan Ctrl+C (atau client crash, atau ditutup paksa), sistem operasi langsung menutup koneksi WebSocket, dan server sebenarnya tahu saat itu juga. Saat ini informasi itu diabaikan, dan server tetap menunggu heartbeat yang tidak datang. Usulan perbaikan saya:

Offline langsung saat koneksi tertutup. Server mencatat waktu WebSocket tertutup, dan peserta langsung tampil Offline (tersorot kuning) dalam 2–3 detik, bukan 20–30 detik. Kasus jaringan yang benar-benar hilang tanpa sinyal tutup tetap terdeteksi lewat aturan 30 detik.
Status “Terputus” tetap menunggu interruption_threshold, supaya putus sesaat yang langsung tersambung lagi tidak tercatat sebagai interupsi. Di panel peserta saya tambahkan keterangan “offline sejak 22:15:03 (14 detik)”, sehingga pengawas tahu sudah berapa lama.
Scheduler dicek tiap 2 detik (sekarang 5 detik), dan panel peserta dimuat ulang tiap 2 detik (sekarang 3 detik), supaya sambung ulang juga tampil dalam ≤2 detik.
Dengan perbaikan ini, waktu dari Ctrl+C sampai tersorot Offline turun dari sekitar 25 detik menjadi sekitar 3 detik. Status resmi “Terputus” tetap sekitar 60 detik, sesuai PRD.

Satu hal perlu Anda putuskan: apakah 60 detik untuk status “Terputus” mau diturunkan? Nilai ini sudah bisa diatur per platform, organisasi, atau ujian (minimal 15 detik; skenario crash memakai 15 detik). Saran saya, default tetap 60 detik karena perbaikan nomor 1 sudah memberi sinyal visual yang cepat, dan instansi yang jaringannya stabil bisa menurunkannya sendiri per ujian.

Mau saya kerjakan sekarang sebagai perbaikan kecil Phase 3a, atau digabung ke zip Phase 3b? Kalau sekarang, Anda cukup memasang ulang zip server, karena client Rust tidak perlu diubah.

Dengan adanya status offline dan terputus ini takut saya malah membuat pengawas bingung. Jadi samakan saja. Kalau offline per 2-3 detik, informasi terputus juga harus sama.

Keputusan Anda jelas: satu status, satu waktu. Begitu server tahu peserta terputus, peserta langsung berstatus Terputus, dan tidak ada lagi tahap “Offline tapi masih Mengerjakan”. Saya kerjakan sekarang sebagai perbaikan Phase 3a.

Ada dua jalur deteksi yang akan saya samakan:

Koneksi tertutup (Ctrl+C, crash, aplikasi ditutup, laptop mati): server tahu seketika, jadi langsung Terputus, terlihat di Admin Web dalam 2–3 detik.
Jaringan hilang diam-diam (kabel dicabut, Wi-Fi mati, tidak ada sinyal tutup): server hanya bisa menyimpulkan dari heartbeat yang tidak datang. Status Offline dan Terputus akan muncul bersamaan saat batas waktu tercapai. Saya samakan keduanya di 30 detik (tiga heartbeat terlewat), turun dari sebelumnya 30 dan 60 detik.
Saya lihat dulu kode yang terlibat:


Ran 12 commands
Ran 12 commands
Now the edits: sessions threshold helper, attempts/dashboard callers, client_flow liveness, WS close handling.


Ran 25 commands, created a file
Ran 25 commands, created a file
Now run all eg-sim scenarios against the new server to see what the reconnect scenario does.


Ran 22 commands
Ran 22 commands
Now a visual check in the Admin Web: a candidate is killed, and the Live register should flip within ~2 s.


Ran 24 commands, created a file, read a file
Ran 24 commands, created a file, read a file
Sudah diperbaiki. Status Offline dan Terputus sekarang selalu muncul pada waktu yang sama.

Hasil uji di sini:

Client ditutup paksa (seperti Ctrl+C): baris peserta di halaman Pemantauan berubah ke “Terputus” + “Offline” dalam 1,0 detik. Di server sendiri perubahannya tercatat dalam 0,04 detik.
Client dijalankan lagi: kembali ke “Mengerjakan” + “Online” dalam 1,9 detik.
Jaringan hilang diam-diam (kabel dicabut, Wi-Fi mati): kasus ini tidak bisa terdeteksi seketika karena tidak ada sinyal penutupan koneksi. Offline dan Terputus muncul bersamaan setelah 30 detik. Sebelumnya Offline muncul di 30 detik dan Terputus baru di 60 detik.
Yang berubah:

Penyebab lambatnya: dulu server mengabaikan saat koneksi client tertutup, dan baru tahu dari heartbeat yang tidak datang lagi. Sekarang koneksi yang tertutup langsung dicatat sebagai Terputus. Peserta yang sedang dijeda tetap berstatus “Dijeda”, hanya koneksinya jadi Offline.
Ambang 30 detik berlaku untuk keduanya. Nilai ini masih bisa diubah per ujian (15–600 detik). Server yang masih memakai default lama 60 detik otomatis diubah ke 30 saat db upgrade.
Request apa pun dari client (sinkronisasi, selesai ujian, kirim event) sekarang ikut melanjutkan ujian yang terputus. Karena itu kembalinya juga lebih cepat.
Jeda di bawah 10 detik tidak membuat incident, supaya daftar incident tidak penuh oleh gangguan sesaat. Jeda itu tetap tercatat di riwayat peserta.
Pemeriksaan otomatis server sekarang tiap 2 detik (sebelumnya 5). Panel detail peserta juga dimuat ulang tiap 2 detik.
seed live-exam menambah akhiran otomatis kalau kodenya sudah dipakai, misalnya LIVE-1024-1548-2.
Client: setelah tersambung kembali, request pertamanya sekarang menyertakan penyebab putus (CLIENT_CRASH atau NETWORK_FAILURE). Tanpa ini, incident akan tercatat dengan penyebab UNKNOWN. Skenario reconnect juga ditulis ulang, karena jeda lewat pengawas tidak bisa lagi dilakukan saat peserta terputus.
Pengujian: 160 tes server, skenario client 24/24, dan tes Admin Web 11/11 lulus. Semuanya diulang dari zip yang sudah diekstrak bersih.

Cara pasang (Windows):

Server: ganti isi folder examguard-server, tapi pertahankan .env dan folder .examguard. Lalu jalankan:
pip install -e ".[dev]"
examguard db upgrade
examguard serve --port 8080 --with-scheduler
Client: ganti isi folder examguard-client, lalu jalankan cargo build --release. Versinya sekarang 0.2.1.
Admin Web: hasil build-nya sudah ada di zip server. Zip examguard-web hanya perlu kalau Anda ingin mengubah tampilannya.
Untuk mencoba lagi Skenario B: jalankan examguard seed live-exam --in-minutes 1 --candidates 4, mulai satu peserta dengan eg-sim run, lalu tekan Ctrl+C sambil membuka halaman Pemantauan.

Perubahannya juga sudah dicatat di PRD v0.3.5 (riwayat §0.1, §10.2, §17.6, §20.3, §27.5, keputusan Q25 dan Q26). Setelah ini kita bisa lanjut ke Phase 3b.

Files hidden when shared
Oke sekarang sudah bisa dan sudah lumayan cepat dibanding versi sebelumnya. Selanjutnya saya juga menemukan sesuatu, yaitu pada tampilan ujian, misalkan peserta terdapat 2 kali incident, nah tidak ada informasi 2 incident itu apa. Harusnya informasi ini muncul waktu kita klik nama peserta itu dan ada semacam tabel atau apa lah begitu yang berisi informasi mengenai 2 incident itu apa. Kaalau informasi incidentnya lengkap lebih bagus, misalkan disertai jamnya dan berapa lama incident itu terjadi.


Ran 5 commands
Ran 5 commands
Server side first: include the candidate’s incidents in the attempt detail.


Ran 28 commands, read 2 files
Ran 28 commands, read 2 files
Fine. Seed fresh exams and rerun e2e.


Ran 6 commands, read 3 files, shared files
Ran 6 commands, read 3 files, shared files
Sekarang kalau nama peserta diklik, panelnya menampilkan bagian Incident paling atas, sebelum tombol aksi. Bisa juga langsung klik angka incident (misalnya angka 2 merah itu): panel terbuka dan langsung menuju daftar incident.

Isi setiap baris incident:

Waktu: jam mulai, dan jam selesai kalau ada jedanya (misalnya “02.40.45 s.d. 02.40.52”).
Kejadian: nama dalam bahasa Indonesia (“Keluar dari jendela ujian”, “Lebih dari satu orang”, “Tidak terpantau (terputus)”), lengkap dengan severity dan satu kalimat penjelasan.
Rincian tambahan kalau ada: penyebab terputus (misalnya “client crash atau ditutup”), tingkat keyakinan deteksi AI (“keyakinan 86%”), dan jumlah event yang digabung.
Durasi: contohnya “7 d” atau “sesaat”. Incident yang belum selesai ditulis “berlangsung 1 m 40 d”, dan angkanya terus bertambah setiap detik.
Tinjauan: status dari pengawas, beserta catatannya kalau ada.
Urutannya: yang belum ditinjau di atas, lalu dari yang terbaru. Klik satu baris untuk melihat event terkait (mulai/selesai beserta jamnya) sekaligus meninjau incident itu dari situ. Kode teknisnya (FOCUS_LOST dan sebagainya) masih bisa dilihat di dialog tersebut.

Dua perubahan kecil yang ikut:

Status “Terbuka” saya ganti jadi “Belum ditinjau”. Di tabel ini ada juga incident yang masih “berlangsung”, dan dua kata itu mudah tertukar.
Tab Incident sekarang juga memakai nama kejadian yang mudah dibaca, bukan kode.
Di layar HP, durasi pindah ke bawah jam supaya kolom kejadian tetap terbaca.
Pengujian: 161 tes server lulus. Tes browser sekarang ada 12 dan semuanya lulus, termasuk cek baru: klik angka incident lalu daftar incident harus langsung terlihat. Semuanya diulang dari zip yang diekstrak bersih.

Cara pasang: ganti isi folder examguard-server, tapi pertahankan .env dan folder .examguard. Lalu jalankan pip install -e ".[dev]" dan restart server. Tidak ada migrasi database baru, dan client tidak berubah. Zip web hanya perlu kalau Anda ingin mengubah tampilan.

Perubahannya juga sudah dicatat di PRD v0.3.6 (riwayat §0.1, §27.6 beserta mockup barunya, dan keputusan Q27).

Oke sementara oke dulu. Selanjutnya apa yang akan kita lakukan?

Berikutnya Phase 3b, sisa pekerjaan Phase 3. Isinya ada dua kelompok besar.

1. Candidate Portal (PRD §28)
Ini web untuk peserta, dan menjadi syarat selesainya Phase 3. Sekarang peserta baru bisa “ada” lewat CLI (seed, sim link), jadi alurnya belum terasa nyata. Isinya:

daftar akun, verifikasi email, login, dan lupa password;
daftar ujian yang diikuti, beserta jadwal dan statusnya;
pendaftaran ujian publik dan menerima undangan;
tombol “Mulai ujian”, yang membuat link examguard://launch untuk membuka client;
halaman cek kesiapan dan riwayat hasil (selesai, terputus, dan seterusnya).
2. Admin Web lanjutan

Pengaturan organisasi dan anggota: tambah staf, ubah peran, nonaktifkan.
Integrasi LMS: API key, webhook, riwayat pengiriman webhook.
Audit log: daftar, filter, dan verifikasi hash chain.
Pengaturan platform untuk Platform Admin: default dan batas nilai seperti ambang 30 detik tadi.
Terjemahan Inggris untuk Admin Web dan Candidate Portal.
Usul urutan saya: Candidate Portal dulu (3b-1), lalu Admin Web lanjutan (3b-2), dan terjemahan Inggris paling akhir setelah semua teks stabil. Alasannya, dengan Candidate Portal Anda bisa menguji alur ujian dari sudut pandang peserta: daftar, login, klik “Mulai ujian”, lalu client simulasi terbuka. Ini lebih dekat ke pemakaian sebenarnya dibanding lewat CLI. Server untuk bagian peserta sebagian besar sudah ada sejak Phase 1a, jadi pekerjaannya lebih banyak di sisi web.

Satu hal yang perlu diputuskan dulu: Candidate Portal dibuat sebagai aplikasi terpisah (misalnya di /portal/), atau satu aplikasi dengan Admin Web tapi tampilan dan login yang berbeda? Saran saya aplikasi terpisah dalam folder examguard-web yang sama. Peserta dan staf punya kebutuhan yang berbeda (peserta lebih banyak memakai HP, tampilannya lebih sederhana), dan kode yang bisa dipakai bersama, seperti koneksi ke API, i18n, dan format waktu, tetap dipakai bersama.

Satu pengingat: kunci tanda tangan server di laptop Anda berlaku sampai 29 Desember 2026. Sebelum tanggal itu jalankan examguard keys rotate --root-key .examguard\dev-root.key.

Kalau urutan dan bentuknya sudah cocok, saya mulai 3b-1 Candidate Portal.

Ada yang perlu saya luruskan disini. Jika kamu mengaggap peserta dan staf berbeda karena peserta lebih banyak menggunakan hp itu salah. Peserta juga defaultnya diminta menggunakan laptop atau PC. Untuk terpisah atau tidak sebenarnya saya terserah saja. Yang penting nanti ada login untuk peserta dan staf. Entah loginnya mau jadi satu atau terpisah saya ikut saja.


Ran 2 commands
Ran 2 commands
Terima kasih, koreksinya saya catat: peserta juga memakai laptop atau PC. Itu memang masuk akal, karena ujiannya berjalan di client ExamGuard yang hanya ada untuk desktop. Jadi Candidate Portal dirancang untuk layar laptop, sama seperti Admin Web. Tampilan HP tetap tidak rusak, tapi bukan prioritas.

Bentuk yang saya ambil: satu alamat masuk di /, berisi halaman pilihan “Masuk sebagai Peserta” atau “Masuk sebagai Staf”.

Peserta masuk ke portal di /portal/, staf ke Admin Web di /admin/.
Login-nya tetap dua. Akun peserta dan akun staf memang tersimpan terpisah di server. Satu email bisa saja menjadi staf di satu organisasi dan peserta ujian di organisasi lain. Dengan login terpisah, server tidak perlu menebak siapa yang masuk, dan sesi staf tidak tercampur dengan sesi peserta.
Kodenya tetap di folder examguard-web yang sama dan memakai komponen yang sama (koneksi API, bahasa, format waktu, gaya tampilan), jadi tampilannya seragam.
Isi 3b-1 Candidate Portal. Sebagian besar API-nya sudah ada di server sejak Phase 1a:

daftar akun, verifikasi email, login dan logout;
lupa password: ini yang belum ada di server dan akan saya tambahkan;
katalog ujian publik dan pendaftarannya, pindah sesi, pembatalan;
menerima undangan ujian instansi lewat link email;
“Ujian saya”: jadwal, status, hitung mundur ke check-in, lalu tombol Mulai ujian yang membuka client lewat link examguard://launch;
petunjuk singkat kalau client belum terpasang, dan riwayat ujian yang sudah selesai.
Untuk mengujinya, pengecekan otomatis di browser akan menjalankan alur lengkap: peserta mendaftar, verifikasi email (lewat outbox development), login, mendaftar ujian, lalu klik Mulai ujian. Setelah itu client simulasi masuk memakai link yang didapat dari portal, dan pengawas melihat peserta itu muncul di halaman Pemantauan Admin Web.

Kalau bentuk ini sudah sesuai, saya langsung kerjakan di pesan berikutnya.

Oke silahkan dikerjakan


Ran 26 commands, updated tasks, created a file
Ran 26 commands, updated tasks, created a file
Now the shared API client (per-app session storage) and the landing page.


Ran 11 commands
Ran 11 commands
Now the central page, “Ujian saya”, with the exam card and launch dialog.


Ran 15 commands, created 5 files
Ran 15 commands, created 5 files
Now screenshots to review the design on desktop and mobile.


Ran 14 commands, read 5 files, updated tasks
Ran 14 commands, read 5 files, updated tasks
Phase 3b-1 (Candidate Portal) sudah jadi dan sudah diuji end-to-end di browser.

Cara masuk: buka http://127.0.0.1:8080/, lalu pilih Masuk sebagai peserta atau Masuk sebagai staf. Login dan sesinya tetap terpisah: kalau Anda masuk sebagai staf di browser yang sama, sesi peserta tidak ikut keluar. Portal dirancang untuk layar laptop/PC.

Isi portal:

Akun: daftar dengan nama sesuai kartu identitas, verifikasi email, masuk, lupa kata sandi, ganti kata sandi, dan ubah nama.
Ujian saya: setiap ujian tampil sebagai kartu ujian dengan tanggal, jam, jam check-in dibuka, batas mulai, dan durasi, ditambah satu kalimat posisi peserta (misalnya “Check-in dibuka dalam 2 hari 3 jam”).
Tombol Mulai ujian aktif dari check-in dibuka sampai batas mulai. Kartu yang bisa dikerjakan saat itu diberi tanda kuning, sama seperti register pengawas.
Saat ujian berjalan, tombolnya menjadi Buka kembali ExamGuard, untuk membuka client lagi setelah crash.
Ujian yang selesai, dibatalkan, atau dipindah sesinya masuk ke bagian Riwayat.
Katalog ujian publik: filter teks, jenis tes, dan tanggal, sisa kursi, serta kode akses kalau dibutuhkan. Dari sini peserta bisa mendaftar, pindah sesi dalam jenis tes yang sama, atau membatalkan.
Undangan: tautan dari email langsung menampilkan isi undangannya. Peserta lalu diarahkan masuk atau membuat akun dengan email tujuan undangan, dan undangan diingat sampai peserta selesai masuk.
Mencoba dengan eg-sim: setelah klik Mulai ujian, browser akan mencoba membuka examguard://…. Karena aplikasi desktopnya belum ada, buka bagian Untuk pengujian dengan eg-sim di dialog itu, salin tautannya, lalu jalankan eg-sim launch "<tautan>".

Belum ada di tahap ini: cek kesiapan perangkat dan unduhan client (menunggu client desktop di Phase 5), pengingat email H-1 dan 1 jam, permintaan hapus akun, dan tampilan hasil ujian. Sementara ini tombol Unduh ExamGuard tampil tapi belum aktif. Pengingat email dan hapus akun saya jadwalkan di Phase 3b-2. Hasil ujian menunggu website ujian bisa mengirim nilainya.

Pengujian: 172 tes server lulus. Tes browser baru untuk portal lulus 10/10 dengan alur: buat akun → verifikasi email → terima undangan → daftar, pindah, dan batalkan ujian publik → ubah nama → reset kata sandi → Mulai ujian. Di akhir alur itu, Admin Web menampilkan peserta tersebut sebagai “Mengerjakan” dan Online. Tes Admin Web juga tetap lulus 12/12. Semuanya diulang dari zip yang diekstrak bersih.

Cara pasang:

Ganti isi folder examguard-server dan examguard-web, tapi pertahankan .env dan folder .examguard. Lalu jalankan pip install -e ".[dev]" dan restart server. Tidak ada migrasi database baru, dan client Rust tidak berubah.
Penting: buka .env di folder server, lalu hapus baris EXAMGUARD_PORTAL_BASE_URL=http://localhost:5173. Baris itu ikut tersalin dari .env.example lama dan membuat tautan di email mengarah ke alamat yang salah. Tanpa baris itu, tautan otomatis menuju http://127.0.0.1:8080/portal/....
Isi email (verifikasi, reset kata sandi, undangan) bisa dilihat dengan examguard outbox list --to email@contoh.com.
Ada dua perubahan aturan yang perlu Anda ketahui:

Tombol Mulai ujian di portal sekarang dibatasi jendela waktu, termasuk di server. Tapi examguard sim link dan link dari Integration API (LMS) sengaja tidak ikut dibatasi, karena LMS mengatur sendiri kapan peserta diarahkan ke ujian.
Sebutan “password” di portal saya ganti jadi “kata sandi”, supaya seragam dengan Admin Web.
Semua perubahan sudah tercatat di PRD v0.3.7 (§0.1, §28.4–28.6, §30.2, Q28–Q29). Berikutnya Phase 3b-2: Admin Web lanjutan, yaitu pengaturan organisasi dan anggota, integrasi LMS, audit log, dan pengaturan platform.

