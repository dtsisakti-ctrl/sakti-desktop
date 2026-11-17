# 40-candidate-portal: Module Overview

Coordinates the Candidate Portal interface served at `/portal/`, landing gate at `/`, self-registration, public exam catalogs, private organization invitations, and the time-gated "Mulai Ujian" launcher.

### Views & Components Owned (in `examguard-web/src/portal`)
- `LandingPage.tsx` (Choice: `/portal/` vs `/admin/`)
- `MyExamsView.tsx` (Exam cards, countdowns & launch button)
- `PublicCatalogView.tsx` (Open testing session registration)
- `LaunchExamDialog.tsx` (`examguard://` protocol link generator)
- `PasswordResetView.tsx` (60-minute single-use email token reset)

