# ExamGuard Web — Admin Web (Phase 3a) dan Candidate Portal (Phase 3b-1)

Satu proyek React 18 + Vite + TypeScript, tanpa library UI, dengan tiga halaman masuk:

| Alamat | Untuk | Kode |
|---|---|---|
| `/` | Halaman masuk: pilih peserta atau staf | `index.html`, `src/landing.tsx` |
| `/admin/` | Admin Web (PRD §27): Exam Admin, pengawas, Org Admin | `admin/index.html`, `src/main.tsx`, `src/pages` |
| `/portal/` | Candidate Portal (PRD §28): peserta | `portal/index.html`, `src/portal` |

Koneksi API, bahasa, format waktu, dan gaya tampilan dipakai bersama. Bahasa Indonesia; semua teks
ada di `src/i18n/id.ts` sehingga terjemahan Inggris tinggal ditambahkan (§25).

**Untuk sekadar memakai UI, Node.js tidak diperlukan.** Hasil build sudah ikut di paket server dan
disajikan oleh `examguard serve` di **http://127.0.0.1:8080/**. Folder ini hanya dibutuhkan kalau
Anda ingin mengubah UI.

## Isi Candidate Portal (Phase 3b-1)

| Layar | PRD | Isi |
|---|---|---|
| Masuk, buat akun, verifikasi email | §28.1 | Nama sesuai kartu identitas; kirim ulang tautan verifikasi |
| Lupa / atur ulang kata sandi | §28.1 | Tautan email 60 menit; semua sesi dikeluarkan |
| Ujian saya | §28.4 | Kartu ujian: tanggal, jam, check-in, batas mulai, durasi, hitung mundur; **Mulai ujian** aktif dari check-in sampai batas mulai (dan untuk membuka ulang saat ujian berjalan); batalkan/pindah sesi; riwayat |
| Katalog ujian publik | §28.1–28.2 | Filter teks, jenis tes, tanggal; sisa kursi; kode akses; daftar; pindah sesi dalam jenis tes yang sama |
| Undangan | §28.3 | Isi undangan sebelum masuk; buat akun/masuk dengan email tujuan; terima |
| Profil | §28.1 | Ubah nama, ganti kata sandi |

Setelah **Mulai ujian**, browser membuka `examguard://launch?t=...`. Selama client desktop belum ada,
tautan itu bisa disalin dari dialog (bagian *Untuk pengujian dengan eg-sim*) lalu dipakai:
`eg-sim launch "<tautan>"`.

## Isi Admin Web (Phase 3a)

| Layar | PRD | Isi |
|---|---|---|
| Login & pemilih organisasi | §27.1 | Sesi staf; pindah organisasi bila tergabung di beberapa |
| Dashboard | §27.2 | Ujian siap/berjalan/ditutup, jumlah online, terputus, menunggu persetujuan, incident |
| Daftar & formulir ujian | §27.3–27.4 | Buat/ubah draf, kebijakan keamanan & proctoring, publikasi dengan daftar masalah, kembali ke draf, batalkan |
| Pemantauan (Live Monitoring) | §27.5 | Register peserta bernomor, baris yang butuh perhatian disorot, filter, cari, sisa waktu berjalan, aksi massal |
| Panel peserta (Candidate Detail) | §27.6–27.7 | Fakta, kesehatan perangkat, **daftar incident** (waktu, kejadian, durasi, rincian, tinjauan; dibuka juga dari angka incident di register), aksi sesuai status & peran, timeline event, riwayat status, perangkat, perintah |
| Check-in | §27.13 | Foto selfie & kartu identitas, setujui/tolak |
| Incident | §27.8 | Terbuka/semua, detail event, tinjau dengan catatan |
| Terputus & masuk kembali | §27.9 | Jeda, penyebab, izinkan/tolak |
| Peserta | §27.12 (sebagian) | Daftar peserta, undangan email, akomodasi waktu, batalkan pendaftaran |
| Pengawas | §27.3 | Tugaskan/lepas pengawas |
| Aksi ujian | §27.10, §22 | Perpanjang, finalisasi, kode cadangan emergency unlock (bisa dicetak) |

Phase 3b-2 menyusul: pengaturan organisasi & anggota, integrasi LMS, audit log, pengaturan platform;
lalu terjemahan Inggris.

