import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../../api/client";
import { Empty, ErrorNotice, Loading, Modal, useToast } from "../../components/ui";
import { t, tx, type Key } from "../../i18n";
import { id } from "../../i18n/id";
import { useLoad, useTick } from "../../lib/hooks";
import { dateTime, dayParts, longDate, time, until, zoneLabel } from "../../lib/time";
import { usePortal } from "../session";
import type { Enrollment, LaunchLink } from "../types";
import { PortalError } from "../ui";
import { ResendVerification } from "./VerifyEmail";

const FINAL = new Set(["SUBMITTED", "EXPIRED", "TERMINATED", "NO_SHOW", "FINALIZED"]);
const RUNNING = new Set(["ACTIVE", "PAUSED", "INTERRUPTED", "WAITING_FOR_INVIGILATOR", "REOPENED", "REINSTATED"]);

/** Past entries: ended attempts, cancelled enrollments, cancelled exams. */
export function isHistory(e: Enrollment): boolean {
  return e.status !== "CONFIRMED" || e.exam.status === "CANCELLED" || FINAL.has(e.attempt?.status ?? "");
}

/** One line telling the candidate where they stand right now (PRD §28.4). */
export function phaseText(e: Enrollment, nowMs: number): string {
  const st = e.attempt?.status ?? "";
  if (st === "WAITING_FOR_INVIGILATOR") return t("p.phase.WAITING");
  if (RUNNING.has(st)) return t("p.phase.RUNNING");
  if (e.can_launch) return t("p.phase.OPEN", { time: time(e.exam.latest_start) });
  if (e.launch_reason === "NOT_YET_OPEN" && e.exam.checkin_open) {
    return t("p.phase.NOT_YET_OPEN", { d: until(Date.parse(e.exam.checkin_open) - nowMs) });
  }
  if (e.launch_reason === "LATE_START_CLOSED") return t("p.phase.LATE_START_CLOSED");
  if (e.launch_reason === "EXAM_NOT_OPEN") return t("p.phase.EXAM_NOT_OPEN");
  return "";
}

export function historyText(e: Enrollment): string {
  if (e.status !== "CONFIRMED") {
    const key = `p.cancelled.${e.cancel_reason}` as Key;
    return key in id ? t(key) : t("p.result.CANCELLED");
  }
  if (e.exam.status === "CANCELLED") return t("p.result.EXAM_CANCELLED");
  return tx("p.result", e.attempt?.status);
}

