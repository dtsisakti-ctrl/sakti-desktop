// Shapes returned by the ExamGuard server (see server openapi.json). Only fields the UI uses.

export type AttemptStatus =
  | "NOT_STARTED" | "ACTIVE" | "PAUSED" | "INTERRUPTED" | "WAITING_FOR_INVIGILATOR" | "REOPENED"
  | "REINSTATED" | "SUBMITTED" | "EXPIRED" | "TERMINATED" | "NO_SHOW" | "FINALIZED";
export type ExamStatus = "DRAFT" | "READY" | "RUNNING" | "CLOSED" | "FINALIZED" | "CANCELLED";

export interface Membership {
  org_id: string;
  org_slug: string;
  org_name: string;
  roles: string[];
}
export interface Me {
  id: string;
  email: string;
  full_name: string;
  is_platform_admin: boolean;
  memberships: Membership[];
}

export type Policy = Record<string, boolean | number | string | string[]>;

export interface Exam {
  id: string;
  code: string;
  name: string;
  description: string | null;
  series: string | null;
  visibility: "PRIVATE" | "PUBLIC";
  status: ExamStatus;
  exam_url: string | null;
  allowed_origins: string[];
  window_start: string | null;
  latest_start: string | null;
  window_end: string | null;
  duration_minutes: number | null;
  late_start_policy: "FIXED_END" | "FULL_DURATION";
  checkin_open: string | null;
  identity_check: "NONE" | "MANUAL";
  registration_open: string | null;
  registration_close: string | null;
  capacity: number | null;
  registered_count: number;
  has_access_code: boolean;
  integration_level: 0 | 2;
  min_client_version: string | null;
  policy: Policy;
  extension_minutes: number;
}

export interface DashboardExam {
  id: string;
  code: string;
  name: string;
  status: ExamStatus;
  visibility: string;
  window_start: string | null;
  latest_start: string | null;
  window_end: string | null;
  starts_within_24h: boolean;
  enrolled: number;
  online: number;
  interrupted: number;
  waiting: number;
  paused: number;
  ended: number;
  open_incidents: number;
}
export interface Dashboard {
  server_time: string;
  totals: { online: number; interrupted: number; waiting: number; open_incidents: number; running_exams: number };
  exams: DashboardExam[];
}

export interface AttemptRow {
  attempt_id: string;
  enrollment_id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  status: AttemptStatus;
  state_version: number;
  connection_status: "ONLINE" | "OFFLINE";
  last_seen_at: string | null;
  started_at: string | null;
  deadline: string | null;
  remaining_seconds: number | null;
  paused_at: string | null;
  pause_timer_mode: string | null;
  identity_status: string;
  time_accommodation_minutes: number;
  reopen_count: number;
  reinstate_count: number;
  termination_reason_category: string | null;
  final_status: string | null;
  open_incidents: number;
  health: Record<string, unknown>;
  client_version: string | null;
}
export interface ExamAttempts {
  exam_id: string;
  exam_status: ExamStatus;
  server_time: string;
  summary: Record<string, number>;
  attempts: AttemptRow[];
}
export interface Transition {
  state_version: number;
  from_status: string;
  to_status: string;
  trigger: string;
  actor_kind: string;
  reason: string | null;
  reason_category: string | null;
  old_deadline: string | null;
  new_deadline: string | null;
  data: Record<string, unknown>;
  occurred_at: string;
}
export interface EventRow {
  event_id: string;
  type: string;
  phase: string;
  severity: string;
  started_at: string;
  ended_at: string | null;
  confidence: number | null;
  incident_status: string | null;
}
export interface AttemptDetail extends AttemptRow {
  exam_id: string;
  server_time: string;
  available_actions: string[];
  device_sessions: {
    id: string;
    status: string;
    client_version: string | null;
    os_info: Record<string, unknown>;
    created_at: string;
    revoked_at: string | null;
    revoke_reason: string | null;
    connection_status: string;
  }[];
  transitions: Transition[];
  commands: { id: string; type: string; payload: Record<string, unknown>; issued_at: string; delivery_status: string }[];
  events: EventRow[];
  incidents: Incident[];
}
export interface Incident {
  id: string;
  attempt_id: string;
  type: string;
  severity: string;
  status: string;
  started_at: string;
  ended_at: string | null;
  event_count: number;
  data: Record<string, unknown>;
  review_note: string | null;
  reviewed_at?: string | null;
  candidate_name?: string;
}
export interface ReentryRow {
  attempt_id: string;
  candidate_name: string;
  occurred_at: string;
  last_seen_at: string | null;
  gap_seconds: number | null;
  cause: string | null;
  device_changed: boolean;
  outcome: "AUTO_RESUMED" | "WAITING";
  current_status: AttemptStatus;
  state_version: number;
}
export interface CheckinItem {
  attempt_id: string;
  candidate_name: string;
  candidate_email: string;
  submission: number;
  retries_left: number;
  photos: { id: string; kind: "SELFIE" | "ID_CARD"; url: string; created_at: string }[];
}
export interface Enrollment {
  id: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  source: string;
  status: string;
  time_accommodation_minutes: number;
  created_at: string;
  cancel_reason: string | null;
}
export interface Invitation {
  id: string;
  email: string;
  status: string;
  expires_at: string;
  created_at: string;
}
export interface Invigilator {
  user_id: string;
  email: string;
  full_name: string;
  assigned_at?: string;
}
