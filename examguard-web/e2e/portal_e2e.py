"""End-to-end test of the Candidate Portal in a real browser against a running ExamGuard server.

A new candidate signs up, verifies the email, registers for a public exam, moves to another session,
cancels, resets the password, accepts an invitation to a live exam and starts it. The launch link
from the portal is redeemed by the server's reference client (signed protocol, no Rust build needed),
and the Admin Web must then show the candidate as working.

Requirements (once):  pip install playwright httpx && python -m playwright install chromium
Run from examguard-web, right after `examguard seed live-exam --in-minutes 2 --candidates 1`
(the invitation must be accepted before the exam starts):
    python e2e/portal_e2e.py --exam LIVE-MMDD-HHMM --root-key ..\\examguard-server\\.examguard\\dev-root.key
Options: --server http://127.0.0.1:8080  --server-dir ..\\examguard-server  --headed
The emails (verification, reset, invitation) are read with `examguard outbox list`, run in --server-dir.
"""
import argparse
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

import httpx
from playwright.sync_api import Page, expect, sync_playwright

PASSWORD = "demo-password-123"
NEW_PASSWORD = "password-baru-untuk-e2e"
EXAM_ADMIN = "exams@pt-contoh-jaya.demo.example.com"

results: list[tuple[str, bool, str]] = []


def check(name: str, fn) -> None:
    try:
        fn()
        results.append((name, True, ""))
        print(f"  PASS {name}")
    except Exception as e:  # noqa: BLE001 — report every failed step and continue
        msg = str(e).splitlines()[0][:200]
        results.append((name, False, msg))
        print(f"  FAIL {name}: {msg}")


def email_link(server_dir: str, to: str, template: str) -> str:
    """Latest link of `template` sent to `to`, from the development outbox."""
    out = subprocess.run(["examguard", "outbox", "list", "--to", to, "--limit", "20"], cwd=server_dir,
                         capture_output=True, text=True, check=True).stdout
    for block in re.split(r"(?m)^#\d+ ", out):
        if f"[{template}]" in block:
            m = re.search(r"(https?://\S+token=[\w-]+)", block)
            if m:
                return m.group(1)
    raise AssertionError(f"no {template} email with a link for {to}")


