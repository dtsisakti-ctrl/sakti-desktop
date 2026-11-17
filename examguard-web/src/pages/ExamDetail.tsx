import { useState } from "react";
import { Link, NavLink, Navigate, Route, Routes, useNavigate, useParams } from "react-router-dom";
import { api, ApiError, org } from "../api/client";
import type { Exam } from "../api/types";
import { useSession } from "../auth/session";
import { Ruler } from "../components/Ruler";
import { ErrorNotice, ExamStatus, Field, Loading, Modal, errorText, useToast } from "../components/ui";
import { t, tx, type Key } from "../i18n";
import { useLoad, useTick } from "../lib/hooks";
import { dateTime, zoneLabel } from "../lib/time";
import { Candidates } from "./tabs/Candidates";
import { Checkin } from "./tabs/Checkin";
import { Incidents } from "./tabs/Incidents";
import { Invigilators } from "./tabs/Invigilators";
import { Live } from "./tabs/Live";
import { Reentry } from "./tabs/Reentry";

const MONITORED = new Set(["READY", "RUNNING", "CLOSED", "FINALIZED"]);

export function ExamDetail() {
  const { examId = "" } = useParams();
  const q = useLoad(() => api.get<Exam>(org(`/exams/${examId}`)), [examId], 15000);
  const now = useTick(15000);
  const [publishError, setPublishError] = useState<unknown>(null);
  if (q.loading && !q.data) return <Loading />;
  if (q.error && !q.data) return <ErrorNotice error={q.error} onRetry={q.reload} />;
  const exam = q.data!;
  const monitored = MONITORED.has(exam.status);
  const tab = (to: string, label: Key) => (
    <NavLink to={to} end={to === ""}>{t(label)}</NavLink>
  );
  return (
    <>
      <div className="page-head">
        <div>
          <p className="small muted row" style={{ gap: "0.75rem" }}>
            <span className="num">{exam.code}</span>
            <span className="tag">{tx("vis", exam.visibility)}</span>
          </p>
          <h1>{exam.name}</h1>
          <p className="sub row" style={{ gap: "0.5rem 1rem" }}>
            <ExamStatus status={exam.status} />
            <span className="num">{dateTime(exam.window_start)} – {dateTime(exam.window_end)} {zoneLabel()}</span>
            {exam.extension_minutes > 0 && <span className="tag">+{exam.extension_minutes} menit</span>}
          </p>
        </div>
        <ExamActions exam={exam} reload={q.reload} onPublishError={setPublishError} />
      </div>
      {monitored && <Ruler start={exam.window_start} latest={exam.latest_start} end={exam.window_end} now={now} />}
      <nav className="tabs" aria-label="Bagian ujian">
        {monitored && tab("", "detail.tab.live")}
        {monitored && exam.identity_check === "MANUAL" && tab("checkin", "detail.tab.checkin")}
        {monitored && tab("incidents", "detail.tab.incidents")}
        {monitored && tab("reentry", "detail.tab.reentry")}
        {tab("candidates", "detail.tab.candidates")}
        {tab("invigilators", "detail.tab.invigilators")}
        {tab("settings", "detail.tab.settings")}
      </nav>
      <Routes>
        <Route index element={monitored ? <Live exam={exam} /> : <Navigate to="settings" replace />} />
        <Route path="checkin" element={<Checkin exam={exam} />} />
        <Route path="incidents" element={<Incidents exam={exam} />} />
        <Route path="reentry" element={<Reentry exam={exam} />} />
        <Route path="candidates" element={<Candidates exam={exam} />} />
        <Route path="invigilators" element={<Invigilators exam={exam} />} />
        <Route path="settings" element={<Overview exam={exam} publishError={publishError} />} />
      </Routes>
    </>
  );
}

// ------------------------------------------------------------------ exam-level actions
type Dlg = null | "cancel" | "extend" | "finalize" | "codes";

