import { useEffect, useRef, useState } from "react";
import { api, org } from "../api/client";
import type { AttemptDetail } from "../api/types";
import { ActionDialog, type Action } from "../components/ActionDialog";
import { IncidentDialog } from "../components/IncidentDialog";
import { AttemptStatus, ErrorNotice, Loading, Severity } from "../components/ui";
import { t, tx, type Key } from "../i18n";
import { useLoad, useTick } from "../lib/hooks";
import { eventDescription, eventLabel, incidentDuration, incidentFacts } from "../lib/incidents";
import { clock, dateTime, gap, timeSec } from "../lib/time";
import { remainingNow } from "./tabs/Live";

const LIVE = new Set(["ACTIVE", "PAUSED", "INTERRUPTED", "WAITING_FOR_INVIGILATOR"]);
/** Order of buttons; primary actions first, ending actions last. */
const ORDER: Action[] = ["allow_reentry", "identity_approve", "resume", "warning", "pause", "add_time", "reopen",
  "reinstate", "identity_reject", "force_submit", "reject_reentry", "terminate"];
const PRIMARY = new Set<Action>(["allow_reentry", "identity_approve", "resume", "reopen", "reinstate"]);
const DANGER = new Set<Action>(["terminate", "reject_reentry", "force_submit", "identity_reject"]);

