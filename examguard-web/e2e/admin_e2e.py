"""End-to-end test of the Admin Web in a real browser against a running ExamGuard server.

Every step clicks through the UI, then checks the result through the API. Candidates are simulated
with the server's reference client (signed protocol), so no Rust build is needed.

Requirements (once):  pip install playwright httpx && python -m playwright install chromium
Run (server with --with-scheduler, exam created with `examguard seed live-exam --candidates 6`,
after its start time):
    python e2e/admin_e2e.py --exam LIVE-MMDD-HHMM --root-key ..\\examguard-server\\.examguard\\dev-root.key
Options: --server http://127.0.0.1:8080  --server-dir ..\\examguard-server  --headed
         --checkin-exam CODE   an exam seeded with `--identity-check MANUAL` (tests the Check-in Queue)
"""
import argparse
import os
import re
import sys
import time
from datetime import datetime

import httpx
from playwright.sync_api import Page, expect, sync_playwright

PASSWORD = "demo-password-123"
EXAM_ADMIN = "exams@pt-contoh-jaya.demo.example.com"
INVIGILATOR = "pengawas@pt-contoh-jaya.demo.example.com"

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


class Staff:
    def __init__(self, http: httpx.Client, email: str):
        self.http = http
        tok = http.post("/api/v1/staff/auth/login", json={"email": email, "password": PASSWORD}).json()["token"]
        self.h = {"Authorization": f"Bearer {tok}"}
        org = http.get("/api/v1/staff/me", headers=self.h).json()["memberships"][0]["org_id"]
        self.h["X-Org-Id"] = org

    def get(self, path):
        r = self.http.get(f"/api/v1/org{path}", headers=self.h)
        r.raise_for_status()
        return r.json()

    def post(self, path, body):
        return self.http.post(f"/api/v1/org{path}", headers=self.h, json=body)