class Staff:
    def __init__(self, http: httpx.Client, email: str):
        self.http = http
        tok = http.post("/api/v1/staff/auth/login", json={"email": email, "password": PASSWORD}).json()["token"]
        self.h = {"Authorization": f"Bearer {tok}"}
        self.h["X-Org-Id"] = http.get("/api/v1/staff/me", headers=self.h).json()["memberships"][0]["org_id"]

    def get(self, path):
        r = self.http.get(f"/api/v1/org{path}", headers=self.h)
        r.raise_for_status()
        return r.json()

    def post(self, path, body):
        r = self.http.post(f"/api/v1/org{path}", headers=self.h, json=body)
        assert r.status_code < 300, r.text
        return r.json()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--exam", required=True, help="a live exam seeded a few minutes before its start")
    ap.add_argument("--root-key", required=True)
    ap.add_argument("--server-dir", default=os.environ.get("EXAMGUARD_SERVER_DIR", "../examguard-server"))
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()
    base = args.server.rstrip("/")
    http = httpx.Client(base_url=base, timeout=15)
    staff = Staff(http, EXAM_ADMIN)
    live = next(e for e in staff.get("/exams") if e["code"] == args.exam)
    if live["status"] != "READY":
        print(f"{args.exam} is {live['status']}; seed a new one with --in-minutes 2 and run right away")
        return 2
    email = f"e2e-{int(time.time())}@peserta.example.com"
    print(f"candidate {email}, live exam {args.exam}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=not args.headed)
        ctx = browser.new_context(viewport={"width": 1366, "height": 860}, locale="id-ID", timezone_id="Asia/Jakarta")
        page: Page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        def landing_and_signup():
            page.goto(f"{base}/")
            page.get_by_role("link", name=re.compile("Masuk sebagai peserta")).click()
            expect(page.get_by_role("heading", name="Masuk sebagai peserta")).to_be_visible()
            page.get_by_role("link", name="Buat akun").click()
            page.get_by_label("Nama lengkap (sesuai kartu identitas)").fill("Peserta Uji E2E")
            page.get_by_label("Email").fill(email)
            page.get_by_label("Kata sandi", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Buat akun").click()
            expect(page.locator(".notice.ok")).to_contain_text(email)
        check("landing page leads to sign-up; account created", landing_and_signup)

        def verify_and_login():
            link = email_link(args.server_dir, email, "candidate_verify_email")
            assert link.startswith(f"{base}/portal/verify-email?token="), link
            page.goto(link)
            expect(page.locator(".notice.ok")).to_contain_text("terverifikasi")
            page.get_by_role("link", name="Ke halaman masuk").click()
            page.get_by_label("Email").fill(email)
            page.get_by_label("Kata sandi", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Masuk").click()
            expect(page.get_by_role("heading", name="Ujian saya")).to_be_visible()
            expect(page.locator(".notice.warn")).to_have_count(0)        # no "unverified" banner
        check("email link verifies the account; sign-in opens Ujian saya", verify_and_login)

        def invitation():
            staff.post(f"/exams/{live['id']}/invitations", {"emails": [email]})
            link = email_link(args.server_dir, email, "invitation")
            page.get_by_role("button", name="Keluar").click()
            page.goto(link)
            expect(page.locator(".invite-card")).to_contain_text(live["name"])
            page.get_by_role("link", name="Masuk", exact=True).click()
            expect(page.get_by_label("Email")).to_have_value(email)
            page.get_by_label("Kata sandi", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Masuk").click()
            page.get_by_role("button", name="Terima undangan").click()  # back on the invitation after sign-in
            expect(page.locator(".toast", has_text="Undangan diterima")).to_be_visible()
            ticket = page.locator("article.ticket", has_text=live["name"])
            expect(ticket).to_have_class(re.compile("ticket-open"))      # check-in is open: highlighted
            expect(ticket.get_by_role("button", name="Mulai ujian")).to_be_enabled()
        check("invitation link: preview, sign in, accept; the exam can be started", invitation)

        def register_move_cancel():
            page.get_by_role("link", name="Katalog ujian").click()
            page.get_by_label("Jenis tes").select_option("EPT")
            a = page.locator("article.ticket", has_text="Sesi A")
            a.get_by_role("button", name="Daftar").click()
            page.locator("dialog[open]").get_by_role("button", name="Daftar").click()
            expect(page.locator(".toast", has_text="terkonfirmasi")).to_be_visible()
            t = page.locator("article.ticket", has_text="Sesi A")
            expect(t).to_contain_text("Check-in dibuka dalam")
            expect(t.get_by_role("button", name="Mulai ujian")).to_be_disabled()
            t.get_by_role("link", name="Pindah sesi").click()
            b = page.locator("article.ticket", has_text="Sesi B")
            b.get_by_role("button", name="Pindah ke sesi ini").click()
            page.locator("dialog[open]").get_by_role("button", name="Pindah sesi").click()
            expect(page.locator(".toast", has_text="dipindahkan")).to_be_visible()
            expect(page.locator(".history")).to_contain_text("Dipindahkan ke sesi lain")
            page.locator("article.ticket", has_text="Sesi B").get_by_role("button", name="Batalkan pendaftaran").click()
            page.locator("dialog[open]").get_by_role("button", name="Ya, batalkan").click()
            expect(page.locator(".toast", has_text="dibatalkan")).to_be_visible()
            expect(page.locator(".history")).to_contain_text("Dibatalkan oleh Anda")
            expect(page.locator("article.ticket", has_text="Sesi B")).to_have_count(0)
        check("public exam: register, move to another session, cancel", register_move_cancel)

        def profile_name():
            page.get_by_role("link", name="Profil").click()
            page.get_by_label("Nama lengkap (sesuai kartu identitas)").fill("Peserta Uji E2E Lengkap")
            page.get_by_role("button", name="Simpan").click()
            expect(page.locator(".toast", has_text="Profil disimpan")).to_be_visible()
            expect(page.locator(".topbar-user")).to_have_text("Peserta Uji E2E Lengkap")
        check("profile: the name as on the identity card is saved", profile_name)

        def forgot_password():
            page.get_by_role("button", name="Keluar").click()
            page.get_by_role("link", name="Lupa kata sandi?").click()
            page.get_by_label("Email").fill(email)
            page.get_by_role("button", name="Kirim tautan").click()
            expect(page.locator(".notice.ok")).to_be_visible()
            page.goto(email_link(args.server_dir, email, "candidate_password_reset"))
            page.get_by_label("Kata sandi baru").fill(NEW_PASSWORD)
            page.get_by_label("Ulangi kata sandi").fill(NEW_PASSWORD)
            page.get_by_role("button", name="Simpan kata sandi").click()
            expect(page.locator(".notice.ok")).to_contain_text("Kata sandi diganti")
            page.get_by_role("link", name="Ke halaman masuk").click()
            page.get_by_label("Email").fill(email)
            page.get_by_label("Kata sandi", exact=True).fill(PASSWORD)
            page.get_by_role("button", name="Masuk").click()
            expect(page.locator(".notice.error")).to_contain_text("salah")     # old password refused
            page.get_by_label("Kata sandi", exact=True).fill(NEW_PASSWORD)
            page.get_by_role("button", name="Masuk").click()
            expect(page.get_by_role("heading", name="Ujian saya")).to_be_visible()
        check("forgot password: email link sets a new password; the old one stops working", forgot_password)

        state: dict = {}

        def start_exam():
            start = datetime.fromisoformat(live["window_start"].replace("Z", "+00:00"))
            wait = (start - datetime.now(timezone.utc)).total_seconds() + 2
            if wait > 0:
                print(f"    ... waiting {wait:.0f} s for the exam window to open")
                time.sleep(wait)
            page.reload()
            ticket = page.locator("article.ticket", has_text=live["name"])
            ticket.get_by_role("button", name="Mulai ujian").click()
            dlg = page.locator("dialog[open]")
            expect(dlg).to_contain_text("Membuka ExamGuard")
            dlg.locator("summary").click()
            url = dlg.get_by_test_id("launch-url").inner_text()
            assert url.startswith("examguard://launch?t="), url
            token = url.split("t=", 1)[1]
            sys.path.insert(0, args.server_dir)
            from examguard import crypto  # noqa: PLC0415
            from tests.refclient import RefClient  # noqa: PLC0415
            root = crypto.public_raw(crypto.load_private_pem(open(args.root_key, "rb").read()))
            rc = RefClient(http, root)
            rc.launch(token)
            assert rc.register(token).status_code == 201
            r = rc.start()
            assert r.status_code == 200, r.text
            rc.heartbeat(health={"lockdown_ok": True})
            state["rc"] = rc
            dlg.get_by_role("button", name="Tutup").click()
            page.reload()
            expect(page.locator("article.ticket", has_text=live["name"])
                   .get_by_role("button", name="Buka kembali ExamGuard")).to_be_visible()
        check("Mulai ujian gives a launch link; the client starts the exam with it", start_exam)

        def admin_sees_candidate():
            admin = ctx.new_page()
            admin.goto(f"{base}/admin/")
            admin.get_by_label("Email").fill(EXAM_ADMIN)
            admin.get_by_label("Kata sandi").fill(PASSWORD)
            admin.get_by_role("button", name="Masuk").click()
            expect(admin.get_by_role("heading", name="Dashboard")).to_be_visible()
            admin.goto(f"{base}/admin/exams/{live['id']}")
            row = admin.locator("table.register tr", has_text="Peserta Uji E2E Lengkap")
            expect(row).to_contain_text("Mengerjakan", timeout=5000)
            expect(row).to_contain_text("Online")
            admin.close()
        check("Admin Web shows the portal candidate as working and online", admin_sees_candidate)

        def separate_sessions():
            # signing in as staff did not touch the candidate session in the same browser
            page.reload()
            expect(page.get_by_role("heading", name="Ujian saya")).to_be_visible()
        check("candidate and staff sessions stay separate in one browser", separate_sessions)

        check("no JavaScript errors in the page", lambda: (_ for _ in ()).throw(AssertionError(errors)) if errors else None)
        browser.close()

    passed = sum(ok for _, ok, _ in results)
    print(f"\n{len(results)} checks, {passed} passed, {len(results) - passed} failed")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
