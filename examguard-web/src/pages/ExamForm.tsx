import { useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, org } from "../api/client";
import type { Exam, Policy } from "../api/types";
import { ErrorNotice, Field, Loading, useToast } from "../components/ui";
import { t, type Key } from "../i18n";
import { fromLocalInput, toLocalInput, zoneLabel } from "../lib/time";

const POLICY_LOCKDOWN = [
  "fullscreen", "block_app_switching", "disable_clipboard", "disable_screenshots", "block_additional_monitors",
  "monitor_applications", "block_remote_access", "block_virtual_machines", "block_wsl",
] as const;
const POLICY_PROCTORING = [
  "require_camera", "person_detection", "face_detection", "require_microphone", "voice_activity_detection",
  "evidence_snapshot",
] as const;
const NOT_AVAILABLE = new Set(["block_virtual_machines", "block_wsl"]);

const DEFAULT_POLICY: Policy = {
  fullscreen: true, block_app_switching: true, disable_clipboard: true, disable_screenshots: true,
  block_additional_monitors: true, monitor_applications: true, allowed_applications: [], block_remote_access: true,
  block_virtual_machines: false, block_wsl: false, require_camera: true, require_microphone: true,
  person_detection: true, face_detection: true, voice_activity_detection: true, evidence_snapshot: false,
  inference_fps: 2, min_lockdown_level: "STANDARD",
};

interface FormState {
  code: string;
  name: string;
  description: string;
  visibility: "PRIVATE" | "PUBLIC";
  series: string;
  exam_url: string;
  allowed_origins: string;
  integration_level: 0 | 2;
  window_start: string;
  latest_start: string;
  window_end: string;
  duration_minutes: string;
  late_start_policy: "FIXED_END" | "FULL_DURATION";
  checkin_open: string;
  identity_check: "NONE" | "MANUAL";
  registration_open: string;
  registration_close: string;
  capacity: string;
  access_code: string;
  remove_access_code: boolean;
  min_client_version: string;
  policy: Policy;
}

function fromExam(e: Exam | null): FormState {
  return {
    code: e?.code ?? "",
    name: e?.name ?? "",
    description: e?.description ?? "",
    visibility: e?.visibility ?? "PRIVATE",
    series: e?.series ?? "",
    exam_url: e?.exam_url ?? "",
    allowed_origins: (e?.allowed_origins ?? []).join("\n"),
    integration_level: e?.integration_level ?? 2,
    window_start: toLocalInput(e?.window_start),
    latest_start: toLocalInput(e?.latest_start),
    window_end: toLocalInput(e?.window_end),
    duration_minutes: e?.duration_minutes ? String(e.duration_minutes) : "",
    late_start_policy: e?.late_start_policy ?? "FIXED_END",
    checkin_open: toLocalInput(e?.checkin_open),
    identity_check: e?.identity_check ?? "NONE",
    registration_open: toLocalInput(e?.registration_open),
    registration_close: toLocalInput(e?.registration_close),
    capacity: e?.capacity ? String(e.capacity) : "",
    access_code: "",
    remove_access_code: false,
    min_client_version: e?.min_client_version ?? "",
    policy: { ...DEFAULT_POLICY, ...(e?.policy ?? {}) },
  };
}

function toBody(f: FormState, creating: boolean, hadCode: boolean) {
  const n = (v: string) => (v.trim() === "" ? null : Number(v));
  const s = (v: string) => (v.trim() === "" ? null : v.trim());
  const body: Record<string, unknown> = {
    name: f.name.trim(),
    description: s(f.description),
    visibility: f.visibility,
    series: s(f.series),
    exam_url: s(f.exam_url),
    allowed_origins: f.allowed_origins.split(/[\s,]+/).map((x) => x.trim()).filter(Boolean),
    integration_level: f.integration_level,
    window_start: fromLocalInput(f.window_start),
    latest_start: fromLocalInput(f.latest_start),
    window_end: fromLocalInput(f.window_end),
    duration_minutes: n(f.duration_minutes),
    late_start_policy: f.late_start_policy,
    checkin_open: fromLocalInput(f.checkin_open),
    identity_check: f.identity_check,
    min_client_version: s(f.min_client_version),
    policy: { ...f.policy, inference_fps: Number(f.policy.inference_fps) },
    registration_open: f.visibility === "PUBLIC" ? fromLocalInput(f.registration_open) : null,
    registration_close: f.visibility === "PUBLIC" ? fromLocalInput(f.registration_close) : null,
    capacity: n(f.capacity),
  };
  if (f.access_code.trim()) body.access_code = f.access_code.trim();
  else if (hadCode && f.remove_access_code) body.access_code = null;
  if (creating) {
    body.code = f.code.trim();
    for (const k of Object.keys(body)) if (body[k] === null) delete body[k];
  }
  return body;
}

