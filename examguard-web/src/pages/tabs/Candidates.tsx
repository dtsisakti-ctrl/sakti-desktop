import { useState } from "react";
import { api, org } from "../../api/client";
import type { Enrollment, Exam, Invitation } from "../../api/types";
import { useSession } from "../../auth/session";
import { Empty, ErrorNotice, Field, Loading, Modal, errorText, useToast } from "../../components/ui";
import { t, tx } from "../../i18n";
import { useLoad } from "../../lib/hooks";
import { dateTime } from "../../lib/time";

export function Candidates({ exam }: { exam: Exam }) {
  const { isExamAdmin } = useSession();
  const toast = useToast();
  const q = useLoad(() => api.get<Enrollment[]>(org(`/exams/${exam.id}/enrollments`)), [exam.id]);
  const inv = useLoad(() => (isExamAdmin ? api.get<Invitation[]>(org(`/exams/${exam.id}/invitations`)) : Promise.resolve([])),
    [exam.id, isExamAdmin]);
  const [emails, setEmails] = useState("");
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState<{ e: Enrollment; mode: "acc" | "cancel" } | null>(null);
  const canInvite = isExamAdmin && (exam.status === "DRAFT" || exam.status === "READY");

  async function invite() {
    const list = emails.split(/[\s,;]+/).map((x) => x.trim()).filter(Boolean);
    if (!list.length) return;
    setBusy(true);
    try {
      const r = await api.post<{ created: unknown[]; skipped: unknown[] }>(org(`/exams/${exam.id}/invitations`), { emails: list });
      toast(t("enr.invited", { n: r.created.length, skipped: r.skipped.length }));
      setEmails("");
      await inv.reload();
    } catch (e) {
      toast(errorText(e), "error");
    } finally {
      setBusy(false);
    }
  }
  async function revoke(id: string) {
    try {
      await api.post(org(`/invitations/${id}/revoke`));
      await inv.reload();
    } catch (e) {
      toast(errorText(e), "error");
    }
  }

  return (
    <div className="stack">
      {canInvite && (
        <section className="panel panel-pad stack" style={{ gap: "0.6rem" }}>
          <h3>{t("enr.invite")}</h3>
          <Field label={t("login.email")} hint={t("enr.inviteHint")}>
            <textarea value={emails} onChange={(e) => setEmails(e.target.value)} placeholder="nama@kampus.ac.id" />
          </Field>
          <div><button className="btn btn-primary" disabled={busy || !emails.trim()} onClick={() => void invite()}>{t("enr.invite")}</button></div>
        </section>
      )}
      {q.loading && !q.data && <Loading />}
      <ErrorNotice error={q.error} onRetry={q.reload} />
      {q.data && q.data.length === 0 && <div className="panel"><Empty title={t("enr.empty")} hint={t("enr.emptyHint")} /></div>}
      {q.data && q.data.length > 0 && (
        <div className="table-wrap">
          <table className="register">
            <thead>
              <tr>
                <th className="seat">{t("live.col.no")}</th>
                <th>{t("enr.col.candidate")}</th>
                <th>{t("enr.col.source")}</th>
                <th>{t("enr.col.status")}</th>
                <th>{t("enr.col.accommodation")}</th>
                <th>{t("enr.col.registered")}</th>
                {isExamAdmin && <th />}
              </tr>
            </thead>
            <tbody>
              {q.data.map((e, i) => (
                <tr key={e.id}>
                  <td className="seat">{i + 1}</td>
                  <td><div className="name">{e.candidate_name}</div><div className="email">{e.candidate_email}</div></td>
                  <td>{tx("enr.src", e.source)}</td>
                  <td>{tx("enr", e.status)}{e.cancel_reason && <div className="small muted">{e.cancel_reason}</div>}</td>
                  <td className="num">{e.time_accommodation_minutes ? t("common.minutes", { n: e.time_accommodation_minutes }) : "—"}</td>
                  <td className="num">{dateTime(e.created_at)}</td>
                  {isExamAdmin && (
                    <td>
                      {e.status === "CONFIRMED" && (
                        <span className="row" style={{ gap: "0.4rem", flexWrap: "nowrap" }}>
                          <button className="btn btn-sm" onClick={() => setEdit({ e, mode: "acc" })}>{t("enr.setAccommodation")}</button>
                          <button className="btn btn-sm btn-danger" onClick={() => setEdit({ e, mode: "cancel" })}>{t("enr.cancel")}</button>
                        </span>
                      )}
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {isExamAdmin && inv.data && inv.data.length > 0 && (
        <section className="stack" style={{ gap: "0.5rem" }}>
          <h3>{t("enr.invitations")}</h3>
          <div className="table-wrap">
            <table className="register">
              <tbody>
                {inv.data.map((x) => (
                  <tr key={x.id}>
                    <td>{x.email}</td>
                    <td>{tx("inv", x.status)}</td>
                    <td className="num small muted">{dateTime(x.expires_at)}</td>
                    <td>{x.status === "PENDING" && <button className="btn btn-sm" onClick={() => void revoke(x.id)}>{t("enr.revoke")}</button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
      {edit && <EnrollmentDialog edit={edit} onClose={() => setEdit(null)} onDone={q.reload} />}
    </div>
  );
}

function EnrollmentDialog({ edit, onClose, onDone }: {
  edit: { e: Enrollment; mode: "acc" | "cancel" }; onClose: () => void; onDone: () => Promise<void>;
}) {
  const toast = useToast();
  const [minutes, setMinutes] = useState(edit.e.time_accommodation_minutes);
  const [reason, setReason] = useState("");
  const [error, setError] = useState<unknown>(null);
  const acc = edit.mode === "acc";
  async function save() {
    try {
      if (acc) await api.patch(org(`/enrollments/${edit.e.id}`), { time_accommodation_minutes: minutes });
      else await api.post(org(`/enrollments/${edit.e.id}/cancel`), { reason });
      toast(t("form.saved"));
      await onDone();
      onClose();
    } catch (e) {
      setError(e);
    }
  }
  return (
    <Modal title={acc ? t("enr.setAccommodation") : t("enr.cancel")} open onClose={onClose}
           footer={<>
             <button className="btn" onClick={onClose}>{t("common.cancel")}</button>
             <button className={`btn ${acc ? "btn-primary" : "btn-danger solid"}`} disabled={!acc && reason.trim().length < 3}
                     onClick={() => void save()}>{acc ? t("common.save") : t("enr.cancel")}</button>
           </>}>
      <p><b>{edit.e.candidate_name}</b></p>
      {acc ? (
        <Field label={t("dlg.minutes")} hint={t("enr.accommodationHint")}>
          <input type="number" min={0} max={600} value={minutes} onChange={(e) => setMinutes(Number(e.target.value))} />
        </Field>
      ) : (
        <Field label={t("common.reason")} hint={t("common.reasonHint")}>
          <textarea value={reason} onChange={(e) => setReason(e.target.value)} />
        </Field>
      )}
      <ErrorNotice error={error} />
    </Modal>
  );
}
