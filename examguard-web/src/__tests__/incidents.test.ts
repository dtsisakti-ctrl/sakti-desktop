import { describe, expect, it } from "vitest";
import type { Incident } from "../api/types";
import { eventDescription, eventLabel, incidentDuration, incidentFacts } from "../lib/incidents";

const base: Incident = {
  id: "i", attempt_id: "a", type: "FACE_MISSING", severity: "MEDIUM", status: "OPEN",
  started_at: "2026-10-25T02:00:00Z", ended_at: "2026-10-25T02:00:42Z", event_count: 2, data: {}, review_note: null,
};

describe("incident display", () => {
  it("labels known event types in Indonesian and keeps unknown codes", () => {
    expect(eventLabel("FOCUS_LOST")).toBe("Keluar dari jendela ujian");
    expect(eventLabel("NEW_SENSOR_X")).toBe("NEW_SENSOR_X");
    expect(eventDescription("UNMONITORED_INTERRUPTION")).toContain("tidak terpantau");
    expect(eventDescription("NEW_SENSOR_X")).toBeNull();
  });
  it("duration: finished, instant, and ongoing counted to now", () => {
    expect(incidentDuration(base, 0)).toBe("42 d");
    expect(incidentDuration({ ...base, ended_at: base.started_at }, 0)).toBe("sesaat");
    const now = Date.parse("2026-10-25T02:03:10Z");
    expect(incidentDuration({ ...base, ended_at: null }, now)).toBe("berlangsung 3 m 10 d");
  });
  it("facts: interruption cause, AI confidence, merged events", () => {
    expect(incidentFacts({ ...base, event_count: 1, data: { cause: "CLIENT_CRASH", gap_seconds: 45 } }))
      .toEqual(["penyebab: client crash atau ditutup"]);
    expect(incidentFacts({ ...base, data: { confidence: 0.83 } })).toEqual(["keyakinan 83%", "2 event"]);
  });
});