export function MyExams() {
  const { me, pendingInvite } = usePortal();
  // the list changes slowly (check-in opening, an invigilator's action); the countdown ticks locally
  const q = useLoad(() => api.get<Enrollment[]>("/api/v1/candidate/enrollments"), [], 15000);
  const now = useTick(30000);
  const upcoming = (q.data ?? []).filter((e) => !isHistory(e))
    .sort((a, b) => Date.parse(a.exam.window_start ?? "") - Date.parse(b.exam.window_start ?? ""));
  const history = (q.data ?? []).filter(isHistory);

  return (
    <div className="portal-grid">
      <div className="stack" style={{ gap: "1.25rem" }}>
        <h1>{t("p.mine.title")}</h1>
        {me && !me.email_verified_at && (
          <div className="notice warn stack" style={{ gap: "0.5rem" }}>
            <span>{t("p.verify.banner")}</span>
            <ResendVerification initial={me.email} compact />
          </div>
        )}
        {pendingInvite && (
          <div className="notice row">
            <span>{t("p.inv.pending")}</span>
            <span className="spacer" />
            <Link className="btn btn-sm" to={`/invitations/accept?token=${encodeURIComponent(pendingInvite)}`}>{t("p.inv.open")}</Link>
          </div>
        )}
        {q.loading && !q.data && <Loading />}
        <ErrorNotice error={q.error} onRetry={q.reload} />
        {q.data && (
          <section className="stack" aria-labelledby="up-head">
            <h2 id="up-head" className="section-title">{t("p.mine.upcoming")}</h2>
            {upcoming.length === 0 ? (
              <div className="panel">
                <Empty title={t("p.mine.empty")} hint={t("p.mine.emptyHint")}>
                  <Link className="btn" to="/catalog">{t("p.mine.toCatalog")}</Link>
                </Empty>
              </div>
            ) : upcoming.map((e) => <ExamCard key={e.id} e={e} now={now} onChanged={q.reload} />)}
          </section>
        )}
        {q.data && (
          <section className="stack" aria-labelledby="hist-head">
            <h2 id="hist-head" className="section-title">{t("p.mine.history")}</h2>
            {history.length === 0 ? <p className="muted">{t("p.mine.noHistory")}</p> : (
              <ul className="history">
                {history.map((e) => (
                  <li key={e.id}>
                    <span className="num history-date">{e.exam.window_start ? dateTime(e.exam.window_start) : "—"}</span>
                    <span>
                      <strong>{e.exam.name}</strong>
                      <span className="muted small"> {e.exam.org_name}</span>
                    </span>
                    <span className="history-result">
                      {historyText(e)}
                      {e.attempt?.started_at && (
                        <span className="muted small"> {t("p.result.started", { time: time(e.attempt.started_at) })}
                          {e.attempt.ended_at ? `, ${t("p.result.ended", { time: time(e.attempt.ended_at) })}` : ""}</span>
                      )}
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
      <Preparation />
    </div>
  );
}

function ExamCard({ e, now, onChanged }: { e: Enrollment; now: number; onChanged: () => void }) {
  const toast = useToast();
  const [link, setLink] = useState<LaunchLink | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [cancelOpen, setCancelOpen] = useState(false);
  const x = e.exam;
  const day = x.window_start ? dayParts(x.window_start) : null;
  const running = RUNNING.has(e.attempt?.status ?? "");
  const phase = phaseText(e, now);

  async function start() {
    setBusy(true);
    setError(null);
    try {
      const l = await api.post<LaunchLink>(`/api/v1/candidate/enrollments/${e.id}/launch`);
      setLink(l);
      window.location.href = l.launch_url;      // the OS asks to open ExamGuard (PRD §12.2)
    } catch (err) {
      setError(err);
      onChanged();
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    try {
      await api.post(`/api/v1/candidate/enrollments/${e.id}/cancel`);
      toast(t("p.cancel.done"));
      setCancelOpen(false);
      onChanged();
    } catch (err) {
      setError(err);
      setCancelOpen(false);
    }
  }

  return (
    <article className={`ticket ${e.can_launch || running ? "ticket-open" : ""}`} aria-labelledby={`ex-${e.id}`}>
      <div className="ticket-date" aria-hidden={!day}>
        {day ? (<><span className="ticket-day num">{day.day}</span><span className="ticket-month">{day.month}</span></>) : "—"}
      </div>
      <div className="ticket-body">
        <div className="ticket-head">
          <span className="tag">{x.visibility === "PUBLIC" ? t("p.card.public") : t("p.card.private")}</span>
          <span className="muted small">{x.org_name}</span>
          <span className="muted small num">{x.code}</span>
        </div>
        <h3 id={`ex-${e.id}`}>{x.name}</h3>
        {x.window_start && (
          <p className="num">
            {longDate(x.window_start)}, {t("p.card.time", { start: time(x.window_start), end: time(x.window_end), zone: zoneLabel() })}
          </p>
        )}
        <ul className="ticket-facts">
          {x.checkin_open && <li>{t("p.card.checkin", { time: time(x.checkin_open) })}</li>}
          {x.latest_start && <li>{t("p.card.latest", { time: time(x.latest_start) })}</li>}
          {x.duration_minutes && <li>{t("p.card.duration", { n: x.duration_minutes })}</li>}
        </ul>
        {x.identity_check === "MANUAL" && <p className="small muted">{t("p.card.identity")}</p>}
        {phase && <p className={`ticket-phase ${e.can_launch || running ? "on" : ""}`} role="status">{phase}</p>}
        <PortalError error={error} />
      </div>
      <div className="ticket-actions">
        <button className="btn btn-primary btn-lg" disabled={!e.can_launch || busy} onClick={() => void start()}>
          {running ? t("p.card.reopen") : t("p.card.start")}
        </button>
        {e.can_change && (
          <div className="row" style={{ gap: "0.4rem" }}>
            {x.series && <Link className="btn btn-sm" to={`/catalog?series=${encodeURIComponent(x.series)}&move=${e.id}`}>{t("p.card.move")}</Link>}
            <button className="btn btn-sm btn-ghost" onClick={() => setCancelOpen(true)}>{t("p.card.cancel")}</button>
          </div>
        )}
      </div>
      {link && <LaunchDialog link={link} onClose={() => setLink(null)} />}
      <Modal title={t("p.cancel.title")} open={cancelOpen} onClose={() => setCancelOpen(false)}
             footer={<>
               <button className="btn" onClick={() => setCancelOpen(false)}>{t("common.cancel")}</button>
               <button className="btn btn-danger" onClick={() => void cancel()}>{t("p.cancel.confirm")}</button>
             </>}>
        <p><strong>{x.name}</strong></p>
        <p>{t("p.cancel.text")}</p>
      </Modal>
    </article>
  );
}

function LaunchDialog({ link, onClose }: { link: LaunchLink; onClose: () => void }) {
  const toast = useToast();
  async function copy() {
    try {
      await navigator.clipboard.writeText(link.launch_url);
      toast(t("p.launch.copied"));
    } catch {
      /* clipboard blocked: the link is selectable in the box */
    }
  }
  return (
    <Modal title={t("p.launch.title")} open onClose={onClose}
           footer={<>
             <button className="btn" onClick={onClose}>{t("common.close")}</button>
             <button className="btn btn-primary" onClick={() => { window.location.href = link.launch_url; }}>{t("p.launch.again")}</button>
           </>}>
      <p>{t("p.launch.text")}</p>
      <p className="small muted">{t("p.launch.notInstalled")}</p>
      <p className="small muted">{t("p.launch.expires", { time: time(link.expires_at) })}</p>
      <details className="dev-link">
        <summary>{t("p.launch.dev")}</summary>
        <p className="small muted">{t("p.launch.devText")}</p>
        <code className="launch-url" data-testid="launch-url">{link.launch_url}</code>
        <button className="btn btn-sm" onClick={() => void copy()}>{t("p.launch.copy")}</button>
      </details>
    </Modal>
  );
}

function Preparation() {
  return (
    <aside className="panel prep" aria-labelledby="prep-head">
      <h2 id="prep-head" className="section-title">{t("p.prep.title")}</h2>
      <ul className="checklist">
        <li>{t("p.prep.device")}</li>
        <li>{t("p.prep.network")}</li>
        <li>{t("p.prep.client")}</li>
      </ul>
      <button className="btn" disabled title={t("p.prep.downloadSoon")}>{t("p.prep.download")}</button>
      <p className="small muted">{t("p.prep.downloadSoon")}</p>
    </aside>
  );
}
