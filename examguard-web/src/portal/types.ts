// Candidate Portal API shapes (server: examguard/api/candidate.py, PRD §28).

export interface Candidate {
  id: string;
  email: string;
  full_name: string;
  email_verified_at: string | null;
}

export interface PortalExam {
  id: string;
  code: string;
  name: string;
  series: string | null;
  visibility: "PUBLIC" | "PRIVATE";
  status: string;
  window_start: string | null;
  window_end: string | null;
  checkin_open: string | null;
  registration_close: string | null;
  latest_start: string | null;
  duration_minutes: number | null;
  description: string | null;
  identity_check: string | null;
  org_name: string | null;
}

export interface Enrollment {
  id: string;
  status: string;
  source: "SELF_REGISTERED" | "INVITED" | "IMPORTED" | "API" | string;
  created_at: string;
  cancelled_at: string | null;
  attempt_status: string | null;
  cancel_reason: string | null;
  attempt: { id: string; status: string; started_at: string | null; deadline: string | null; ended_at: string | null } | null;
  can_launch: boolean;
  launch_reason: "ENDED" | "EXAM_NOT_OPEN" | "NOT_YET_OPEN" | "LATE_START_CLOSED" | "NOT_ENROLLED" | null;
  can_change: boolean;
  exam: PortalExam;
}

export interface CatalogExam {
  id: string;
  org_name: string;
  code: string;
  name: string;
  description: string | null;
  series: string | null;
  window_start: string | null;
  window_end: string | null;
  duration_minutes: number | null;
  registration_open: string | null;
  registration_close: string | null;
  registration_status: "NOT_YET_OPEN" | "OPEN" | "CLOSED" | "FULL";
  seats_left: number | null;
  requires_access_code: boolean;
  identity_check: string;
}

export interface LaunchLink {
  launch_token: string;
  launch_url: string;
  expires_at: string;
  attempt_id: string;
}

export interface InvitationPreview {
  status: "PENDING" | "ACCEPTED" | "REVOKED" | "EXPIRED";
  email: string;
  expires_at: string;
  org_name: string;
  exam_name: string;
  exam_code: string;
  window_start: string | null;
  window_end: string | null;
  account_exists: boolean;
}