export function AttemptPanel({ attemptId, seat, focus, onClose, onChanged }: {
  attemptId: string; seat?: number; focus?: "incidents"; onClose: () => void; onChanged: () => void;
}) {
  const q = useLoad(() => api.get<AttemptDetail>(org(`/attempts/${attemptId}`)), [attemptId], 2000);
  const now = useTick(1000);
  const [action, setAction] = useState<Action | null>(null);
  const [incidentId, setIncidentId] = useState<string | null>(null);
  const incidentsRef = useRef<HTMLElement>(null);
  const loaded = !!q.data;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape" && !action && !incidentId) onClose(); };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [action, incidentId, onClose]);

  // opened from the incident count in the register: go straight to the list
  useEffect(() => {
    if (loaded && focus === "incidents") incidentsRef.current?.scrollIntoView({ block: "start" });
  }, [loaded, focus, attemptId]);

  const d = q.data;
  const actions = d ? ORDER.filter((a) => d.available_actions.includes(a)) : [];
  // emergency unlock needs the same right as warnings (invigilator control) and a live session
  const canUnlock = !!d && d.available_actions.includes("warning") && LIVE.has(d.status);

  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true" aria-label={d?.candidate_name ?? t("common.loading")}>
        <header className="drawer-head">
          <div className="row">
            <div>
              {seat && <p className="small muted">{t("live.col.no")} {seat}</p>}
              <h2>{d?.candidate_name ?? "…"}</h2>
              {d && <p className="small muted">{d.candidate_email}</p>}
            </div>
            <span className="spacer" />
            <button className="btn btn-sm" onClick={onClose}>{t("common.close")}</button>
          </div>
        </header>
        <div className="drawer-body">
          {!d && q.loading && <Loading />}
          <ErrorNotice error={q.error} onRetry={q.reload} />
          {d && (
            <>
              <dl className="facts">
                <dt>{t("cand.status")}</dt>
                <dd><AttemptStatus status={d.status} /></dd>
                <dt>{t("cand.connection")}</dt>
                <dd>
                  {LIVE.has(d.status) ? <span className={`conn ${d.connection_status}`}>{tx("conn", d.connection_status)}</span> : "—"}
                  {d.last_seen_at && d.connection_status === "OFFLINE" && LIVE.has(d.status) && (
                    <span className="muted small"> {t("live.lastSeen", { time: timeSec(d.last_seen_at) })}</span>
                  )}
                </dd>
                <dt>{t("cand.deadline")}</dt>
                <dd className="num">{dateTime(d.deadline)}</dd>
                <dt>{t("cand.remaining")}</dt>
                <dd className="num"><b>{clock(remainingNow(d, q.at, now))}</b></dd>
                <dt>{t("cand.started")}</dt>
                <dd className="num">{dateTime(d.started_at)}</dd>
                <dt>{t("cand.accommodation")}</dt>
                <dd>{d.time_accommodation_minutes ? t("common.minutes", { n: d.time_accommodation_minutes }) : "—"}</dd>
                <dt>{t("cand.identity")}</dt>
                <dd>{tx("identity", d.identity_status)}</dd>
                <dt>{t("cand.client")}</dt>
                <dd>{d.client_version ? `ExamGuard ${d.client_version}` : "—"}</dd>
                <dt>{t("cand.health")}</dt>
                <dd><Health health={d.health} /></dd>
                {d.termination_reason_category && <>
                  <dt>{t("dlg.category")}</dt><dd>{tx("dlg.cat", d.termination_reason_category)}</dd>
                </>}
              </dl>

              <section className="stack" style={{ gap: "0.4rem" }} ref={incidentsRef} aria-labelledby="inc-head">
                <div className="row" style={{ alignItems: "baseline" }}>
                  <h3 id="inc-head">{t("inc.section")}</h3>
                  {d.incidents.length > 0 && (
                    <span className="small muted">
                      {t("inc.sectionCount", { open: d.incidents.filter((i) => i.status === "OPEN").length, all: d.incidents.length })}
                    </span>
                  )}
                </div>
                {d.incidents.length === 0 ? <p className="small muted">{t("inc.noneForCandidate")}</p> : (
                  <>
                    <table className="mini">
                      <thead>
                        <tr>
                          <th>{t("inc.col.time")}</th>
                          <th>{t("inc.col.what")}</th>
                          <th>{t("inc.col.duration")}</th>
                          <th>{t("inc.col.review")}</th>
                        </tr>
                      </thead>
                      <tbody>
                        {d.incidents.map((i) => {
                          const facts = incidentFacts(i);
                          const desc = eventDescription(i.type);
                          return (
                            <tr key={i.id} className={`clickable ${i.status === "OPEN" ? "open" : ""}`} tabIndex={0}
                                onClick={() => setIncidentId(i.id)}
                                onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setIncidentId(i.id); } }}>
                              <td className="num">
                                {timeSec(i.started_at)}
                                {i.ended_at && i.ended_at !== i.started_at && <div className="small muted">{t("inc.until", { time: timeSec(i.ended_at) })}</div>}
                                <div className="mini-dur small">{incidentDuration(i, now)}</div>
                              </td>
                              <td>
                                <div className="inc-what"><b>{eventLabel(i.type)}</b> <Severity level={i.severity} /></div>
                                {desc && <div className="small muted">{desc}</div>}
                                {facts.length > 0 && <div className="small">{facts.join(", ")}</div>}
                                {i.review_note && <div className="small"><span className="muted">{t("inc.note")}:</span> {i.review_note}</div>}
                              </td>
                              <td className="num">{incidentDuration(i, now)}</td>
                              <td>{tx("inc", i.status)}</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                    <p className="small muted">{t("inc.openTip")}</p>
                  </>
                )}
              </section>

              <section className="stack" style={{ gap: "0.6rem" }}>
                <h3>{t("cand.actions")}</h3>
                {actions.length === 0 && !canUnlock && <p className="small muted">{t("cand.noActions")}</p>}
                <div className="row" style={{ gap: "0.5rem" }}>
                  {actions.map((a) => (
                    <button key={a} className={`btn ${PRIMARY.has(a) ? "btn-primary" : ""} ${DANGER.has(a) ? "btn-danger" : ""}`}
                            onClick={() => setAction(a)}>{t(`act.${a}` as Key)}</button>
                  ))}
                </div>
                {canUnlock && (
                  <div className="row" style={{ gap: "0.5rem" }}>
                    <button className="btn btn-sm" onClick={() => setAction("emergency_unlock")}>{t("act.emergency_unlock")}</button>
                    <button className="btn btn-sm" onClick={() => setAction("unlock_response")}>{t("act.unlock_response")}</button>
                  </div>
                )}
              </section>

              <section className="stack" style={{ gap: "0.4rem" }}>
                <h3>{t("cand.events")}</h3>
                {d.events.length === 0 ? <p className="small muted">{t("cand.noEvents")}</p> : (
                  <ul className="timeline">
                    {d.events.map((e) => (
                      <li key={e.event_id}>
                        <time>{timeSec(e.started_at)}</time>
                        <span className="what">
                          {eventLabel(e.type)}
                          <span className="why">
                            {e.ended_at ? ` ${gap(Math.round((Date.parse(e.ended_at) - Date.parse(e.started_at)) / 1000))}` : e.phase === "OPEN" ? ` ${t("inc.ongoing")}` : ""}
                            {e.confidence !== null ? `, ${Math.round(e.confidence * 100)}%` : ""}
                          </span>
                        </span>
                        <Severity level={e.severity} />
                      </li>
                    ))}
                  </ul>
                )}
              </section>

              <section className="stack" style={{ gap: "0.4rem" }}>
                <h3>{t("cand.history")}</h3>
                <ul className="timeline">
                  {[...d.transitions].reverse().map((tr) => (
                    <li key={tr.state_version}>
                      <time>{timeSec(tr.occurred_at)}</time>
                      <span className="what">
                        {tr.trigger === "UPDATE_DEADLINE"
                          ? `${t("dlg.newDeadline")} ${timeSec(tr.new_deadline)}`
                          : t("cand.transition", { from: tx("status", tr.from_status), to: tx("status", tr.to_status) })}
                        {tr.reason && <span className="why"> {tr.reason}</span>}
                        {typeof tr.data.gap_seconds === "number" && <span className="why"> ({gap(tr.data.gap_seconds as number)})</span>}
                      </span>
                      <span className="small muted">{tx("actor", tr.actor_kind)}</span>
                    </li>
                  ))}
                </ul>
              </section>

              {d.device_sessions.length > 0 && (
                <section className="stack" style={{ gap: "0.4rem" }}>
                  <h3>{t("cand.devices")}</h3>
                  <ul className="timeline">
                    {d.device_sessions.map((ds) => (
                      <li key={ds.id}>
                        <time>{timeSec(ds.created_at)}</time>
                        <span className="what">
                          {ds.client_version ? `v${ds.client_version}` : "—"}
                          <span className="why"> {String((ds.os_info as { os?: string }).os ?? "")} {ds.revoke_reason ?? ""}</span>
                        </span>
                        <span className="tag">{ds.status}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}

              {d.commands.length > 0 && (
                <section className="stack" style={{ gap: "0.4rem" }}>
                  <h3>{t("cand.commands")}</h3>
                  <ul className="timeline">
                    {d.commands.map((c) => (
                      <li key={c.id}>
                        <time>{timeSec(c.issued_at)}</time>
                        <span className="what">{c.type}</span>
                        <span className="tag">{c.delivery_status}</span>
                      </li>
                    ))}
                  </ul>
                </section>
              )}
            </>
          )}
        </div>
      </aside>
      {d && (
        <ActionDialog action={action} attempt={d} onClose={() => setAction(null)}
                      onDone={() => { void q.reload(); onChanged(); }} />
      )}
      {incidentId && (
        <IncidentDialog id={incidentId} onClose={() => setIncidentId(null)}
                        onDone={() => { void q.reload(); onChanged(); }} />
      )}
    </>
  );
}

function Health({ health }: { health: Record<string, unknown> }) {
  const keys = (["lockdown_ok", "camera_ok", "mic_ok"] as const).filter((k) => k in health);
  if (!keys.length && !("queue_depth" in health)) return <span className="muted small">{t("health.unknown")}</span>;
  return (
    <span className="row" style={{ gap: "0.25rem 0.9rem" }}>
      {keys.map((k) => (
        <span key={k} style={{ color: health[k] ? "var(--st-active)" : "var(--st-alert)", fontWeight: 600 }}>
          {t(`health.${k}` as Key)} {health[k] ? "OK" : "✕"}
        </span>
      ))}
      {"queue_depth" in health && <span className="muted">{t("health.queue_depth")} {String(health.queue_depth)}</span>}
    </span>
  );
}