**Pembaruan langsung.** Pemantauan dan panel peserta memuat ulang setiap 2 detik selama tab terlihat
(target PRD §25: perubahan tampil < 3 detik). Terputus dan Offline selalu muncul bersamaan: client yang
tertutup tampil dalam ≤ 2 detik, jaringan yang hilang diam-diam setelah ambang ujian (default 30 detik); sisa waktu berdetak di browser di antara pemuatan. Aksi mengirim
`expected_state_version`, sehingga bila dua pengawas bertindak bersamaan yang kedua mendapat pesan
dan data dimuat ulang, bukan menimpa.

## Mengubah UI (butuh Node.js 20+)

```bat
cd examguard-web
npm install
npm run dev            :: http://localhost:5173/ (/admin/, /portal/) — API diteruskan ke server :8080
```

Server harus berjalan (`examguard serve --port 8080 --with-scheduler`). Setelah selesai mengubah:

```bat
npm run build
npm run install-to-server     :: menyalin dist\ ke ..\examguard-server\src\examguard\webui\site
```

Alamat server lain: `set EXAMGUARD_SERVER=http://host:port` sebelum `npm run dev`; folder server
lain: `set EXAMGUARD_SERVER_DIR=...` sebelum `install-to-server`.

## Test

```bat
npm test               :: 22 unit test logika (hitung mundur, sorotan, incident, kartu ujian, katalog, i18n)
npm run typecheck
```

**End-to-end di browser sungguhan** (opsional; klik di UI lalu cek hasilnya lewat API):

```bat
pip install playwright httpx
python -m playwright install chromium

:: di folder server, server berjalan dengan --with-scheduler
examguard seed live-exam --in-minutes 1 --candidates 6
examguard seed live-exam --in-minutes 20 --candidates 2 --identity-check MANUAL

:: di folder examguard-web, setelah jam mulai ujian pertama lewat
python e2e\admin_e2e.py --exam LIVE-MMDD-HHMM --checkin-exam LIVE-MMDD-HHMM ^
    --root-key ..\examguard-server\.examguard\dev-root.key
```

Peserta disimulasikan lewat client referensi server, jadi tidak perlu build Rust. Hasil yang
diharapkan: `12 checks, 12 passed, 0 failed`. Setiap peserta hanya bisa dipakai sekali; untuk
mengulang, buat ujian baru.

**End-to-end Candidate Portal**: peserta baru membuat akun, verifikasi email, menerima undangan,
mendaftar dan pindah sesi ujian publik, membatalkan, mengatur ulang kata sandi, lalu memulai ujian;
Admin Web harus menampilkannya sebagai Mengerjakan. Undangan harus diterima sebelum ujian mulai, jadi
jalankan segera setelah membuat ujian:

```bat
:: di folder server
examguard seed live-exam --in-minutes 2 --candidates 1

:: di folder examguard-web (email dibaca dengan `examguard outbox list` di --server-dir)
python e2e\portal_e2e.py --exam LIVE-MMDD-HHMM --root-key ..\examguard-server\.examguard\dev-root.key
```

Hasil yang diharapkan: `10 checks, 10 passed, 0 failed` (test menunggu jam mulai ujian, ±2 menit).

## Struktur

```text
src/
  api/          klien fetch (token + X-Org-Id) dan tipe respons server
  auth/         sesi staf dan organisasi aktif
  portal/       Candidate Portal: sesi peserta, halaman, tipe API
  landing.tsx   halaman masuk (/)
  i18n/         kamus teks (id.ts) dan t()/tx()
  lib/          format waktu, hook pemuatan berkala
  components/   Layout, mistar waktu, dialog aksi, komponen kecil
  pages/        Dashboard, Ujian, formulir, detail ujian, panel peserta, tabs/
  styles/       app.css (token desain), portal.css
e2e/            test end-to-end Playwright
```

## Desain

Konsepnya daftar hadir ujian: register bernomor dengan sorotan kuning stabilo hanya untuk peserta
yang perlu ditangani (terputus, menunggu persetujuan, incident terbuka, offline, menunggu
check-in). Mistar waktu di atas register menunjukkan mulai, batas mulai, akhir, dan sekarang.
Huruf Public Sans dibundel lokal sehingga UI tidak butuh internet di ruang ujian.

Candidate Portal memakai kertas, tinta, dan stabilo yang sama. Unsurnya sendiri adalah **kartu ujian**:
kartu dengan sobekan tanggal di kiri; kartu yang bisa dikerjakan sekarang (check-in dibuka atau ujian
berjalan) diberi tepi stabilo, seperti baris yang perlu ditangani di register pengawas.