function ExamActions({ exam, reload, onPublishError }: {
  exam: Exam; reload: () => Promise<void>; onPublishError: (e: unknown) => void;
}) {
  const { isExamAdmin } = useSession();
  const nav = useNavigate();
  const toast = useToast();
  const [dlg, setDlg] = useState<Dlg>(null);
  const [reason, setReason] = useState("");
  const [minutes, setMinutes] = useState(10);
  const [count, setCount] = useState(20);
  const [codes, setCodes] = useState<string[] | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (!isExamAdmin) return null;

  const run = async (fn: () => Promise<unknown>, done?: string, close = true) => {
    setBusy(true);
    setError(null);
    try {
      const r = await fn();
      if (done) toast(done);
      if (close) setDlg(null);
      setReason("");
      await reload();
      return r;
    } catch (e) {
      if (dlg) setError(e);
      else toast(errorText(e), "error");
      return null;
    } finally {
      setBusy(false);
    }
  };
  const open = (d: Dlg) => { setError(null); setReason(""); setCodes(null); setDlg(d); };
  const reasonOk = reason.trim().length >= 3;
  const s = exam.status;

  return (
    <div className="toolbar no-print">
      {s === "DRAFT" && <Link className="btn" to={`/exams/${exam.id}/edit`}>{t("detail.edit")}</Link>}
      {s === "DRAFT" && (
        <button className="btn btn-primary" disabled={busy} onClick={async () => {
          setBusy(true);
          try {
            await api.post(org(`/exams/${exam.id}/publish`));
            onPublishError(null);
            toast(t("detail.published"));
            await reload();
          } catch (e) {
            onPublishError(e);
            nav(`/exams/${exam.id}/settings`);
          } finally {
            setBusy(false);
          }
        }}>
          {t("detail.publish")}
        </button>
      )}
      {s === "READY" && (
        <button className="btn" disabled={busy}
                onClick={() => void run(() => api.post(org(`/exams/${exam.id}/unpublish`)), t("detail.unpublished"))}>
          {t("detail.unpublish")}
        </button>
      )}
      {(s === "READY" || s === "RUNNING") && <button className="btn" onClick={() => open("codes")}>{t("detail.backupCodes")}</button>}
      {(s === "READY" || s === "RUNNING" || s === "CLOSED") && <button className="btn" onClick={() => open("extend")}>{t("detail.extend")}</button>}
      {s === "CLOSED" && <button className="btn btn-primary" onClick={() => open("finalize")}>{t("detail.finalize")}</button>}
      {(s === "DRAFT" || s === "READY") && <button className="btn btn-danger" onClick={() => open("cancel")}>{t("detail.cancelExam")}</button>}

      <Modal title={t("detail.cancelExam")} open={dlg === "cancel"} onClose={() => setDlg(null)}
             footer={<>
               <button className="btn" onClick={() => setDlg(null)}>{t("common.close")}</button>
               <button className="btn btn-danger solid" disabled={!reasonOk || busy}
                       onClick={() => void run(() => api.post(org(`/exams/${exam.id}/cancel`), { reason }), t("detail.cancelled"))}>
                 {t("detail.cancelExam")}
               </button>
             </>}>
        <p>{t("detail.cancelText")}</p>
        <ReasonField value={reason} onChange={setReason} />
        <ErrorNotice error={error} />
      </Modal>

      <Modal title={t("detail.extend")} open={dlg === "extend"} onClose={() => setDlg(null)}
             footer={<>
               <button className="btn" onClick={() => setDlg(null)}>{t("common.cancel")}</button>
               <button className="btn btn-primary" disabled={!reasonOk || busy || minutes < 1}
                       onClick={() => void run(async () => {
                         const r = await api.post<{ attempts_updated: number }>(org(`/exams/${exam.id}/extend`), { minutes, reason });
                         toast(t("detail.extended", { n: minutes, count: r.attempts_updated }));
                       })}>
                 {t("detail.extend")}
               </button>
             </>}>
        <p>{t("detail.extendText")}</p>
        <Field label={t("dlg.minutes")}>
          <input type="number" min={1} max={600} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
        </Field>
        <ReasonField value={reason} onChange={setReason} />
        <ErrorNotice error={error} />
      </Modal>

      <Modal title={t("detail.finalize")} open={dlg === "finalize"} onClose={() => setDlg(null)}
             footer={<>
               <button className="btn" onClick={() => setDlg(null)}>{t("common.cancel")}</button>
               <button className="btn btn-primary" disabled={busy}
                       onClick={() => void run(() => api.post(org(`/exams/${exam.id}/finalize`), { reason: reason || null }), t("detail.finalized"))}>
                 {t("detail.finalize")}
               </button>
             </>}>
        <p>{t("detail.finalizeText")}</p>
        <Field label={t("common.reason")}>
          <input value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
        <ErrorNotice error={error} />
      </Modal>

      <Modal title={t("codes.title")} open={dlg === "codes"} onClose={() => setDlg(null)}
             footer={codes ? <>
               <button className="btn" onClick={() => window.print()}>{t("codes.print")}</button>
               <button className="btn btn-primary" onClick={() => setDlg(null)}>{t("common.close")}</button>
             </> : <>
               <button className="btn" onClick={() => setDlg(null)}>{t("common.cancel")}</button>
               <button className="btn btn-primary" disabled={busy}
                       onClick={() => void run(async () => {
                         const r = await api.post<{ codes: string[] }>(org(`/exams/${exam.id}/backup-codes`), { count });
                         setCodes(r.codes);
                       }, undefined, false)}>
                 {t("codes.generate")}
               </button>
             </>}>
        {codes ? (
          <>
            <div className="notice warn">{t("codes.once")}</div>
            <p className="small"><b>{exam.code}</b> {exam.name}</p>
            <div className="codes">{codes.map((c) => <span key={c}>{c}</span>)}</div>
          </>
        ) : (
          <>
            <p>{t("codes.text")}</p>
            <Field label={t("codes.count")}>
              <input type="number" min={1} max={500} value={count} onChange={(e) => setCount(Number(e.target.value))} />
            </Field>
          </>
        )}
        <ErrorNotice error={error} />
      </Modal>
    </div>
  );
}

