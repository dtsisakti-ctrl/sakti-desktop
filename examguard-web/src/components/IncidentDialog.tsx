import { useState } from "react";
import { api, org } from "../api/client";
import type { Incident } from "../api/types";
import { t, tx, type Key } from "../i18n";
import { useLoad } from "../lib/hooks";
import { eventDescription, eventLabel, incidentDuration, incidentFacts } from "../lib/incidents";
import { dateTime, timeSec } from "../lib/time";
import { ErrorNotice, Field, Loading, Modal, Severity, useToast } from "./ui";

interface IncidentDetail extends Incident {
  events: { event_id: string; seq: number; type: string; phase: string; started_at: string; ended_at: string | null; confidence: number | null }[];
}

const PHASE: Record<string, string> = { OPEN: "mulai", CLOSE: "selesai", INSTANT: "" };

/** Incident detail with its events, and the review form (§27.8). */
export function IncidentDialog({ id, onClose, onDone }: { id: string; onClose: () => void; onDone: () => void | Promise<void> }) {
  const toast = useToast();
  const q = useLoad(() => api.get<IncidentDetail>(org(`/incidents/${id}`)), [id]);
  const [status, setStatus] = useState("REVIEWED");
  const [note, setNote] = useState("");
  const [error, setError] = useState<unknown>(null);
  const d = q.data;
  async function save() {
    try {
      await api.post(org(`/incidents/${id}/review`), { status, note: note || null });
      toast(t("inc.reviewed"));
      await onDone();
      onClose();
    } catch (e) {
      setError(e);
    }
  }
  const desc = d ? eventDescription(d.type) : null;
  const lastSeen = d && typeof d.data?.last_seen_at === "string" ? d.data.last_seen_at : null;
  return (
    <Modal title={d ? eventLabel(d.type) : t("inc.review")} open onClose={onClose}
           footer={<>
             <button className="btn" onClick={onClose}>{t("common.close")}</button>
             <button className="btn btn-primary" disabled={!d} onClick={() => void save()}>{t("common.save")}</button>
           </>}>
      {!d && <Loading />}
      {d && (
        <>
          {desc && <p>{desc}</p>}
          <dl className="facts">
            <dt>{t("inc.col.time")}</dt>
            <dd className="num">{timeSec(d.started_at)}{d.ended_at && d.ended_at !== d.started_at ? `–${timeSec(d.ended_at)}` : ""}</dd>
            <dt>{t("inc.col.duration")}</dt><dd className="num">{incidentDuration(d, Date.now())}</dd>
            <dt>{t("inc.col.severity")}</dt><dd><Severity level={d.severity} /></dd>
            {incidentFacts(d).length > 0 && <><dt>{t("cand.details")}</dt><dd>{incidentFacts(d).join(", ")}</dd></>}
            {lastSeen && <><dt>{t("reentry.col.lastSeen")}</dt><dd className="num">{timeSec(lastSeen)}</dd></>}
            <dt>{t("inc.col.review")}</dt>
            <dd>{tx("inc", d.status)}{d.reviewed_at ? <span className="muted small"> {dateTime(d.reviewed_at)}</span> : null}</dd>
            {d.review_note && <><dt>{t("inc.note")}</dt><dd>{d.review_note}</dd></>}
            <dt>{t("inc.code")}</dt><dd className="small muted">{d.type}</dd>
          </dl>
          <p className="small muted">{t("inc.notVerdict")}</p>
          {d.events.length > 0 && (
            <>
              <h3>{t("inc.events")}</h3>
              <ul className="timeline">
                {d.events.map((e) => (
                  <li key={e.event_id}>
                    <time>{timeSec(e.started_at)}</time>
                    <span className="what">{eventLabel(e.type)} <span className="why">{PHASE[e.phase] ?? e.phase}{e.confidence !== null ? `, ${Math.round(e.confidence * 100)}%` : ""}</span></span>
                    <span className="small muted">#{e.seq}</span>
                  </li>
                ))}
              </ul>
            </>
          )}
          <Field label={t("inc.col.review")}>
            <select value={status} onChange={(e) => setStatus(e.target.value)}>
              {["REVIEWED", "DISMISSED", "ESCALATED"].map((s) => <option key={s} value={s}>{t(`inc.${s}` as Key)}</option>)}
            </select>
          </Field>
          <Field label={t("inc.note")}>
            <textarea maxLength={2000} value={note} onChange={(e) => setNote(e.target.value)} />
          </Field>
          <ErrorNotice error={error} />
        </>
      )}
    </Modal>
  );
}
