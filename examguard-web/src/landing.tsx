// The server's front door (/): candidates go to the portal, staff to the Admin Web.
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { t } from "./i18n";
import "./styles/app.css";
import "./styles/portal.css";

function Landing() {
  return (
    <main className="landing">
      <div className="landing-inner">
        <div className="brand brand-ink">
          <span className="brand-mark" aria-hidden>
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M3 8.5l3 3L13 4.5" stroke="currentColor" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </span>
          {t("app.name")}
        </div>
        <h1>{t("landing.title")}</h1>
        <div className="landing-choices">
          <a className="landing-choice" href="/portal/">
            <span className="landing-kicker">{t("landing.candidate")}</span>
            <strong>{t("landing.candidateTitle")}</strong>
            <span>{t("landing.candidateText")}</span>
          </a>
          <a className="landing-choice" href="/admin/">
            <span className="landing-kicker">{t("landing.staff")}</span>
            <strong>{t("landing.staffTitle")}</strong>
            <span>{t("landing.staffText")}</span>
          </a>
        </div>
        <p className="small muted">{t("landing.note")}</p>
      </div>
    </main>
  );
}

createRoot(document.getElementById("root")!).render(<StrictMode><Landing /></StrictMode>);
