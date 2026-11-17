import { useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, org } from "../../api/client";
import type { AttemptRow, Exam, ExamAttempts } from "../../api/types";
import { useSession } from "../../auth/session";
import { AttemptStatus, Empty, ErrorNotice, Field, Loading, Modal, errorText, useToast } from "../../components/ui";
import { t, tx, type Key } from "../../i18n";
import { useLoad, useTick } from "../../lib/hooks";
import { clock, timeSec } from "../../lib/time";
import { AttemptPanel } from "../AttemptPanel";

export const POLL_MS = 2000; // PRD §25: status changes visible in the Admin Web within 3 s
const LIVE = new Set(["ACTIVE", "PAUSED", "INTERRUPTED", "WAITING_FOR_INVIGILATOR"]);
const ENDED = new Set(["SUBMITTED", "EXPIRED", "TERMINATED", "NO_SHOW", "FINALIZED"]);

/** Rows that need an invigilator now: highlighted in the register. */
export function needsAttention(r: AttemptRow): boolean {
  return r.status === "INTERRUPTED" || r.status === "WAITING_FOR_INVIGILATOR" || r.open_incidents > 0 ||
    r.identity_status === "PENDING" || (LIVE.has(r.status) && r.connection_status === "OFFLINE");
}

/** Remaining seconds now, ticking locally between polls; frozen while paused with PAUSE_TIMER. */
export function remainingNow(r: AttemptRow, fetchedAt: number, now: number): number | null {
  if (r.remaining_seconds === null || ENDED.has(r.status)) return null;
  if (r.status === "PAUSED" && r.pause_timer_mode === "PAUSE_TIMER") return r.remaining_seconds;
  return Math.max(0, r.remaining_seconds - (now - fetchedAt) / 1000);
}

type Filter = "ALL" | "ATTENTION" | "ACTIVE" | "PAUSED" | "INTERRUPTED" | "WAITING_FOR_INVIGILATOR" | "NOT_STARTED" | "ENDED" | "INCIDENTS";

const FILTERS: { key: Filter; label: Key | string; test: (r: AttemptRow) => boolean; attention?: boolean }[] = [
  { key: "ALL", label: "live.all", test: () => true },
  { key: "ATTENTION", label: "live.attention", test: needsAttention, attention: true },
  { key: "ACTIVE", label: "status.ACTIVE", test: (r) => r.status === "ACTIVE" },
  { key: "PAUSED", label: "status.PAUSED", test: (r) => r.status === "PAUSED" },
  { key: "INTERRUPTED", label: "status.INTERRUPTED", test: (r) => r.status === "INTERRUPTED" },
  { key: "WAITING_FOR_INVIGILATOR", label: "status.WAITING_FOR_INVIGILATOR", test: (r) => r.status === "WAITING_FOR_INVIGILATOR" },
  { key: "NOT_STARTED", label: "status.NOT_STARTED", test: (r) => r.status === "NOT_STARTED" || r.status === "REOPENED" || r.status === "REINSTATED" },
  { key: "ENDED", label: "live.ended", test: (r) => ENDED.has(r.status) },
  { key: "INCIDENTS", label: "live.incidents", test: (r) => r.open_incidents > 0 },
];

