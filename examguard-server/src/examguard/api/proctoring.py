"""Check-in Queue, emergency unlock and incidents (Admin Web backend, PRD §22, §27.8, §27.13)."""
from uuid import UUID

from fastapi import APIRouter, Query, Response

from ..schemas import BackupCodesIn, EmergencyUnlockIn, IncidentReviewIn, UnlockResponseIn
from ..services import proctoring as svc
from .deps import DB, OrgPrincipal

router = APIRouter(prefix="/api/v1/org", tags=["check-in, unlock & incidents"])


@router.get("/exams/{exam_id}/checkin-queue")
def checkin_queue(db: DB, p: OrgPrincipal, exam_id: UUID):
    """Candidates waiting for identity approval, with links to their photos."""
    return svc.checkin_queue(db, p, exam_id)


@router.get("/identity-photos/{photo_id}", response_class=Response,
            responses={200: {"content": {"image/jpeg": {}, "image/png": {}, "image/webp": {}}}})
def identity_photo(db: DB, p: OrgPrincipal, photo_id: UUID):
    data, content_type = svc.photo(db, p, photo_id)
    return Response(data, media_type=content_type, headers={"Cache-Control": "no-store"})


@router.post("/attempts/{attempt_id}/emergency-unlock")
def emergency_unlock(db: DB, p: OrgPrincipal, attempt_id: UUID, body: EmergencyUnlockIn):
    """Online method: sends a signed EMERGENCY_UNLOCK command to the connected client."""
    return svc.online_unlock(db, p, attempt_id, body.reason)


@router.post("/attempts/{attempt_id}/unlock-response")
def unlock_response(db: DB, p: OrgPrincipal, attempt_id: UUID, body: UnlockResponseIn):
    """Challenge–response method: the client is offline, the invigilator types its challenge here."""
    return svc.unlock_response(db, p, attempt_id, body.challenge, body.reason)


@router.post("/exams/{exam_id}/backup-codes", status_code=201)
def backup_codes(db: DB, p: OrgPrincipal, exam_id: UUID, body: BackupCodesIn):
    """Printable one-time codes for when server and Admin Web are both unreachable. Shown once."""
    return svc.create_backup_codes(db, p, exam_id, body.count)


@router.get("/exams/{exam_id}/incidents")
def incidents(db: DB, p: OrgPrincipal, exam_id: UUID, status: str | None = Query(None),
              severity: str | None = Query(None), attempt_id: UUID | None = Query(None)):
    """Open incidents first, then by severity (HIGH → INFO) and time."""
    return svc.list_incidents(db, p, exam_id, status, severity, attempt_id)


@router.get("/incidents/{incident_id}")
def incident(db: DB, p: OrgPrincipal, incident_id: UUID):
    return svc.incident_detail(db, p, incident_id)


@router.post("/incidents/{incident_id}/review")
def review(db: DB, p: OrgPrincipal, incident_id: UUID, body: IncidentReviewIn):
    return svc.review_incident(db, p, incident_id, body.status, body.note)
