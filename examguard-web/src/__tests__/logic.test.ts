import { describe, expect, it } from "vitest";
import type { AttemptRow } from "../api/types";
import { t, tx } from "../i18n";
import { id } from "../i18n/id";
import { clock, fromLocalInput, gap, toLocalInput } from "../lib/time";
import { needsAttention, remainingNow } from "../pages/tabs/Live";

const row = (over: Partial<AttemptRow>): AttemptRow => ({
  attempt_id: "a", enrollment_id: "e", candidate_id: "c", candidate_name: "N", candidate_email: "n@x",
  status: "ACTIVE", state_version: 1, connection_status: "ONLINE", last_seen_at: null, started_at: null,
  deadline: null, remaining_seconds: 600, paused_at: null, pause_timer_mode: null, identity_status: "NONE",
  time_accommodation_minutes: 0, reopen_count: 0, reinstate_count: 0, termination_reason_category: null,
  final_status: null, open_incidents: 0, health: {}, client_version: null, ...over,
});

describe("countdown between polls", () => {
  it("ticks down locally from the server value", () => {
    expect(remainingNow(row({}), 1_000, 11_000)).toBe(590);
    expect(remainingNow(row({ remaining_seconds: 5 }), 0, 60_000)).toBe(0);
  });
  it("is frozen while paused with PAUSE_TIMER but keeps running with KEEP_RUNNING", () => {
    expect(remainingNow(row({ status: "PAUSED", pause_timer_mode: "PAUSE_TIMER" }), 0, 60_000)).toBe(600);
    expect(remainingNow(row({ status: "PAUSED", pause_timer_mode: "KEEP_RUNNING" }), 0, 60_000)).toBe(540);
  });
  it("shows nothing for ended or not started attempts", () => {
    expect(remainingNow(row({ status: "SUBMITTED" }), 0, 0)).toBeNull();
    expect(remainingNow(row({ status: "NOT_STARTED", remaining_seconds: null }), 0, 0)).toBeNull();
  });
});

describe("attention highlight", () => {
  it.each([
    [{ status: "INTERRUPTED" as const }, true],
    [{ status: "WAITING_FOR_INVIGILATOR" as const }, true],
    [{ open_incidents: 1 }, true],
    [{ identity_status: "PENDING", status: "NOT_STARTED" as const }, true],
    [{ connection_status: "OFFLINE" as const }, true],
    [{ connection_status: "OFFLINE" as const, status: "SUBMITTED" as const }, false],
    [{ status: "NOT_STARTED" as const, connection_status: "OFFLINE" as const }, false],
    [{}, false],
  ])("%o → %s", (over, expected) => {
    expect(needsAttention(row(over))).toBe(expected);
  });
});

describe("time helpers", () => {
  it("formats clocks and gaps", () => {
    expect(clock(5025)).toBe("01:23:45");
    expect(clock(null)).toBe("—");
    expect(gap(858)).toBe("14 m 18 d");
    expect(gap(42)).toBe("42 d");
    expect(gap(3725)).toBe("1 j 2 m");
  });
  it("round-trips datetime-local values through ISO", () => {
    const iso = fromLocalInput("2026-10-12T09:30")!;
    expect(toLocalInput(iso)).toBe("2026-10-12T09:30");
    expect(fromLocalInput("")).toBeNull();
  });
});

describe("i18n", () => {
  it("interpolates and falls back to raw codes", () => {
    expect(t("common.minutes", { n: 5 })).toBe("5 menit");
    expect(tx("status", "ACTIVE")).toBe("Mengerjakan");
    expect(tx("status", "SOMETHING_NEW")).toBe("SOMETHING_NEW");
  });
  it("has a label for every attempt status", () => {
    for (const s of ["NOT_STARTED", "ACTIVE", "PAUSED", "INTERRUPTED", "WAITING_FOR_INVIGILATOR", "REOPENED",
      "REINSTATED", "SUBMITTED", "EXPIRED", "TERMINATED", "NO_SHOW", "FINALIZED"]) {
      expect(`status.${s}` in id).toBe(true);
    }
  });
});
