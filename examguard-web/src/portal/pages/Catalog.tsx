import { useMemo, useState, type FormEvent } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { Empty, ErrorNotice, Field, Loading, Modal, useToast } from "../../components/ui";
import { t, tx } from "../../i18n";
import { useLoad } from "../../lib/hooks";
import { dateTime, dayParts, longDate, time, zoneLabel } from "../../lib/time";
import { usePortal } from "../session";
import type { CatalogExam, Enrollment } from "../types";
import { PortalError } from "../ui";

/** Public sessions open for registration (PRD §28.1): filter by text, test series and start date. */
export function filterCatalog(rows: CatalogExam[], text: string, series: string, from: string): CatalogExam[] {
  const q = text.trim().toLowerCase();
  const fromMs = from ? Date.parse(`${from}T00:00:00`) : null;
  return rows.filter((x) =>
    (!q || [x.name, x.code, x.org_name, x.series ?? ""].some((v) => v.toLowerCase().includes(q))) &&
    (!series || x.series === series) &&
    (fromMs === null || (x.window_start !== null && Date.parse(x.window_start) >= fromMs)));
}

export function Catalog() {
  const [params, setParams] = useSearchParams();
  const moveFrom = params.get("move");
  const [text, setText] = useState("");
  const [series, setSeries] = useState(params.get("series") ?? "");
  const [from, setFrom] = useState("");
  const cat = useLoad(() => api.get<CatalogExam[]>("/api/v1/public/exams"), []);
  const mine = useLoad(() => api.get<Enrollment[]>("/api/v1/candidate/enrollments"), []);
  const [picked, setPicked] = useState<CatalogExam | null>(null);

  const allSeries = useMemo(() => [...new Set((cat.data ?? []).map((x) => x.series).filter(Boolean) as string[])].sort(), [cat.data]);
  const registered = new Set((mine.data ?? []).filter((e) => e.status === "CONFIRMED").map((e) => e.exam.id));
  const moving = (mine.data ?? []).find((e) => e.id === moveFrom && e.can_change) ?? null;
  const rows = filterCatalog(cat.data ?? [], text, series, from);

  return (
    <div className="stack" style={{ gap: "1.25rem" }}>
      <div className="stack" style={{ gap: "0.25rem" }}>
        <h1>{t("p.catalog.title")}</h1>
        <p className="muted">{t("p.catalog.lead")}</p>
      </div>
      {moving && (
        <div className="notice row">
          <span>{t("p.move.text", { from: moving.exam.name })}</span>
          <span className="spacer" />
          <button className="btn btn-sm" onClick={() => { params.delete("move"); setParams(params); }}>{t("common.cancel")}</button>
        </div>
      )}
      <div className="filters">
        <Field label={t("p.catalog.search")}>
          <input type="search" value={text} onChange={(e) => setText(e.target.value)} />
        </Field>
        <Field label={t("p.catalog.series")}>
          <select value={series} onChange={(e) => setSeries(e.target.value)}>
            <option value="">{t("p.catalog.allSeries")}</option>
            {allSeries.map((s) => <option key={s} value={s}>{s}</option>)}
          </select>
        </Field>
        <Field label={t("p.catalog.from")}>
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
        </Field>
      </div>
      {cat.loading && !cat.data && <Loading />}
      <ErrorNotice error={cat.error} onRetry={cat.reload} />
      {cat.data && rows.length === 0 && <div className="panel"><Empty title={t("p.catalog.empty")} hint={t("p.catalog.emptyHint")} /></div>}
      <div className="stack">
        {rows.map((x) => {
          const day = x.window_start ? dayParts(x.window_start) : null;
          const isMine = registered.has(x.id);
          const canMoveHere = !!moving && moving.exam.id !== x.id && moving.exam.series === x.series;
          return (
            <article key={x.id} className="ticket" aria-labelledby={`c-${x.id}`}>
              <div className="ticket-date">
                {day ? (<><span className="ticket-day num">{day.day}</span><span className="ticket-month">{day.month}</span></>) : "—"}
              </div>
              <div className="ticket-body">
                <div className="ticket-head">
                  {x.series && <span className="tag">{x.series}</span>}
                  <span className="muted small">{x.org_name}</span>
                  <span className="muted small num">{x.code}</span>
                </div>
                <h3 id={`c-${x.id}`}>{x.name}</h3>
                {x.window_start && (
                  <p className="num">{longDate(x.window_start)}, {t("p.card.time", { start: time(x.window_start), end: time(x.window_end), zone: zoneLabel() })}</p>
                )}
                {x.description && <p className="small">{x.description}</p>}
                <ul className="ticket-facts">
                  {x.duration_minutes && <li>{t("p.card.duration", { n: x.duration_minutes })}</li>}
                  <li>{x.seats_left === null ? t("p.catalog.unlimited") : t("p.catalog.seats", { n: x.seats_left })}</li>
                  {x.registration_status === "NOT_YET_OPEN" && x.registration_open
                    ? <li>{t("p.catalog.opens", { time: dateTime(x.registration_open) })}</li>
                    : x.registration_close && <li>{t("p.catalog.closes", { time: dateTime(x.registration_close) })}</li>}
                  {x.requires_access_code && <li>{t("p.catalog.code")}</li>}
                </ul>
                {x.identity_check === "MANUAL" && <p className="small muted">{t("p.card.identity")}</p>}
              </div>
              <div className="ticket-actions">
                <span className={`reg-status r-${x.registration_status}`}>{tx("p.status", x.registration_status)}</span>
                {isMine ? <span className="tag tag-ok">{t("p.catalog.registered")}</span> : canMoveHere ? (
                  <button className="btn btn-primary" disabled={x.registration_status !== "OPEN"} onClick={() => setPicked(x)}>{t("p.catalog.moveHere")}</button>
                ) : (
                  <button className="btn btn-primary" disabled={x.registration_status !== "OPEN"} onClick={() => setPicked(x)}>{t("p.catalog.register")}</button>
                )}
              </div>
            </article>
          );
        })}
      </div>
      {picked && (
        <RegisterDialog exam={picked} moving={moving && moving.exam.series === picked.series ? moving : null}
                        onClose={() => setPicked(null)} onDone={() => { void cat.reload(); void mine.reload(); }} />
      )}
    </div>
  );
}

