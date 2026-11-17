# 00-standards/ui: Web UI Standards (Admin Web & Candidate Portal)

---

## 1. Single App Architecture with Distinct Entrypoints
`examguard-web` is a single React + Vite project serving two primary endpoints:
- `/admin/`: Back-office and invigilation dashboard.
- `/portal/`: Candidate exam registration and launch gate.
- `/`: Landing page allowing users to choose their path.

---

## 2. Desktop-First Design Rule (PRD §28.5)
Both the Admin Web and Candidate Portal are designed for **laptop and desktop screens** (minimum width 1024px) where exams are operated and taken. While layouts must remain readable on mobile viewports, full table functionality and live monitoring grids are optimized for multi-column desktop views.

---

## 3. Mandatory 5 UI States
1. **Loading Skeleton**: Card and table skeleton pulses while querying endpoints.
2. **Empty State**: Friendly copy with call-to-action (e.g. "Belum ada ujian aktif").
3. **Error State**: Actionable error banner with server error code.
4. **Forbidden State**: Clear unauthorized notice (e.g. Candidate attempting to access `/admin/`).
5. **Happy Path**: Real-time polling updates every 2 seconds on the live monitoring dashboard.