export function ExamForm() {
  const { examId } = useParams();
  const creating = !examId;
  const nav = useNavigate();
  const toast = useToast();
  const [exam, setExam] = useState<Exam | null>(null);
  const [f, setF] = useState<FormState>(fromExam(null));
  const [loadError, setLoadError] = useState<unknown>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (creating) return;
    api.get<Exam>(org(`/exams/${examId}`)).then((e) => { setExam(e); setF(fromExam(e)); }, setLoadError);
  }, [creating, examId]);

  const set = <K extends keyof FormState>(k: K, v: FormState[K]) => setF((x) => ({ ...x, [k]: v }));
  const setPolicy = (k: string, v: boolean | number | string) => setF((x) => ({ ...x, policy: { ...x.policy, [k]: v } }));

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const body = toBody(f, creating, !!exam?.has_access_code);
      const saved = creating
        ? await api.post<Exam>(org("/exams"), body)
        : await api.patch<Exam>(org(`/exams/${examId}`), body);
      toast(creating ? t("form.created") : t("form.saved"));
      nav(`/exams/${saved.id}/settings`);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (loadError) return <ErrorNotice error={loadError} />;
  if (!creating && !exam) return <Loading />;

  const dt = (k: keyof FormState, label: Key, hint?: Key) => (
    <Field label={t(label)} hint={hint ? t(hint) : undefined}>
      <input type="datetime-local" value={f[k] as string} onChange={(e) => set(k, e.target.value as never)} />
    </Field>
  );

  return (
    <form onSubmit={submit}>
      <div className="page-head">
        <div>
          <h1>{creating ? t("form.newTitle") : t("form.editTitle")}</h1>
          {exam && <p className="sub">{exam.code}</p>}
        </div>
        <div className="toolbar">
          <Link className="btn" to={creating ? "/exams" : `/exams/${examId}/settings`}>{t("common.cancel")}</Link>
          <button className="btn btn-primary" type="submit" disabled={busy}>{creating ? t("form.create") : t("common.save")}</button>
        </div>
      </div>
      <ErrorNotice error={error} />

      <section className="form-section">
        <header><h3>{t("form.basic")}</h3></header>
        <div className="form-grid">
          <Field label={t("form.code")} hint={t("form.codeHint")}>
            <input required pattern="[A-Za-z0-9][A-Za-z0-9_\-]{0,63}" value={f.code} disabled={!creating}
                   onChange={(e) => set("code", e.target.value)} />
          </Field>
          <Field label={t("form.name")}>
            <input required maxLength={200} value={f.name} onChange={(e) => set("name", e.target.value)} />
          </Field>
          <Field label={t("form.visibility")}>
            <select value={f.visibility} onChange={(e) => set("visibility", e.target.value as FormState["visibility"])}>
              <option value="PRIVATE">{t("vis.PRIVATE")}</option>
              <option value="PUBLIC">{t("vis.PUBLIC")}</option>
            </select>
          </Field>
          <Field label={t("form.series")} hint={t("form.seriesHint")}>
            <input maxLength={100} value={f.series} onChange={(e) => set("series", e.target.value)} />
          </Field>
        </div>
        <Field label={t("form.description")}>
          <textarea maxLength={5000} value={f.description} onChange={(e) => set("description", e.target.value)} />
        </Field>
      </section>

      <section className="form-section">
        <header><h3>{t("form.website")}</h3></header>
        <div className="form-grid">
          <Field label={t("form.examUrl")}>
            <input type="url" placeholder="https://ujian.kampus.ac.id/run" value={f.exam_url} onChange={(e) => set("exam_url", e.target.value)} />
          </Field>
          <Field label={t("form.integration")}>
            <select value={f.integration_level} onChange={(e) => set("integration_level", Number(e.target.value) as 0 | 2)}>
              <option value={2}>{t("form.integration2")}</option>
              <option value={0}>{t("form.integration0")}</option>
            </select>
          </Field>
        </div>
        <Field label={t("form.allowedOrigins")} hint={t("form.allowedOriginsHint")}>
          <textarea value={f.allowed_origins} onChange={(e) => set("allowed_origins", e.target.value)} />
        </Field>
      </section>

      <section className="form-section">
        <header>
          <h3>{t("form.timing")}</h3>
          <p>{t("form.timingHint")} ({zoneLabel()})</p>
        </header>
        <div className="form-grid">
          {dt("window_start", "form.windowStart")}
          {dt("latest_start", "form.latestStart", "form.latestStartHint")}
          {dt("window_end", "form.windowEnd")}
          {dt("checkin_open", "form.checkinOpen", "form.checkinOpenHint")}
          <Field label={t("form.duration")} hint={t("form.durationHint")}>
            <input type="number" min={1} max={1440} value={f.duration_minutes} onChange={(e) => set("duration_minutes", e.target.value)} />
          </Field>
          <Field label={t("form.lateStart")}>
            <select value={f.late_start_policy} onChange={(e) => set("late_start_policy", e.target.value as FormState["late_start_policy"])}>
              <option value="FIXED_END">{t("form.FIXED_END")}</option>
              <option value="FULL_DURATION">{t("form.FULL_DURATION")}</option>
            </select>
          </Field>
        </div>
      </section>

      {f.visibility === "PUBLIC" && (
        <section className="form-section">
          <header><h3>{t("form.registration")}</h3></header>
          <div className="form-grid">
            {dt("registration_open", "form.registrationOpen")}
            {dt("registration_close", "form.registrationClose")}
            <Field label={t("form.capacity")}>
              <input type="number" min={1} value={f.capacity} onChange={(e) => set("capacity", e.target.value)} />
            </Field>
            <Field label={t("form.accessCode")} hint={t("form.accessCodeHint")}>
              <input minLength={4} maxLength={64} value={f.access_code} onChange={(e) => set("access_code", e.target.value)} />
            </Field>
          </div>
          {exam?.has_access_code && (
            <label className="check">
              <input type="checkbox" checked={f.remove_access_code} onChange={(e) => set("remove_access_code", e.target.checked)} />
              {t("form.removeAccessCode")}
            </label>
          )}
        </section>
      )}

      <section className="form-section">
        <header>
          <h3>{t("form.policy")}</h3>
          <p>{t("form.policyHint")}</p>
        </header>
        <div className="form-grid">
          <Field label={t("form.identity")}>
            <select value={f.identity_check} onChange={(e) => set("identity_check", e.target.value as FormState["identity_check"])}>
              <option value="NONE">{t("form.identity.NONE")}</option>
              <option value="MANUAL">{t("form.identity.MANUAL")}</option>
            </select>
          </Field>
          <Field label={t("form.minLevel")}>
            <select value={String(f.policy.min_lockdown_level)} onChange={(e) => setPolicy("min_lockdown_level", e.target.value)}>
              <option value="STRICT">STRICT</option>
              <option value="STANDARD">STANDARD</option>
              <option value="RELAXED">RELAXED</option>
            </select>
          </Field>
          <Field label={t("form.fps")}>
            <input type="number" min={1} max={5} value={Number(f.policy.inference_fps)} onChange={(e) => setPolicy("inference_fps", Number(e.target.value))} />
          </Field>
          <Field label={t("form.minClient")}>
            <input placeholder="0.2.0" pattern="\d+\.\d+\.\d+" value={f.min_client_version} onChange={(e) => set("min_client_version", e.target.value)} />
          </Field>
        </div>
        <div className="form-grid">
          <div className="stack" style={{ gap: "0.5rem" }}>
            {POLICY_LOCKDOWN.map((k) => (
              <label key={k} className="check">
                <input type="checkbox" checked={!!f.policy[k]} disabled={NOT_AVAILABLE.has(k) && !f.policy[k]}
                       onChange={(e) => setPolicy(k, e.target.checked)} />
                {t(`policy.${k}` as Key)}
              </label>
            ))}
          </div>
          <div className="stack" style={{ gap: "0.5rem" }}>
            {POLICY_PROCTORING.map((k) => (
              <label key={k} className="check">
                <input type="checkbox" checked={!!f.policy[k]} onChange={(e) => setPolicy(k, e.target.checked)} />
                {t(`policy.${k}` as Key)}
              </label>
            ))}
          </div>
        </div>
      </section>
    </form>
  );
}
