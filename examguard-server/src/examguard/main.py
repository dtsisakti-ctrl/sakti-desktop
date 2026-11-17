"""FastAPI application factory."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DBAPIError

from . import __version__
from .api import attempts, candidate, client, integration, platform, proctoring, staff
from .errors import AppError

log = logging.getLogger("examguard")


def create_app() -> FastAPI:
    app = FastAPI(title="ExamGuard Server", version=__version__,
                  description="Phase 1b — tenancy, accounts, exams, registration, audit chain, attempt state & timing engine, client protocol, integration API.")

    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        body = {"error": {"code": exc.code, "message": exc.message}}
        if exc.details is not None:
            body["error"]["details"] = exc.details
        # details may hold datetimes/UUIDs (e.g. window_start): encode them, never turn a 4xx into a 500
        return JSONResponse(status_code=exc.status, content=jsonable_encoder(body))

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(status_code=422, content={"error": {
            "code": "VALIDATION_ERROR", "message": "request validation failed", "details": details}})

    @app.exception_handler(DBAPIError)
    async def _db_error(_: Request, exc: DBAPIError):
        # RLS / privilege violations surface as 42501; never leak SQL to clients.
        code = getattr(getattr(exc, "orig", None), "sqlstate", None)
        if code == "42501":
            return JSONResponse(status_code=403, content={"error": {
                "code": "FORBIDDEN", "message": "operation not permitted"}})
        log.exception("database error")
        return JSONResponse(status_code=500, content={"error": {
            "code": "INTERNAL", "message": "internal error"}})

    @app.get("/healthz", tags=["meta"])
    def healthz():
        return {"status": "ok", "version": __version__}

    for r in (candidate.public, candidate.router, staff.auth_router, staff.router, attempts.router, platform.router,
                   client.router, client.well_known, integration.router, integration.admin,
                   proctoring.router):
        app.include_router(r)
    from . import webui
    webui.mount(app)
    return app


app = create_app()