export function ReasonField({ value, onChange, label }: { value: string; onChange: (v: string) => void; label?: string }) {
  return (
    <Field label={label ?? t("common.reason")} hint={t("common.reasonHint")}>
      <textarea required minLength={3} maxLength={500} value={value} onChange={(e) => onChange(e.target.value)} />
    </Field>
  );
}

// ------------------------------------------------------------------ "Rincian" tab
function Overview({ exam, publishError }: { exam: Exam; publishError: unknown }) {
  const policyOn = Object.entries(exam.policy).filter(([k, v]) => v === true && k !== "fullscreen").map(([k]) => k);
  const problems = publishError instanceof ApiError && publishError.code === "EXAM_NOT_PUBLISHABLE" && exam.status === "DRAFT"
    ? (publishError.details as { field: string; problem: string }[]) : null;
  return (
    <div className="stack">
      {exam.status === "DRAFT" && <div className="notice warn">{t("detail.draftHint")}</div>}
      {exam.status === "READY" && <div className="notice">{t("detail.readyHint")}</div>}
      {problems && (
        <div className="notice error" role="alert">
          {t("detail.notPublishable")}
          <ul>{problems.map((p, i) => <li key={i}><b>{p.field}</b>: {p.problem}</li>)}</ul>
        </div>
      )}
      {!!publishError && !problems && exam.status === "DRAFT" && <ErrorNotice error={publishError} />}
      <section className="panel panel-pad stack">
        <h3>{t("detail.facts")}</h3>
        <dl className="facts">
          <dt>{t("form.examUrl")}</dt><dd>{exam.exam_url ?? "—"}</dd>
          <dt>{t("form.allowedOrigins")}</dt><dd>{exam.allowed_origins.join(", ") || "—"}</dd>
          <dt>{t("form.integration")}</dt><dd>{exam.integration_level === 2 ? t("form.integration2") : t("form.integration0")}</dd>
          <dt>{t("form.checkinOpen")}</dt><dd className="num">{dateTime(exam.checkin_open)}</dd>
          <dt>{t("form.windowStart")}</dt><dd className="num">{dateTime(exam.window_start)}</dd>
          <dt>{t("form.latestStart")}</dt><dd className="num">{dateTime(exam.latest_start)}</dd>
          <dt>{t("form.windowEnd")}</dt><dd className="num">{dateTime(exam.window_end)}</dd>
          <dt>{t("form.duration")}</dt><dd>{exam.duration_minutes ? t("common.minutes", { n: exam.duration_minutes }) : "—"}</dd>
          <dt>{t("form.lateStart")}</dt><dd>{t(`form.${exam.late_start_policy}` as Key)}</dd>
          <dt>{t("form.identity")}</dt><dd>{t(`form.identity.${exam.identity_check}` as Key)}</dd>
          {exam.visibility === "PUBLIC" && <>
            <dt>{t("form.registrationOpen")}</dt><dd className="num">{dateTime(exam.registration_open)}</dd>
            <dt>{t("form.registrationClose")}</dt><dd className="num">{dateTime(exam.registration_close)}</dd>
            <dt>{t("form.capacity")}</dt><dd>{exam.capacity ?? "—"}</dd>
          </>}
          <dt>{t("form.minLevel")}</dt><dd>{String(exam.policy.min_lockdown_level ?? "—")}</dd>
          <dt>{t("form.policy")}</dt>
          <dd>{policyOn.map((k) => t(`policy.${k}` as Key)).join(", ") || "—"}</dd>
        </dl>
      </section>
    </div>
  );
}
