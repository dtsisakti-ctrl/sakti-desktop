import { useEffect, useState } from "react";
import { api, ApiError, org } from "../api/client";
import type { AttemptRow } from "../api/types";
import { t, tx, type Key } from "../i18n";
import { dateTime, fromLocalInput, toLocalInput } from "../lib/time";
import { AttemptStatus, ErrorNotice, Field, Modal, useToast } from "./ui";

export type Action =
  | "warning" | "pause" | "resume" | "add_time" | "force_submit" | "terminate" | "allow_reentry"
  | "reject_reentry" | "reopen" | "reinstate" | "identity_approve" | "identity_reject"
  | "emergency_unlock" | "unlock_response";

const PATH: Record<Action, string> = {
  warning: "warning", pause: "pause", resume: "resume", add_time: "add-time", force_submit: "force-submit",
  terminate: "terminate", allow_reentry: "reentry/allow", reject_reentry: "reentry/reject", reopen: "reopen",
  reinstate: "reinstate", identity_approve: "identity/approve", identity_reject: "identity/reject",
  emergency_unlock: "emergency-unlock", unlock_response: "unlock-response",
};
/** actions whose request body accepts expected_state_version (optimistic check, §10.3) */
const VERSIONED = new Set<Action>(["pause", "resume", "add_time", "force_submit", "terminate", "allow_reentry",
  "reject_reentry", "reopen", "reinstate"]);
const DANGER = new Set<Action>(["terminate", "reject_reentry", "force_submit", "emergency_unlock"]);
const CATEGORIES = ["TECHNICAL", "ADMINISTRATIVE", "DISCIPLINARY"] as const;

