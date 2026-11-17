import { describe, expect, it } from "vitest";
import { until } from "../lib/time";
import { filterCatalog } from "../portal/pages/Catalog";
import { historyText, isHistory, phaseText } from "../portal/pages/MyExams";
import type { CatalogExam, Enrollment } from "../portal/types";

const exam = {
  id: "x", code: "EPT-A", name: "EPT Sesi A", series: "EPT", visibility: "PUBLIC" as const, status: "READY",
  window_start: "2026-10-31T09:00:00Z", window_end: "2026-10-31T11:00:00Z", checkin_open: "2026-10-31T08:30:00Z",
  registration_close: "2026-10-30T09:00:00Z", latest_start: "2026-10-31T09:30:00Z", duration_minutes: 90,
  description: null, identity_check: "NONE", org_name: "Lembaga Tes",
};
const enr = (over: Partial<Enrollment>): Enrollment => ({
  id: "e", status: "CONFIRMED", source: "SELF_REGISTERED", created_at: "2026-10-01T00:00:00Z", cancelled_at: null,
  attempt_status: "NOT_STARTED", cancel_reason: null,
  attempt: { id: "a", status: "NOT_STARTED", started_at: null, deadline: null, ended_at: null },
  can_launch: false, launch_reason: "NOT_YET_OPEN", can_change: true, exam, ...over,
});

describe("Ujian saya", () => {
  it("countdown to check-in, then the latest start, then running", () => {
    const now = Date.parse("2026-10-29T06:00:00Z");
    expect(phaseText(enr({}), now)).toBe("Check-in dibuka dalam 2 hari 2 jam");
    expect(phaseText(enr({ can_launch: true, launch_reason: null }), now)).toMatch(/^Check-in sudah dibuka\. Mulai sebelum /);
    const running = enr({ can_launch: true, launch_reason: null,
      attempt: { id: "a", status: "INTERRUPTED", started_at: exam.window_start, deadline: null, ended_at: null } });
    expect(phaseText(running, now)).toContain("sedang berjalan");
    expect(phaseText(enr({ launch_reason: "LATE_START_CLOSED" }), now)).toBe("Batas waktu mulai sudah lewat.");
  });
  it("history: ended attempts, cancelled enrollments and cancelled exams", () => {
    const done = enr({ attempt: { id: "a", status: "SUBMITTED", started_at: null, deadline: null, ended_at: null } });
    expect(isHistory(done) && historyText(done)).toBe("Selesai");
    const moved = enr({ status: "CANCELLED", cancel_reason: "MOVED" });
    expect(isHistory(moved) && historyText(moved)).toBe("Dipindahkan ke sesi lain");
    const gone = enr({ exam: { ...exam, status: "CANCELLED" } });
    expect(isHistory(gone) && historyText(gone)).toBe("Ujian dibatalkan penyelenggara");
    expect(isHistory(enr({}))).toBe(false);
  });
  it("until() reads like a person would say it", () => {
    expect(until(30_000)).toBe("< 1 menit");
    expect(until(8 * 60_000)).toBe("8 menit");
    expect(until((3 * 60 + 10) * 60_000)).toBe("3 jam 10 menit");
    expect(until(2 * 86_400_000)).toBe("2 hari");
  });
});

describe("Katalog", () => {
  const rows = [
    { ...exam, org_name: "Lembaga Tes", registration_open: null, registration_status: "OPEN", seats_left: 3,
      requires_access_code: false, identity_check: "NONE" },
    { ...exam, id: "y", code: "TKD-1", name: "Tes Kompetensi Dasar", series: "TKD", window_start: "2026-11-20T02:00:00Z",
      org_name: "Instansi Lain", registration_open: null, registration_status: "FULL", seats_left: 0,
      requires_access_code: true, identity_check: "MANUAL" },
  ] as CatalogExam[];
  it("filters by text, series and start date", () => {
    expect(filterCatalog(rows, "lembaga", "", "").map((r) => r.code)).toEqual(["EPT-A"]);
    expect(filterCatalog(rows, "", "TKD", "").map((r) => r.code)).toEqual(["TKD-1"]);
    expect(filterCatalog(rows, "", "", "2026-11-01").map((r) => r.code)).toEqual(["TKD-1"]);
    expect(filterCatalog(rows, "tkd-1", "EPT", "")).toEqual([]);
  });
});
