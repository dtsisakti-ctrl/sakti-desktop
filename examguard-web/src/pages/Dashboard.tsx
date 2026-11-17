import { Link, useNavigate } from "react-router-dom";
import { api, org } from "../api/client";
import type { Dashboard as D } from "../api/types";
import { Empty, ErrorNotice, ExamStatus, Loading } from "../components/ui";
import { t } from "../i18n";
import { useLoad } from "../lib/hooks";
import { date, time, zoneLabel } from "../lib/time";

export function Dashboard() {
  const nav = useNavigate();
  const q = useLoad(() => api.get<D>(org("/dashboard")), [], 5000);
  if (q.loading && !q.data) return <Loading />;
  if (q.error && !q.data) return <ErrorNotice error={q.error} onRetry={q.reload} />;
  const d = q.data!;
  const tot = d.totals;
  return (
    <>
      <div className="page-head">
        <div>
          <h1>{t("dash.title")}</h1>
          <p className="sub">{t("dash.sub")}</p>
        </div>
      </div>
      <div className="dash-totals" aria-label="Ringkasan">
        <span><b>{tot.running_exams}</b>{t("dash.running")}</span>
        <span><b>{tot.online}</b>{t("dash.online")}</span>
        <span className={tot.interrupted ? "alert" : ""}><b>{tot.interrupted}</b>{t("dash.interrupted")}</span>
        <span className={tot.waiting ? "alert" : ""}><b>{tot.waiting}</b>{t("dash.waiting")}</span>
        <span className={tot.open_incidents ? "alert" : ""}><b>{tot.open_incidents}</b>{t("dash.incidents")}</span>
      </div>
      {d.exams.length === 0 ? (
        <div className="panel">
          <Empty title={t("dash.empty")} hint={t("dash.emptyHint")}>
            <Link className="btn btn-primary" to="/exams/new">{t("exams.new")}</Link>
          </Empty>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="register">
            <thead>
              <tr>
                <th>{t("dash.col.exam")}</th>
                <th>{t("dash.col.status")}</th>
                <th>{t("dash.col.schedule")} ({zoneLabel()})</th>
                <th>{t("dash.col.online")}</th>
                <th>{t("dash.col.attention")}</th>
              </tr>
            </thead>
            <tbody>
              {d.exams.map((e) => {
                const attention = e.interrupted + e.waiting + e.open_incidents;
                return (
                  <tr key={e.id} className={`clickable ${attention ? "attention" : ""}`}
                      onClick={() => nav(`/exams/${e.id}${e.status === "RUNNING" ? "" : "/settings"}`)}>
                    <td>
                      <Link to={`/exams/${e.id}`} className="name" onClick={(ev) => ev.stopPropagation()}>{e.name}</Link>
                      <div className="email">{e.code}</div>
                    </td>
                    <td>
                      <ExamStatus status={e.status} />
                      {e.starts_within_24h && <div className="small muted">{t("dash.startsSoon")}</div>}
                    </td>
                    <td className="num">{date(e.window_start)}, {time(e.window_start)}–{time(e.window_end)}</td>
                    <td className="num">{e.status === "READY" ? "—" : `${e.online} / ${e.enrolled}`}</td>
                    <td className="small">
                      {attention === 0 ? <span className="muted">{t("common.none")}</span> : (
                        <span className="row" style={{ gap: "0.35rem 0.9rem" }}>
                          {e.interrupted > 0 && <span>{e.interrupted} {t("dash.interrupted")}</span>}
                          {e.waiting > 0 && <span>{e.waiting} {t("dash.waiting")}</span>}
                          {e.open_incidents > 0 && <span className="incident-count">{e.open_incidents} {t("dash.incidents")}</span>}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );
}
