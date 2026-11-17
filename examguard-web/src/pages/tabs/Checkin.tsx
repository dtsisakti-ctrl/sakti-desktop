import { useEffect, useState } from "react";
import { api, org } from "../../api/client";
import type { AttemptRow, CheckinItem, Exam } from "../../api/types";
import { ActionDialog, type Action } from "../../components/ActionDialog";
import { Empty, ErrorNotice, Loading } from "../../components/ui";
import { t } from "../../i18n";
import { useLoad } from "../../lib/hooks";
import { timeSec } from "../../lib/time";

/** Photos need the Authorization header, so they are fetched as blobs and shown via object URLs. */
function Photo({ url, label }: { url: string; label: string }) {
  const [src, setSrc] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    let alive = true;
    let obj: string | null = null;
    api.blob(url).then((b) => {
      obj = URL.createObjectURL(b);
      if (alive) setSrc(obj);
    }, () => alive && setFailed(true));
    return () => {
      alive = false;
      if (obj) URL.revokeObjectURL(obj);
    };
  }, [url]);
  return (
    <figure>
      {src ? <img src={src} alt={label} /> : <div className="photos-ph" style={{ aspectRatio: "4 / 3", background: "var(--paper)", borderRadius: "var(--radius)" }} />}
      <figcaption>{failed ? "—" : label}</figcaption>
    </figure>
  );
}

export function Checkin({ exam }: { exam: Exam }) {
  const q = useLoad(() => api.get<CheckinItem[]>(org(`/exams/${exam.id}/checkin-queue`)), [exam.id], 4000);
  const [pending, setPending] = useState<{ item: CheckinItem; action: Action } | null>(null);
  if (q.loading && !q.data) return <Loading />;
  if (q.error && !q.data) return <ErrorNotice error={q.error} onRetry={q.reload} />;
  const items = q.data!;
  if (!items.length) {
    return <div className="panel"><Empty title={t("checkin.empty")} hint={t("checkin.emptyHint")} /></div>;
  }
  // ActionDialog only needs the row fields it displays and the attempt id.
  const asRow = (i: CheckinItem) => ({ attempt_id: i.attempt_id, candidate_name: i.candidate_name, status: "NOT_STARTED",
    state_version: 0, deadline: null } as unknown as AttemptRow);
  return (
    <div className="stack">
      {items.map((item) => (
        <section key={item.attempt_id} className="panel panel-pad stack" style={{ gap: "0.75rem" }}>
          <div className="row">
            <div>
              <h3>{item.candidate_name}</h3>
              <p className="small muted">{item.candidate_email}</p>
            </div>
            <span className="spacer" />
            <span className="small muted">{t("checkin.submission", { n: item.submission, left: item.retries_left })}</span>
          </div>
          <div className="photos">
            {item.photos.map((p) => (
              <Photo key={p.id} url={p.url} label={`${p.kind === "SELFIE" ? t("checkin.selfie") : t("checkin.idCard")}, ${timeSec(p.created_at)}`} />
            ))}
          </div>
          <div className="row">
            <button className="btn btn-primary" onClick={() => setPending({ item, action: "identity_approve" })}>{t("checkin.approve")}</button>
            <button className="btn btn-danger" onClick={() => setPending({ item, action: "identity_reject" })}>{t("checkin.reject")}</button>
          </div>
        </section>
      ))}
      {pending && (
        <ActionDialog action={pending.action} attempt={asRow(pending.item)} onClose={() => setPending(null)} onDone={() => void q.reload()} />
      )}
    </div>
  );
}
