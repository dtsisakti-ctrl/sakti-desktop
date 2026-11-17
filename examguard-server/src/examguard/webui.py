"""Serve the built web UI (React, examguard-web): landing page, Admin Web and Candidate Portal.

    /            landing page: "Masuk sebagai peserta" or "Masuk sebagai staf"
    /admin/...   Admin Web (PRD §27)
    /portal/...  Candidate Portal (PRD §28)
    /assets/...  hashed JS/CSS shared by all three

The production build is copied into ``examguard/webui/site`` so the server needs no Node.js.
Client-side routes fall back to the app's ``index.html``. During UI development run the Vite dev
server instead (``npm run dev`` in examguard-web, which proxies /api to this server).
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response

from .config import get_settings

PACKAGED = Path(__file__).parent / "webui" / "site"
APPS = ("admin", "portal")

_MISSING = """<!doctype html><meta charset="utf-8"><title>ExamGuard</title>
<body style="font-family:system-ui;max-width:40rem;margin:4rem auto;line-height:1.5">
<h1>Web UI belum dibangun</h1>
<p>Folder <code>{path}</code> tidak berisi <code>{file}</code>. Bangun UI dengan
<code>npm run build</code> lalu <code>npm run install-to-server</code> di folder <code>examguard-web</code>,
atau pakai server zip yang sudah berisi build.</p>
<p>API tetap tersedia di <a href="/docs">/docs</a>.</p></body>"""

_IMMUTABLE = {"Cache-Control": "public, max-age=31536000, immutable"}
_REVALIDATE = {"Cache-Control": "no-cache"}


def ui_dir() -> Path:
    custom = get_settings().web_ui_dir
    return Path(custom) if custom else PACKAGED


def _page(base: Path, rel: str) -> Response:
    index = base / rel
    if not index.is_file():
        return HTMLResponse(_MISSING.format(path=base, file=rel), status_code=503)
    return FileResponse(index, headers=_REVALIDATE)


def _inside(base: Path, path: str) -> Path | None:
    target = (base / path).resolve()
    return target if path and target.is_file() and base in target.parents else None


def mount(app: FastAPI) -> None:
    @app.get("/", include_in_schema=False)
    def landing():
        return _page(ui_dir().resolve(), "index.html")

    @app.get("/assets/{path:path}", include_in_schema=False)
    def assets(path: str):
        base = (ui_dir() / "assets").resolve()
        target = _inside(base, path)
        if target is None:
            return Response(status_code=404)
        return FileResponse(target, headers=_IMMUTABLE)   # hashed names never change

    for name in APPS:
        def make(app_name: str):
            def root():
                return RedirectResponse(f"/{app_name}/")

            def page(path: str):
                base = (ui_dir() / app_name).resolve()
                target = _inside(base, path)
                if target is not None:
                    return FileResponse(target, headers=_REVALIDATE)
                return _page(base, "index.html")
            return root, page

        root, page = make(name)
        app.add_api_route(f"/{name}", root, methods=["GET"], include_in_schema=False)
        app.add_api_route(f"/{name}/{{path:path}}", page, methods=["GET"], include_in_schema=False)