export function ActionDialog({ action, attempt, onClose, onDone }: {
  action: Action | null;
  attempt: AttemptRow;
  onClose: () => void;
  onDone: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [timerMode, setTimerMode] = useState("KEEP_RUNNING");
  const [minutes, setMinutes] = useState(10);
  const [category, setCategory] = useState("");
  const [deadline, setDeadline] = useState("");
  const [challenge, setChallenge] = useState("");
  const [response, setResponse] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!action) return;
    setReason(""); setMessage(""); setTimerMode("KEEP_RUNNING"); setMinutes(10); setCategory("");
    setChallenge(""); setResponse(null); setError(null);
    setDeadline(toLocalInput(new Date(Date.now() + 30 * 60_000).toISOString()));
  }, [action]);

  if (!action) return null;
  const a = action;
  const needsReason = a !== "warning" && a !== "identity_approve";
  const needsCategory = a === "terminate" || a === "reject_reentry";
  const isoDeadline = fromLocalInput(deadline);
  const deadlineOk = !(a === "reopen" || a === "reinstate") || (!!isoDeadline && Date.parse(isoDeadline) > Date.now());
  const valid =
    (!needsReason || reason.trim().length >= 3) &&
    (!needsCategory || !!category) &&
    (a !== "warning" || message.trim().length > 0) &&
    (a !== "unlock_response" || /^[A-Za-z2-7]{8}$/.test(challenge)) &&
    (a !== "add_time" || minutes >= 1) &&
    deadlineOk;

  function body(): Record<string, unknown> {
    if (a === "warning") return { message: message.trim() };
    if (a === "identity_approve" || a === "identity_reject") return { reason: reason.trim() || null };
    if (a === "emergency_unlock") return { reason };
    if (a === "unlock_response") return { challenge: challenge.toUpperCase(), reason };
    const b: Record<string, unknown> = { reason };
    if (VERSIONED.has(a)) b.expected_state_version = attempt.state_version;
    if (a === "pause") b.timer_mode = timerMode;
    if (a === "add_time") b.minutes = minutes;
    if (needsCategory) b.reason_category = category;
    if (a === "reopen" || a === "reinstate") b.deadline = isoDeadline;
    return b;
  }

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const r = await api.post<{ response?: string; note?: string }>(org(`/attempts/${attempt.attempt_id}/${PATH[a]}`), body());
      if (a === "unlock_response") {
        setResponse(r.response ?? null);
        return;
      }
      toast(r.note === "DEADLINE_PASSED" ? t("status.EXPIRED") : t(`act.done.${a}` as Key));
      onDone();
      onClose();
    } catch (e) {
      if (e instanceof ApiError && e.code === "STATE_CONFLICT") {
        toast(t("act.conflict"), "error");
        onDone();
        onClose();
      } else {
        setError(e);
      }
    } finally {
      setBusy(false);
    }
  }

  const newDeadline = attempt.deadline ? new Date(Date.parse(attempt.deadline) + minutes * 60_000).toISOString() : null;
  const title = t(`act.${a}` as Key);

  return (
    <Modal title={title} open onClose={onClose}
           footer={response ? (
             <button className="btn btn-primary" onClick={onClose}>{t("common.close")}</button>
           ) : (<>
             <button className="btn" onClick={onClose}>{t("common.cancel")}</button>
             <button className={`btn ${DANGER.has(a) ? "btn-danger solid" : "btn-primary"}`} disabled={!valid || busy}
                     onClick={() => void submit()}>{title}</button>
           </>)}>
      <p className="row" style={{ gap: "0.5rem 1rem" }}>
        <b>{attempt.candidate_name}</b>
        <AttemptStatus status={attempt.status} />
      </p>

      {a === "warning" && (
        <Field label={t("dlg.message")}>
          <textarea required maxLength={1000} value={message} onChange={(e) => setMessage(e.target.value)} autoFocus />
        </Field>
      )}
      {a === "pause" && (
        <fieldset className="field" style={{ border: 0, padding: 0, margin: 0 }}>
          <span>{t("dlg.timerMode")}</span>
          {(["KEEP_RUNNING", "PAUSE_TIMER"] as const).map((m) => (
            <label key={m} className="check">
              <input type="radio" name="timer" checked={timerMode === m} onChange={() => setTimerMode(m)} />
              {t(`dlg.${m}` as Key)}
            </label>
          ))}
        </fieldset>
      )}
      {a === "add_time" && (
        <>
          <dl className="facts">
            <dt>{t("dlg.currentDeadline")}</dt><dd className="num">{dateTime(attempt.deadline)}</dd>
            <dt>{t("dlg.newDeadline")}</dt><dd className="num"><b>{dateTime(newDeadline)}</b></dd>
          </dl>
          <Field label={t("dlg.minutes")}>
            <input type="number" min={1} max={600} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
          </Field>
        </>
      )}
      {a === "force_submit" && <p>{t("dlg.forceSubmitText")}</p>}
      {a === "terminate" && <div className="notice error">{t("dlg.terminateText")}</div>}
      {a === "emergency_unlock" && <p>{t("dlg.unlockText")}</p>}
      {needsCategory && (
        <Field label={t("dlg.category")}>
          <select required value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="" disabled>—</option>
            {CATEGORIES.map((c) => <option key={c} value={c}>{t(`dlg.cat.${c}` as Key)}</option>)}
          </select>
        </Field>
      )}
      {(a === "reopen" || a === "reinstate") && (
        <>
          <dl className="facts">
            <dt>{t("dlg.previous")}</dt><dd>{tx("status", attempt.status)}</dd>
          </dl>
          <Field label={t("dlg.newDeadline")} hint={deadlineOk ? undefined : t("dlg.deadlineFuture")}>
            <input type="datetime-local" required value={deadline} onChange={(e) => setDeadline(e.target.value)} />
          </Field>
        </>
      )}
      {a === "unlock_response" && !response && (
        <Field label={t("dlg.challenge")} hint={t("dlg.challengeHint")}>
          <input required value={challenge} maxLength={8} autoFocus style={{ letterSpacing: "0.2em", fontWeight: 700 }}
                 onChange={(e) => setChallenge(e.target.value.toUpperCase().replace(/[^A-Z2-7]/g, ""))} />
        </Field>
      )}
      {response && (
        <div className="notice warn">
          {t("dlg.response")}
          <div className="num" style={{ fontSize: "2rem", fontWeight: 700, letterSpacing: "0.15em", marginTop: "0.25rem" }}>
            {response.slice(0, 4)} {response.slice(4)}
          </div>
        </div>
      )}
      {!response && a !== "warning" && (
        <Field label={a === "identity_reject" ? t("checkin.rejectReason") : t("common.reason")}
               hint={needsReason ? t("common.reasonHint") : undefined}>
          <textarea required={needsReason} minLength={needsReason ? 3 : 0} maxLength={500} value={reason}
                    onChange={(e) => setReason(e.target.value)} />
        </Field>
      )}
      <ErrorNotice error={error} />
    </Modal>
  );
}
