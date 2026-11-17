import { t } from "../i18n";
import { time } from "../lib/time";

/** The exam session as a ruler: window_start → latest_start (start allowed) → window_end, with "now". */
export function Ruler({ start, latest, end, now }: { start: string | null; latest: string | null; end: string | null; now: number }) {
  if (!start || !end) return null;
  const s = Date.parse(start);
  const e = Date.parse(end);
  const l = latest ? Date.parse(latest) : s;
  const span = Math.max(e - s, 1);
  const pct = (x: number) => `${Math.min(100, Math.max(0, ((x - s) / span) * 100))}%`;
  const inside = now >= s && now <= e;
  const nowFrac = (now - s) / span;
  const edge = nowFrac < 0.12 ? "edge-left" : nowFrac > 0.88 ? "edge-right" : "";
  return (
    <div className="ruler" aria-label="Jadwal ujian">
      <div className="ruler-track">
        <div className="ruler-start-window" style={{ left: 0, width: pct(l) }} title={t("ruler.latestStart", { time: time(latest) })} />
        {now > s && <div className="ruler-elapsed" style={{ width: pct(now) }} />}
      </div>
      <Mark className="start" left="0" label={t("ruler.windowStart", { time: "" })} at={time(start)} />
      {latest && l > s && l < e && <Mark className="" left={pct(l)} label={t("ruler.latestStart", { time: "" })} at={time(latest)} />}
      <Mark className="end" left="100%" label={t("ruler.windowEnd", { time: "" })} at={time(end)} />
      {inside && (
        <div className={`ruler-now ${edge}`} style={{ left: pct(now) }}>
          <span>{t("ruler.now", { time: time(new Date(now).toISOString()) })}</span>
        </div>
      )}
    </div>
  );
}

/** "Batas mulai 21.45"; on narrow screens only the time is shown (see .ruler-mark .lbl). */
function Mark({ className, left, label, at }: { className: string; left: string; label: string; at: string }) {
  return (
    <div className={`ruler-mark ${className}`} style={{ left }}>
      <span className="lbl">{label.trim()} </span>
      <span className="num">{at}</span>
    </div>
  );
}
