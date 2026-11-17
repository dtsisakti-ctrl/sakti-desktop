import { useState } from "react";
import { api, org } from "../../api/client";
import type { Exam, Invigilator } from "../../api/types";
import { useSession } from "../../auth/session";
import { Empty, ErrorNotice, Loading, errorText, useToast } from "../../components/ui";
import { t } from "../../i18n";
import { useLoad } from "../../lib/hooks";
import { dateTime } from "../../lib/time";

export function Invigilators({ exam }: { exam: Exam }) {
  const { isExamAdmin } = useSession();
  const toast = useToast();
  const q = useLoad(() => api.get<Invigilator[]>(org(`/exams/${exam.id}/invigilators`)), [exam.id]);
  const pool = useLoad(() => (isExamAdmin ? api.get<Invigilator[]>(org("/invigilators")) : Promise.resolve([])), [isExamAdmin]);
  const [pick, setPick] = useState("");
  const assigned = new Set((q.data ?? []).map((x) => x.user_id));
  const available = (pool.data ?? []).filter((x) => !assigned.has(x.user_id));
  const editable = isExamAdmin && exam.status !== "FINALIZED" && exam.status !== "CANCELLED";

  async function assign() {
    try {
      await api.post(org(`/exams/${exam.id}/invigilators`), { user_id: pick });
      setPick("");
      await q.reload();
    } catch (e) {
      toast(errorText(e), "error");
    }
  }
  async function remove(id: string) {
    try {
      await api.del(org(`/exams/${exam.id}/invigilators/${id}`));
      await q.reload();
    } catch (e) {
      toast(errorText(e), "error");
    }
  }

  return (
    <div className="stack">
      {editable && (
        <section className="panel panel-pad row">
          {pool.data && pool.data.length === 0 ? <p className="small muted">{t("invig.noneAvailable")}</p> : (
            <>
              <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label={t("invig.pick")}>
                <option value="">{t("invig.pick")}</option>
                {available.map((x) => <option key={x.user_id} value={x.user_id}>{x.full_name} ({x.email})</option>)}
              </select>
              <button className="btn btn-primary" disabled={!pick} onClick={() => void assign()}>{t("invig.assign")}</button>
            </>
          )}
        </section>
      )}
      {q.loading && !q.data && <Loading />}
      <ErrorNotice error={q.error} onRetry={q.reload} />
      {q.data && q.data.length === 0 && <div className="panel"><Empty title={t("invig.empty")} hint={t("invig.emptyHint")} /></div>}
      {q.data && q.data.length > 0 && (
        <div className="table-wrap">
          <table className="register">
            <tbody>
              {q.data.map((x) => (
                <tr key={x.user_id}>
                  <td><div className="name">{x.full_name}</div><div className="email">{x.email}</div></td>
                  <td className="num small muted">{dateTime(x.assigned_at)}</td>
                  <td>{editable && <button className="btn btn-sm" onClick={() => void remove(x.user_id)}>{t("invig.remove")}</button>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
