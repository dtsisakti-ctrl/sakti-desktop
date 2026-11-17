"""Transactional email via an outbox table.

Messages are written in the same transaction as the business change. A separate
sender (Phase 3) delivers them; in development they can be read with `examguard outbox list`.
"""
from sqlalchemy.orm import Session

from .config import get_settings
from .db import elevated
from .models import EmailOutbox

TEMPLATES: dict[str, tuple[str, str]] = {
    "candidate_verify_email": (
        "Verifikasi email ExamGuard",
        "Halo {name},\n\nVerifikasi email Anda dengan kode berikut:\n{token}\n\n"
        "atau buka: {portal}/verify-email?token={token}\n",
    ),
    "candidate_password_reset": (
        "Atur ulang kata sandi ExamGuard",
        "Halo {name},\n\nKami menerima permintaan untuk mengatur ulang kata sandi akun ExamGuard Anda.\n"
        "Buka tautan berikut dalam {minutes} menit:\n{portal}/reset-password?token={token}\n\n"
        "Abaikan email ini bila Anda tidak memintanya; kata sandi lama tetap berlaku.\n",
    ),
    "registration_confirmed": (
        "Pendaftaran terkonfirmasi: {exam_name}",
        "Halo {name},\n\nPendaftaran Anda untuk {exam_name} ({window_start}) sudah terkonfirmasi.\n",
    ),
    "registration_cancelled": (
        "Pendaftaran dibatalkan: {exam_name}",
        "Halo {name},\n\nPendaftaran Anda untuk {exam_name} dibatalkan. Alasan: {reason}\n",
    ),
    "registration_moved": (
        "Jadwal ujian dipindahkan: {exam_name}",
        "Halo {name},\n\nPendaftaran Anda dipindahkan ke {exam_name} ({window_start}).\n",
    ),
    "invitation": (
        "Undangan ujian: {exam_name}",
        "Anda diundang oleh {org_name} untuk mengikuti {exam_name}.\n\n"
        "Kode undangan: {token}\natau buka: {portal}/invitations/accept?token={token}\n"
        "Undangan berlaku sampai {expires_at}.\n",
    ),
}


def enqueue(db: Session, to_email: str, template: str, **ctx: object) -> None:
    subject_t, body_t = TEMPLATES[template]
    ctx.setdefault("portal", get_settings().portal_url)
    with elevated(db, "system"):
        db.add(EmailOutbox(to_email=to_email, template=template,
                           subject=subject_t.format(**ctx), body=body_t.format(**ctx)))
