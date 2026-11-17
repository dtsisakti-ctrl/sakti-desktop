// Human-readable incidents: what happened, for how long, and the details the client sent (PRD §15, §27.6).
import type { Incident } from "../api/types";
import { t, type Key } from "../i18n";
import { id } from "../i18n/id";
import { gap } from "./time";

/** "FOCUS_LOST" → "Keluar dari jendela ujian"; unknown types (newer clients) keep their code. */
export function eventLabel(type: string): string {
  const key = `evt.${type}` as Key;
  return key in id ? t(key) : type;
}

export function eventDescription(type: string): string | null {
  const key = `evtd.${type}` as Key;
  return key in id ? t(key) : null;
}

/** Seconds the incident lasted; null while it is still going on. */
export function incidentSeconds(i: Pick<Incident, "started_at" | "ended_at">): number | null {
  if (!i.ended_at) return null;
  return Math.max(0, Math.round((Date.parse(i.ended_at) - Date.parse(i.started_at)) / 1000));
}

/** "42 d", "sesaat", or "berlangsung 3 m 10 d" (counted up to `nowMs`). */
export function incidentDuration(i: Pick<Incident, "started_at" | "ended_at">, nowMs: number): string {
  const s = incidentSeconds(i);
  if (s === null) return t("inc.ongoingFor", { d: gap(Math.max(0, Math.round((nowMs - Date.parse(i.started_at)) / 1000))) });
  return s === 0 ? t("inc.instant") : gap(s);
}

/** Short facts from the incident data: cause of an interruption, AI confidence, number of merged events. */
export function incidentFacts(i: Incident): string[] {
  const out: string[] = [];
  const d = i.data ?? {};
  if (typeof d.cause === "string") {
    const key = `cause.${d.cause}` as Key;
    out.push(t("inc.cause", { cause: key in id ? t(key) : d.cause }));
  }
  if (typeof d.confidence === "number") out.push(t("inc.confidence", { n: Math.round(d.confidence * 100) }));
  if (i.event_count > 1) out.push(t("inc.times", { n: i.event_count }));
  return out;
}