export function Live({ exam }: { exam: Exam }) {
  const q = useLoad(() => api.get<ExamAttempts>(org(`/exams/${exam.id}/attempts`)), [exam.id], POLL_MS);
  const now = useTick(1000);
  const [params, setParams] = useSearchParams();
  const [filter, setFilter] = useState<Filter>("ALL");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulk, setBulk] = useState<string | null>(null);
  const openId = params.get("attempt");

  const rows = q.data?.attempts ?? [];
  const seat = useMemo(() => new Map(rows.map((r, i) => [r.attempt_id, i + 1])), [rows]);
  const visible = useMemo(() => {
    const f = FILTERS.find((x) => x.key === filter)!;
    const s = search.trim().toLowerCase();
    return rows.filter((r) => f.test(r) && (!s || r.candidate_name.toLowerCase().includes(s) || r.candidate_email.toLowerCase().includes(s)));
  }, [rows, filter, search]);

  if (q.loading && !q.data) return <Loading />;
  if (q.error && !q.data) return <ErrorNotice error={q.error} onRetry={q.reload} />;

  const open = (id: string | null, focus?: "incidents") => {
    const p = new URLSearchParams(params);
    if (id) p.set("attempt", id);
    else p.delete("attempt");
    if (focus) p.set("focus", focus);
    else p.delete("focus");
    setParams(p, { replace: !id });
  };
  const toggle = (id: string) => setSelected((s) => {
    const n = new Set(s);
    if (n.has(id)) n.delete(id);
    else n.add(id);
    return n;
  });
  const allVisibleSelected = visible.length > 0 && visible.every((r) => selected.has(r.attempt_id));

  return (
    <>
      {q.error && <ErrorNotice error={q.error} />}
      <div className="chips" role="group" aria-label="Filter">
        {FILTERS.map((f) => {
          const n = rows.filter(f.test).length;
          if (n === 0 && f.key !== "ALL" && f.key !== filter) return null;
          return (
            <button key={f.key} className={`chip ${filter === f.key ? "on" : ""} ${f.attention && n > 0 ? "attention" : ""}`}
                    aria-pressed={filter === f.key} onClick={() => setFilter(f.key)}>
              <b>{n}</b>{t(f.label as Key)}
            </button>
          );
        })}
      </div>
      <div className="row" style={{ marginBottom: "0.75rem" }}>
        <input type="search" placeholder={t("live.search")} value={search} onChange={(e) => setSearch(e.target.value)}
               aria-label={t("live.search")} style={{ minWidth: "16rem" }} />
        <span className="spacer" />
        {selected.size > 0 && <BulkBar count={selected.size} onPick={setBulk} onClear={() => setSelected(new Set())} />}
        <span className="small muted" aria-live="off">{t("common.updated", { time: timeSec(q.data?.server_time) })}</span>
      </div>
      {rows.length === 0 ? (
        <div className="panel"><Empty title={t("live.empty")} /></div>
      ) : (
        <div className="table-wrap">
          <table className="register">
            <thead>
              <tr>
                <th style={{ width: "2rem" }}>
                  <input type="checkbox" aria-label="Pilih semua" checked={allVisibleSelected}
                         onChange={() => setSelected(allVisibleSelected ? new Set() : new Set(visible.map((r) => r.attempt_id)))} />
                </th>
                <th className="seat">{t("live.col.no")}</th>
                <th>{t("live.col.candidate")}</th>
                <th>{t("live.col.status")}</th>
                <th>{t("live.col.connection")}</th>
                <th>{t("live.col.remaining")}</th>
                <th>{t("live.col.incidents")}</th>
                <th>{t("live.col.device")}</th>
              </tr>
            </thead>
            <tbody>
              {visible.length === 0 && (
                <tr><td colSpan={8} className="muted" style={{ padding: "1.5rem" }}>{t("live.emptyFilter")}</td></tr>
              )}
              {visible.map((r) => {
                const rem = remainingNow(r, q.at, now);
                const frozen = r.status === "PAUSED" && r.pause_timer_mode === "PAUSE_TIMER";
                const cls = [
                  "clickable",
                  needsAttention(r) ? "attention" : "",
                  openId === r.attempt_id ? "selected" : "",
                ].join(" ");
                return (
                  <tr key={r.attempt_id} className={cls} onClick={() => open(r.attempt_id)}>
                    <td onClick={(e) => e.stopPropagation()}>
                      <input type="checkbox" aria-label={`Pilih ${r.candidate_name}`} checked={selected.has(r.attempt_id)}
                             onChange={() => toggle(r.attempt_id)} />
                    </td>
                    <td className="seat">{seat.get(r.attempt_id)}</td>
                    <td>
                      <button className="link-name"
                              onClick={(e) => { e.stopPropagation(); open(r.attempt_id); }}>{r.candidate_name}</button>
                      <div className="email">{r.candidate_email}</div>
                    </td>
                    <td>
                      <AttemptStatus status={r.status} />
                      {r.identity_status === "PENDING" && <div className="small">{tx("identity", "PENDING")}</div>}
                    </td>
                    <td>
                      {LIVE.has(r.status) ? (
                        <>
                          <span className={`conn ${r.connection_status}`}>{tx("conn", r.connection_status)}</span>
                          {r.connection_status === "OFFLINE" && r.last_seen_at && (
                            <div className="small muted">{t("live.lastSeen", { time: timeSec(r.last_seen_at) })}</div>
                          )}
                        </>
                      ) : <span className="muted">—</span>}
                    </td>
                    <td className="num">
                      {clock(rem)}
                      {frozen && <span className="tag" style={{ marginLeft: "0.4rem" }}>{t("live.frozen")}</span>}
                    </td>
                    <td>{r.open_incidents > 0 ? (
                      <button className="incident-count" title={t("live.incidentsTip")}
                              aria-label={t("live.incidentsTipFor", { n: r.open_incidents, name: r.candidate_name })}
                              onClick={(e) => { e.stopPropagation(); open(r.attempt_id, "incidents"); }}>{r.open_incidents}</button>
                    ) : <span className="muted">0</span>}</td>
                    <td className="small muted">{r.client_version ? `v${r.client_version}` : "—"}<HealthFlags health={r.health} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      {openId && (
        <AttemptPanel attemptId={openId} seat={seat.get(openId)} focus={params.get("focus") === "incidents" ? "incidents" : undefined}
                      onClose={() => open(null)} onChanged={q.reload} />
      )}
      {bulk && (
        <BulkDialog exam={exam} action={bulk} ids={[...selected]} onClose={() => setBulk(null)}
                    onDone={() => { setSelected(new Set()); void q.reload(); }} />
      )}
    </>
  );
}

/** Only problems are shown; a healthy device stays quiet. */
export function HealthFlags({ health }: { health: Record<string, unknown> }) {
  const bad = (["lockdown_ok", "camera_ok", "mic_ok"] as const).filter((k) => health[k] === false);
  if (!bad.length) return null;
  return <div className="small" style={{ color: "var(--st-alert)", fontWeight: 600 }}>{bad.map((k) => t(`health.${k}` as Key)).join(", ")} ✕</div>;
}

// ------------------------------------------------------------------ bulk actions (§27.10)
function BulkBar({ count, onPick, onClear }: { count: number; onPick: (a: string) => void; onClear: () => void }) {
  const { isExamAdmin } = useSession();
  const actions = ["WARNING", "PAUSE", "RESUME", "ADD_TIME", ...(isExamAdmin ? ["TERMINATE"] : [])];
  return (
    <div className="row" style={{ gap: "0.4rem" }} role="toolbar" aria-label={t("live.bulk")}>
      <b className="small">{t("live.selected", { n: count })}</b>
      {actions.map((a) => (
        <button key={a} className={`btn btn-sm ${a === "TERMINATE" ? "btn-danger" : ""}`} onClick={() => onPick(a)}>
          {t(`bulk.${a}` as Key)}
        </button>
      ))}
      <button className="btn btn-sm btn-ghost" onClick={onClear}>{t("common.cancel")}</button>
    </div>
  );
}

function BulkDialog({ exam, action, ids, onClose, onDone }: {
  exam: Exam; action: string; ids: string[]; onClose: () => void; onDone: () => void;
}) {
  const toast = useToast();
  const [reason, setReason] = useState("");
  const [message, setMessage] = useState("");
  const [minutes, setMinutes] = useState(10);
  const [timerMode, setTimerMode] = useState("KEEP_RUNNING");
  const [category, setCategory] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const valid = reason.trim().length >= 3 && (action !== "WARNING" || message.trim()) &&
    (action !== "TERMINATE" || (category && code === exam.code));

  async function submit() {
    setBusy(true);
    try {
      const r = await api.post<{ succeeded: number; failed: number }>(org(`/exams/${exam.id}/bulk`), {
        action, attempt_ids: ids, reason, message: message || null, minutes: action === "ADD_TIME" ? minutes : null,
        timer_mode: timerMode, reason_category: category || null, confirm_exam_code: action === "TERMINATE" ? code : null,
      });
      toast(t("bulk.result", { ok: r.succeeded, failed: r.failed }));
      onDone();
      onClose();
    } catch (e) {
      setError(e);
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={`${t(`bulk.${action}` as Key)}: ${t("live.selected", { n: ids.length })}`} open onClose={onClose}
           footer={<>
             <button className="btn" onClick={onClose}>{t("common.cancel")}</button>
             <button className={`btn ${action === "TERMINATE" ? "btn-danger solid" : "btn-primary"}`} disabled={!valid || busy}
                     onClick={() => void submit()}>{t(`bulk.${action}` as Key)}</button>
           </>}>
      {action === "WARNING" && (
        <Field label={t("dlg.message")}><textarea value={message} onChange={(e) => setMessage(e.target.value)} autoFocus /></Field>
      )}
      {action === "PAUSE" && (
        <Field label={t("dlg.timerMode")}>
          <select value={timerMode} onChange={(e) => setTimerMode(e.target.value)}>
            <option value="KEEP_RUNNING">{t("dlg.KEEP_RUNNING")}</option>
            <option value="PAUSE_TIMER">{t("dlg.PAUSE_TIMER")}</option>
          </select>
        </Field>
      )}
      {action === "ADD_TIME" && (
        <Field label={t("dlg.minutes")}>
          <input type="number" min={1} max={600} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
        </Field>
      )}
      {action === "TERMINATE" && (
        <>
          <div className="notice error">{t("dlg.terminateText")}</div>
          <Field label={t("dlg.category")}>
            <select value={category} onChange={(e) => setCategory(e.target.value)}>
              <option value="" disabled>—</option>
              {(["TECHNICAL", "ADMINISTRATIVE", "DISCIPLINARY"] as const).map((c) => <option key={c} value={c}>{t(`dlg.cat.${c}` as Key)}</option>)}
            </select>
          </Field>
          <Field label={t("bulk.confirmCode", { code: exam.code })}>
            <input value={code} onChange={(e) => setCode(e.target.value)} autoComplete="off" />
          </Field>
        </>
      )}
      <Field label={t("common.reason")} hint={t("common.reasonHint")}>
        <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
      </Field>
      <ErrorNotice error={error} />
    </Modal>
  );
}