function RegisterDialog({ exam, moving, onClose, onDone }: {
  exam: CatalogExam; moving: Enrollment | null; onClose: () => void; onDone: () => void;
}) {
  const { me } = usePortal();
  const toast = useToast();
  const nav = useNavigate();
  const [code, setCode] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e?: FormEvent) {
    e?.preventDefault();
    setBusy(true);
    setError(null);
    const body = { access_code: exam.requires_access_code ? code : null };
    try {
      if (moving) {
        await api.post(`/api/v1/candidate/enrollments/${moving.id}/move`, { target_exam_id: exam.id, ...body });
        toast(t("p.move.done"));
      } else {
        await api.post(`/api/v1/candidate/exams/${exam.id}/register`, body);
        toast(t("p.reg.done"));
      }
      onDone();
      nav("/");
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={moving ? t("p.move.title", { name: exam.name }) : t("p.reg.title", { name: exam.name })} open onClose={onClose}
           footer={<>
             <button className="btn" onClick={onClose}>{t("common.cancel")}</button>
             <button className="btn btn-primary" disabled={busy || (exam.requires_access_code && !code)}
                     onClick={() => void submit()}>{moving ? t("p.move.submit") : t("p.reg.submit")}</button>
           </>}>
      <p className="num">{longDate(exam.window_start)}, {time(exam.window_start)}–{time(exam.window_end)} {zoneLabel()}</p>
      {moving ? <p>{t("p.move.text", { from: moving.exam.name })}</p> : <p>{t("p.reg.text", { name: me?.full_name ?? "" })}</p>}
      {!me?.email_verified_at && <div className="notice warn">{t("p.verify.banner")}</div>}
      {exam.requires_access_code && (
        <form onSubmit={submit}>
          <Field label={t("p.reg.access")}>
            <input value={code} onChange={(e) => setCode(e.target.value)} autoFocus autoComplete="off" />
          </Field>
        </form>
      )}
      <PortalError error={error} />
    </Modal>
  );
}
