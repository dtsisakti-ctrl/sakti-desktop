import { useState } from "react";
import { api, org } from "../../api/client";
import type { AttemptRow, Exam, ReentryRow } from "../../api/types";
import { ActionDialog, type Action } from "../../components/ActionDialog";
import { AttemptStatus, Empty, ErrorNotice, Loading } from "../../components/ui";
import { t, tx } from "../../i18n";
import { useLoad } from "../../lib/hooks";
import { gap, timeSec } from "../../lib/time";

export function Reentry({ exam }: { exam: Exam }) {
  const q = useLoad(() => api.get<ReentryRow[]>(org(`/exams/${exam.id}/reentry`)), [exam.id], 3000);
  const [pending, setPending] = useState<{ row: ReentryRow; action: Action } | null>(null);
  if (q.loading && !q.data) return <Loading />;
  if (q.error && !q.data) return <ErrorNotice error={q.error} onRetry={q.reload} />;
  const rows = q.data!;
  if (!rows.length) return <div className="panel"><Empty title={t("reentry.empty")} /></div>;
  const latest = new Set<string>();  // rows are newest first; only the latest row of an attempt gets buttons
  const isLatest = (r: ReentryRow) => (latest.has(r.attempt_id) ? false : (latest.add(r.attempt_id), true));
  const asRow = (r: ReentryRow) => ({ attempt_id: r.attempt_id, candidate_name: r.candidate_name, status: r.current_status,
    state_version: r.state_version, deadline: null } as unknown as AttemptRow);
  return (
    <>
      <div className="table-wrap">
        <table className="register">
          <thead>
            <tr>
              <th>{t("reentry.col.candidate")}</th>
              <th>{t("reentry.col.lastSeen")}</th>
              <th>{t("reentry.col.gap")}</th>
              <th>{t("reentry.col.cause")}</th>
              <th>{t("reentry.col.outcome")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => {
              const waiting = isLatest(r) && r.current_status === "WAITING_FOR_INVIGILATOR" && r.outcome === "WAITING";
              return (
                <tr key={`${r.attempt_id}-${i}`} className={waiting ? "attention" : ""}>
                  <td className="name">{r.candidate_name}</td>
                  <td className="num">{timeSec(r.last_seen_at)}</td>
                  <td className="num">{gap(r.gap_seconds)}</td>
                  <td>{r.cause ?? "—"}{r.device_changed && <span className="tag" style={{ marginLeft: "0.4rem" }}>{t("reentry.deviceChanged")}</span>}</td>
                  <td>{waiting ? <AttemptStatus status={r.current_status} /> : tx("reentry", r.outcome)}</td>
                  <td>
                    {waiting && (
                      <span className="row" style={{ gap: "0.4rem", flexWrap: "nowrap" }}>
                        <button className="btn btn-sm btn-danger" onClick={() => setPending({ row: r, action: "reject_reentry" })}>{t("act.reject_reentry")}</button>
                        <button className="btn btn-sm btn-primary" onClick={() => setPending({ row: r, action: "allow_reentry" })}>{t("act.allow_reentry")}</button>
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {pending && <ActionDialog action={pending.action} attempt={asRow(pending.row)} onClose={() => setPending(null)} onDone={() => void q.reload()} />}
    </>
  );
}
