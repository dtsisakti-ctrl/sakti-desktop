import { useState } from "react";
import { api, org } from "../../api/client";
import type { Exam, Incident } from "../../api/types";
import { IncidentDialog } from "../../components/IncidentDialog";
import { Empty, ErrorNotice, Loading, Severity } from "../../components/ui";
import { t, tx } from "../../i18n";
import { useLoad, useTick } from "../../lib/hooks";
import { eventLabel, incidentDuration } from "../../lib/incidents";
import { timeSec } from "../../lib/time";

export function Incidents({ exam }: { exam: Exam }) {
  const [onlyOpen, setOnlyOpen] = useState(true);
  const q = useLoad(() => api.get<Incident[]>(org(`/exams/${exam.id}/incidents${onlyOpen ? "?status=OPEN" : ""}`)),
    [exam.id, onlyOpen], 5000);
  const [openId, setOpenId] = useState<string | null>(null);
  const now = useTick(1000);
  return (
    <div className="stack">
      <div className="chips" role="group" aria-label="Filter">
        <button className={`chip ${onlyOpen ? "on" : ""}`} aria-pressed={onlyOpen} onClick={() => setOnlyOpen(true)}>{t("inc.filter.open")}</button>
        <button className={`chip ${!onlyOpen ? "on" : ""}`} aria-pressed={!onlyOpen} onClick={() => setOnlyOpen(false)}>{t("inc.filter.all")}</button>
      </div>
      {q.loading && !q.data && <Loading />}
      <ErrorNotice error={q.error} onRetry={q.reload} />
      {q.data && q.data.length === 0 && <div className="panel"><Empty title={t("inc.empty")} hint={t("inc.emptyHint")} /></div>}
      {q.data && q.data.length > 0 && (
        <div className="table-wrap">
          <table className="register">
            <thead>
              <tr>
                <th>{t("inc.col.severity")}</th>
                <th>{t("inc.col.candidate")}</th>
                <th>{t("inc.col.what")}</th>
                <th>{t("inc.col.time")}</th>
                <th>{t("inc.col.duration")}</th>
                <th>{t("inc.col.review")}</th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((i) => (
                <tr key={i.id} className={`clickable ${i.status === "OPEN" && i.severity === "HIGH" ? "attention" : ""}`} onClick={() => setOpenId(i.id)}>
                  <td><Severity level={i.severity} /></td>
                  <td className="name">{i.candidate_name}</td>
                  <td>{eventLabel(i.type)}{i.event_count > 1 && <span className="muted small"> ({i.event_count})</span>}</td>
                  <td className="num">{timeSec(i.started_at)}</td>
                  <td className="num">{incidentDuration(i, now)}</td>
                  <td>{tx("inc", i.status)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {openId && <IncidentDialog id={openId} onClose={() => setOpenId(null)} onDone={q.reload} />}
    </div>
  );
}
