// All times come from the server as UTC ISO strings and are shown in the browser's time zone.

const fmtTime = new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit" });
const fmtTimeSec = new Intl.DateTimeFormat("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" });
const fmtDate = new Intl.DateTimeFormat("id-ID", { weekday: "short", day: "numeric", month: "short", year: "numeric" });
const fmtDateTime = new Intl.DateTimeFormat("id-ID", {
  day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit",
});

const d = (iso: string) => new Date(iso);
export const time = (iso?: string | null) => (iso ? fmtTime.format(d(iso)) : "—");
export const timeSec = (iso?: string | null) => (iso ? fmtTimeSec.format(d(iso)) : "—");
export const date = (iso?: string | null) => (iso ? fmtDate.format(d(iso)) : "—");
export const dateTime = (iso?: string | null) => (iso ? fmtDateTime.format(d(iso)) : "—");

export function zoneLabel(): string {
  const off = -new Date().getTimezoneOffset();
  const named: Record<number, string> = { 420: "WIB", 480: "WITA", 540: "WIT" };
  if (named[off]) return named[off];
  const sign = off >= 0 ? "+" : "-";
  return `UTC${sign}${String(Math.floor(Math.abs(off) / 60)).padStart(2, "0")}:${String(Math.abs(off) % 60).padStart(2, "0")}`;
}

/** 5025 → "01:23:45" */
export function clock(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const s = Math.max(0, Math.round(seconds));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

/** 858 → "14 m 18 d" (menit, detik) */
export function gap(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  if (m >= 60) return `${Math.floor(m / 60)} j ${m % 60} m`;
  return m ? `${m} m ${s} d` : `${s} d`;
}

/** ISO → value for <input type="datetime-local"> in local time */
export function toLocalInput(iso?: string | null): string {
  if (!iso) return "";
  const x = d(iso);
  const p = (n: number) => String(n).padStart(2, "0");
  return `${x.getFullYear()}-${p(x.getMonth() + 1)}-${p(x.getDate())}T${p(x.getHours())}:${p(x.getMinutes())}`;
}

/** <input type="datetime-local"> value (local) → ISO with offset, or null */
export function fromLocalInput(v: string): string | null {
  if (!v) return null;
  const x = new Date(v);
  return Number.isNaN(x.getTime()) ? null : x.toISOString();
}

/** Rough time until a moment, for countdowns: "2 hari 3 jam", "3 jam 10 menit", "8 menit", "< 1 menit". */
export function until(ms: number): string {
  if (ms < 60_000) return "< 1 menit";
  const m = Math.floor(ms / 60_000);
  const d = Math.floor(m / 1440);
  const h = Math.floor((m % 1440) / 60);
  const min = m % 60;
  if (d) return h ? `${d} hari ${h} jam` : `${d} hari`;
  if (h) return min ? `${h} jam ${min} menit` : `${h} jam`;
  return `${min} menit`;
}

const fmtDay = new Intl.DateTimeFormat("id-ID", { day: "numeric" });
const fmtMonth = new Intl.DateTimeFormat("id-ID", { month: "short" });
const fmtWeekday = new Intl.DateTimeFormat("id-ID", { weekday: "long" });
const fmtLongDate = new Intl.DateTimeFormat("id-ID", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
/** Parts for a calendar block: { day: "12", month: "Okt", weekday: "Sabtu" } */
export function dayParts(iso: string) {
  const x = new Date(iso);
  return { day: fmtDay.format(x), month: fmtMonth.format(x).replace(".", ""), weekday: fmtWeekday.format(x) };
}
export const longDate = (iso?: string | null) => (iso ? fmtLongDate.format(new Date(iso)) : "—");
