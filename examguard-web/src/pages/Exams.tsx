import { Link, useNavigate } from "react-router-dom";
import { api, org } from "../api/client";
import type { Exam } from "../api/types";
import { useSession } from "../auth/session";
import { Empty, ErrorNotice, ExamStatus, Loading } from "../components/ui";
import { t, tx } from "../i18n";
import { useLoad } from "../lib/hooks";
import { date, time, zoneLabel } from "../lib/time";

export function Exams() {
  const nav = useNavigate();
  const { isExamAdmin } = useSession();
  const q = useLoad(() => api.get<Exam[]>(org("/exams")), []);
  return (
    <>
      <div className="page-head">
        <h1>{t("exams.title")}</h1>
        {isExamAdmin && <Link className="btn btn-primary" to="/exams/new">{t("exams.new")}</Link>}
      </div>
      {q.loading && !q.data && <Loading />}
      <ErrorNotice error={q.error} onRetry={q.reload} />
      {q.data && q.data.length === 0 && (
        <div className="panel">
          <Empty title={t("exams.empty")} hint={isExamAdmin ? t("exams.emptyHint") : undefined}>
            {isExamAdmin && <Link className="btn btn-primary" to="/exams/new">{t("exams.new")}</Link>}
          </Empty>
        </div>
      )}
      {q.data && q.data.length > 0 && (
        <div className="table-wrap">
          <table className="register">
            <thead>
              <tr>
                <th>{t("exams.col.code")}</th>
                <th>{t("exams.col.name")}</th>
                <th>{t("exams.col.visibility")}</th>
                <th>{t("exams.col.window")} ({zoneLabel()})</th>
                <th>{t("exams.col.registered")}</th>
                <th>{t("exams.col.status")}</th>
              </tr>
            </thead>
            <tbody>
              {q.data.map((e) => (
                <tr key={e.id} className="clickable" onClick={() => nav(`/exams/${e.id}`)}>
                  <td className="num">{e.code}</td>
                  <td><Link className="name" to={`/exams/${e.id}`} onClick={(ev) => ev.stopPropagation()}>{e.name}</Link></td>
                  <td>{tx("vis", e.visibility)}</td>
                  <td className="num">{e.window_start ? `${date(e.window_start)}, ${time(e.window_start)}–${time(e.window_end)}` : "—"}</td>
                  <td className="num">{e.capacity ? `${e.registered_count} / ${e.capacity}` : e.registered_count}</td>
                  <td><ExamStatus status={e.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
