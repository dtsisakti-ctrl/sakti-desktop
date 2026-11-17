"""Event dictionary (PRD §15): default severity and whether an event opens an incident."""
SEVERITIES = ("INFO", "LOW", "MEDIUM", "HIGH")

# type -> (severity, creates_incident)
CATALOG: dict[str, tuple[str, bool]] = {
    **{t: ("INFO", False) for t in (
        "EXAM_STARTED", "EXAM_SUBMITTED", "EXAM_EXPIRED", "EXAM_PAUSED", "EXAM_RESUMED", "DEADLINE_UPDATED",
        "EXAM_TERMINATED", "REENTRY_REQUESTED", "REENTRY_APPROVED", "REENTRY_REJECTED",
        "IDENTITY_CHECK_SUBMITTED", "IDENTITY_CHECK_APPROVED")},
    "CLIENT_CRASH_RECOVERED": ("LOW", False),
    "IDENTITY_CHECK_REJECTED": ("LOW", False),
    "UNMONITORED_INTERRUPTION": ("MEDIUM", True),
    "EMERGENCY_UNLOCK_USED": ("HIGH", True),
    "OFFLINE_AUTO_RELEASE": ("MEDIUM", True),
    "FACE_MISSING": ("MEDIUM", True),
    "VOICE_ACTIVITY": ("MEDIUM", True),
    "MULTIPLE_FACES": ("HIGH", True),
    "MULTIPLE_PERSON": ("HIGH", True),
    "CAMERA_UNAVAILABLE": ("HIGH", True),        # MEDIUM when the camera is not required
    "CAMERA_DISCONNECTED": ("HIGH", True),
    "MICROPHONE_UNAVAILABLE": ("MEDIUM", True),
    "MICROPHONE_DISCONNECTED": ("MEDIUM", True),
    "PROHIBITED_APP": ("HIGH", True),
    "REMOTE_ACCESS_DETECTED": ("HIGH", True),
    "VIRTUAL_MACHINE_DETECTED": ("HIGH", True),
    "ADDITIONAL_MONITOR": ("HIGH", True),
    "FOCUS_LOST": ("MEDIUM", True),
    "SCREEN_CAPTURE_ATTEMPT": ("MEDIUM", True),
    "NAVIGATION_BLOCKED": ("LOW", False),
    "CLIPBOARD_BLOCKED": ("LOW", False),
    "TAMPER_DETECTED": ("HIGH", True),
    "CLIENT_INTEGRITY_FAILED": ("HIGH", True),
}


def classify(event_type: str, policy: dict) -> tuple[str, bool]:
    """Unknown types (newer clients) are stored as INFO without an incident."""
    severity, incident = CATALOG.get(event_type, ("INFO", False))
    if event_type.startswith("CAMERA_") and not policy.get("require_camera", True):
        severity = "MEDIUM"
    override = (policy.get("severity_overrides") or {}).get(event_type)
    if override in SEVERITIES:
        severity = override
    return severity, incident