def simulate(http: httpx.Client, server_dir: str, root_key: str, exam_code: str):
    """p1, p2 active; p3 on a second device (WAITING); p4 active with a HIGH incident."""
    sys.path.insert(0, server_dir)
    from examguard import crypto  # noqa: PLC0415
    from tests.refclient import RefClient  # noqa: PLC0415

    root = crypto.public_raw(crypto.load_private_pem(open(root_key, "rb").read()))

    def link(email):
        tok = http.post("/api/v1/candidate/auth/login", json={"email": email, "password": PASSWORD}).json()["token"]
        h = {"Authorization": f"Bearer {tok}"}
        enr = next(e for e in http.get("/api/v1/candidate/enrollments", headers=h).json()
                   if e["exam"]["code"] == exam_code)
        if enr["attempt_status"] != "NOT_STARTED":
            raise SystemExit(f"{email} already used ({enr['attempt_status']}); seed a new exam")
        return http.post(f"/api/v1/candidate/enrollments/{enr['id']}/launch", headers=h).json()["launch_token"]

    def start(email):
        rc = RefClient(http, root)
        t = link(email)
        rc.launch(t)
        assert rc.register(t).status_code == 201
        r = rc.start()
        assert r.status_code == 200, f"start {email}: {r.text} (is the start window open?)"
        return rc

    c = {n: start(f"peserta{n}@demo.example.com") for n in (1, 2, 3, 4)}
    second = RefClient(http, root)
    tok = http.post("/api/v1/candidate/auth/login",
                    json={"email": "peserta3@demo.example.com", "password": PASSWORD}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    enr = next(e for e in http.get("/api/v1/candidate/enrollments", headers=h).json() if e["exam"]["code"] == exam_code)
    t = http.post(f"/api/v1/candidate/enrollments/{enr['id']}/launch", headers=h).json()["launch_token"]
    second.launch(t)
    second.register(t)
    c[4].call("POST", "/events", {"events": [c[4].event("MULTIPLE_PERSON", confidence=0.9)]})
    for rc in c.values():
        rc.heartbeat(health={"lockdown_ok": True, "camera_ok": True, "mic_ok": True})
    return {n: rc.attempt_id for n, rc in c.items()}


# 64x48 PNG (valid; the server checks the file signature)
PNG = bytes.fromhex("89504e470d0a1a0a0000000d49484452000000400000003008020000002e29eb480000005549444154789cedcf410dc02000c040c0bf301420011d13c1e3b2a4a7a09dfbdcf1674b07bc6a406b406b406b406b406b406b406b406b406b406b406b406b406b406b406b406b406b406b406b406b406b406b40fb00f67902e4808247bd0000000049454e44ae426082")


def submit_identity(http: httpx.Client, server_dir: str, root_key: str, exam_code: str) -> str:
    sys.path.insert(0, server_dir)
    import base64  # noqa: PLC0415
    from examguard import crypto  # noqa: PLC0415
    from tests.refclient import RefClient  # noqa: PLC0415
    root = crypto.public_raw(crypto.load_private_pem(open(root_key, "rb").read()))
    tok = http.post("/api/v1/candidate/auth/login", json={"email": "peserta1@demo.example.com", "password": PASSWORD}).json()["token"]
    h = {"Authorization": f"Bearer {tok}"}
    enr = next(e for e in http.get("/api/v1/candidate/enrollments", headers=h).json() if e["exam"]["code"] == exam_code)
    t = http.post(f"/api/v1/candidate/enrollments/{enr['id']}/launch", headers=h).json()["launch_token"]
    rc = RefClient(http, root)
    rc.launch(t)
    assert rc.register(t).status_code == 201
    b64 = base64.b64encode(PNG).decode()
    r = rc.call("POST", "/identity", {"content_type": "image/png", "selfie": b64, "id_card": b64})
    assert r.status_code == 200, r.text
    return rc.attempt_id


def login(page: Page, base: str, email: str):
    page.goto(f"{base}/admin/")
    page.fill("input[type=email]", email)
    page.fill("input[type=password]", PASSWORD)
    page.click("button[type=submit]")
    expect(page.get_by_role("heading", name="Dashboard")).to_be_visible()


def run(args):
    http = httpx.Client(base_url=args.server, timeout=15)
    ea = Staff(http, EXAM_ADMIN)
    exam = next((e for e in ea.get("/exams") if e["code"] == args.exam), None)
    if not exam:
        raise SystemExit(f"exam {args.exam} not found")
    print(f"exam {args.exam}: {exam['status']}")
    ids = simulate(http, args.server_dir, args.root_key, args.exam)
    attempt = lambda n: ea.get(f"/attempts/{ids[n]}")  # noqa: E731

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not args.headed)
        page = browser.new_page(viewport={"width": 1440, "height": 900}, timezone_id="Asia/Jakarta")
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))
        base = args.server

        print("\n== Exam Admin")
        login(page, base, EXAM_ADMIN)
        row = page.locator("tr", has_text=re.compile(rf"{re.escape(args.exam)}(?![-0-9])"))
        check("dashboard lists the exam with candidates needing attention",
              lambda: (expect(row).to_contain_text("menunggu persetujuan"), expect(row).to_have_class(re.compile("attention"))))
        row.click()
        expect(page.locator("table.register")).to_be_visible()

        def add_time():
            before = attempt(1)["deadline"]
            page.get_by_role("button", name="Peserta Demo 1", exact=True).click()
            page.locator(".drawer").get_by_role("button", name="Tambah waktu").click()
            dlg = page.locator("dialog[open]")
            dlg.locator("input[type=number]").fill("5")
            btn = dlg.get_by_role("button", name="Tambah waktu")
            expect(btn).to_be_disabled()                       # reason is required
            dlg.locator("textarea").fill("kompensasi gangguan listrik")
            btn.click()
            expect(page.locator(".toast", has_text="Waktu ditambahkan.")).to_be_visible()
            after = attempt(1)["deadline"]
            delta = (datetime.fromisoformat(after) - datetime.fromisoformat(before)).total_seconds()
            assert delta == 300, f"deadline moved {delta}s"
            page.get_by_role("button", name="Tutup").click()
        check("add time from the candidate panel moves the deadline by exactly 5 minutes", add_time)

        def pause_resume():
            page.get_by_role("button", name="Peserta Demo 2", exact=True).click()
            page.locator(".drawer").get_by_role("button", name="Jeda").click()
            dlg = page.locator("dialog[open]")
            dlg.get_by_label("Dihentikan sementara").check()
            dlg.locator("textarea").fill("cek meja peserta")
            dlg.get_by_role("button", name="Jeda").click()
            expect(page.locator(".drawer .status")).to_have_text("Dijeda", timeout=5000)
            assert attempt(2)["pause_timer_mode"] == "PAUSE_TIMER"
            page.locator(".drawer").get_by_role("button", name="Lanjutkan").click()
            dlg = page.locator("dialog[open]")
            dlg.locator("textarea").fill("lanjut")
            dlg.get_by_role("button", name="Lanjutkan").click()
            expect(page.locator(".drawer .status")).to_have_text("Mengerjakan", timeout=5000)
            page.get_by_role("button", name="Tutup").click()
            row2 = page.locator("tr", has_text="Peserta Demo 2")
            expect(row2.locator(".status")).to_have_text("Mengerjakan", timeout=4000)
        check("pause with PAUSE_TIMER and resume; the register follows within 3 s", pause_resume)

        def candidate_incidents():
            row4 = page.locator("table.register tr", has_text="Peserta Demo 4")
            row4.get_by_role("button", name=re.compile("incident terbuka")).click()   # the count opens the list
            drawer = page.locator(".drawer")
            inc = drawer.locator("table.mini tbody tr").first
            expect(inc).to_be_in_viewport()
            for text in ("Lebih dari satu orang", "Tinggi", "keyakinan 90%", "sesaat", "Belum ditinjau"):
                expect(inc).to_contain_text(text)
            expect(drawer).to_contain_text("1 belum ditinjau dari 1")
            inc.click()
            dlg = page.locator("dialog[open]")
            expect(dlg).to_contain_text("Kamera menangkap lebih dari satu orang.")
            expect(dlg.locator(".timeline li")).to_have_count(1)
            dlg.get_by_role("button", name="Tutup").click()
            page.locator(".drawer-head").get_by_role("button", name="Tutup").click()
        check("incident count opens the candidate panel at a readable incident list", candidate_incidents)

        def terminate_needs_category():
            page.get_by_role("button", name="Peserta Demo 4", exact=True).click()
            page.locator(".drawer").get_by_role("button", name="Hentikan attempt").click()
            dlg = page.locator("dialog[open]")
            dlg.locator("textarea").fill("uji kategori")
            expect(dlg.get_by_role("button", name="Hentikan attempt")).to_be_disabled()
            dlg.get_by_role("button", name="Batal").click()
            page.get_by_role("button", name="Tutup").click()
            assert attempt(4)["status"] == "ACTIVE"
        check("terminate stays disabled until a reason category is chosen", terminate_needs_category)

        def reentry():
            page.get_by_role("link", name="Terputus & masuk kembali").click()
            r = page.locator("tr", has_text="Peserta Demo 3")
            r.get_by_role("button", name="Izinkan masuk kembali").click()
            dlg = page.locator("dialog[open]")
            dlg.locator("textarea").fill("laptop peserta rusak")
            dlg.get_by_role("button", name="Izinkan masuk kembali").click()
            expect(page.locator(".toast", has_text="diizinkan masuk kembali")).to_be_visible()
            assert attempt(3)["status"] == "ACTIVE"
        check("re-entry approval from the re-entry tab promotes the new device", reentry)

        def incident():
            page.get_by_role("link", name="Incident").click()
            r = page.locator("tr", has_text="Lebih dari satu orang")
            expect(r).to_have_class(re.compile("attention"))          # open + HIGH is highlighted
            r.click()
            dlg = page.locator("dialog[open]")
            dlg.locator("select").select_option("DISMISSED")
            dlg.locator("textarea").fill("bayangan di dinding")
            dlg.get_by_role("button", name="Simpan").click()
            expect(page.locator(".toast", has_text="Incident ditinjau.")).to_be_visible()
            inc = ea.get(f"/exams/{exam['id']}/incidents?attempt_id={ids[4]}")
            assert inc[0]["status"] == "DISMISSED" and inc[0]["review_note"] == "bayangan di dinding"
        check("incident review is saved with status and note", incident)

        def bulk_warning():
            page.get_by_role("link", name="Pemantauan").click()
            page.get_by_label("Pilih Peserta Demo 1").check()
            page.get_by_label("Pilih Peserta Demo 2").check()
            page.get_by_role("toolbar").get_by_role("button", name="Kirim peringatan").click()
            dlg = page.locator("dialog[open]")
            dlg.locator("textarea").first.fill("Harap tetap menghadap kamera")
            dlg.locator("textarea").nth(1).fill("pengumuman umum")
            dlg.get_by_role("button", name="Kirim peringatan").click()
            expect(page.locator(".toast", has_text="2 berhasil")).to_be_visible()
            cmds = attempt(1)["commands"]
            assert any(c["type"] == "WARNING" for c in cmds)
        check("bulk warning reaches both selected candidates", bulk_warning)

        def create_and_publish():
            code = f"E2E-{int(time.time())}"
            page.get_by_role("link", name="Ujian", exact=True).click()
            page.get_by_role("link", name="Buat ujian").first.click()
            page.get_by_label("Kode ujian").fill(code)
            page.get_by_label("Nama ujian").fill("Ujian E2E")
            page.get_by_role("button", name="Buat draf").click()
            expect(page.locator(".toast", has_text="draf")).to_be_visible()
            page.get_by_role("button", name="Publikasikan").click()
            problems = page.locator(".notice.error")
            expect(problems).to_contain_text("exam_url")
            page.get_by_role("link", name="Ubah").click()
            page.get_by_label("URL website ujian").fill("https://ujian.example.edu/run")
            now = time.time()
            fmt = lambda ts: datetime.fromtimestamp(ts).strftime("%Y-%m-%dT%H:%M")  # noqa: E731
            page.get_by_label("Mulai jendela").fill(fmt(now + 86400))
            page.get_by_label("Akhir jendela").fill(fmt(now + 86400 + 7200))
            page.get_by_role("button", name="Simpan").click()
            expect(page.locator(".toast", has_text="tersimpan")).to_be_visible()
            page.get_by_role("button", name="Publikasikan").click()
            expect(page.locator(".page-head .status")).to_have_text("Siap", timeout=5000)
            created = next(e for e in ea.get("/exams") if e["code"] == code)
            assert created["status"] == "READY" and created["latest_start"] is not None
        check("create a draft, see publish problems, fix them, publish", create_and_publish)

        page.get_by_role("button", name="Keluar").click()

        print("\n== Invigilator")
        login(page, base, INVIGILATOR)

        def invigilator_scope():
            names = page.locator("table.register tbody tr").all_inner_texts()
            assert names and all("E2E-" not in n for n in names), "unassigned exam visible"
            page.locator("tr", has_text=re.compile(rf"{re.escape(args.exam)}(?![-0-9])")).click()
            expect(page.get_by_role("button", name="Perpanjang ujian")).to_have_count(0)
            page.get_by_role("button", name="Peserta Demo 1", exact=True).click()
            drawer = page.locator(".drawer")
            expect(drawer.get_by_role("button", name="Jeda")).to_be_visible()
            expect(drawer.get_by_role("button", name="Buka kembali")).to_have_count(0)
        check("invigilator sees only assigned exams and no Exam Admin actions", invigilator_scope)

        if args.checkin_exam:
            print("\n== Check-in (Exam Admin)")
            page.keyboard.press("Escape")                         # close the candidate panel first
            page.get_by_role("button", name="Keluar").click()
            login(page, base, EXAM_ADMIN)
            cid = submit_identity(http, args.server_dir, args.root_key, args.checkin_exam)

            def checkin():
                cx = next(e for e in ea.get("/exams") if e["code"] == args.checkin_exam)
                page.goto(f"{base}/admin/exams/{cx['id']}/checkin")
                card = page.locator("section.panel", has_text="Peserta Demo 1")
                img = card.locator("img").first
                expect(img).to_be_visible(timeout=5000)
                assert img.evaluate("i => i.naturalWidth") > 0, "photo did not load"
                card.get_by_role("button", name="Setujui").click()
                page.locator("dialog[open]").get_by_role("button", name="Setujui identitas").click()
                expect(page.locator(".toast", has_text="Identitas disetujui.")).to_be_visible()
                assert ea.get(f"/attempts/{cid}")["identity_status"] == "APPROVED"
            check("check-in queue shows the decrypted photos and approval is saved", checkin)

        check("no JavaScript errors in the page", lambda: (_ for _ in ()).throw(AssertionError(errors)) if errors else None)
        browser.close()

    failed = [r for r in results if not r[1]]
    print(f"\n{len(results)} checks, {len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://127.0.0.1:8080")
    ap.add_argument("--exam", required=True)
    ap.add_argument("--root-key", required=True)
    ap.add_argument("--server-dir", default=os.environ.get("EXAMGUARD_SERVER_DIR", "../examguard-server"))
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--checkin-exam", default=None)
    sys.exit(run(ap.parse_args()))
