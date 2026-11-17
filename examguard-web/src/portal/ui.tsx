// Small pieces shared by the portal pages.
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { ApiError } from "../api/client";
import { errorText } from "../components/ui";
import { t, type Key } from "../i18n";
import { id } from "../i18n/id";

/** Candidate-friendly error text: known codes get a plain sentence, others the server message. */
export function portalError(e: unknown): string {
  if (e instanceof ApiError) {
    const key = `p.err.${e.code}` as Key;
    if (key in id) return t(key);
  }
  return errorText(e);
}

export function PortalError({ error }: { error: unknown }) {
  if (!error) return null;
  return <div className="notice error" role="alert">{portalError(error)}</div>;
}

export function Brand({ to = "/" }: { to?: string }) {
  return (
    <Link to={to} className="brand brand-ink">
      <span className="brand-mark" aria-hidden>
        <svg width="14" height="14" viewBox="0 0 16 16"><path d="M3 8.5l3 3L13 4.5" stroke="currentColor" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
      </span>
      {t("app.name")} <span className="brand-sub">{t("p.app")}</span>
    </Link>
  );
}

/** Centered card for sign-in, sign-up and the email-link pages. */
export function AuthShell({ title, lead, children, foot }: { title: string; lead?: string; children: ReactNode; foot?: ReactNode }) {
  return (
    <div className="auth">
      <div className="auth-inner">
        <Brand />
        <section className="auth-card">
          <h1>{title}</h1>
          {lead && <p className="muted">{lead}</p>}
          {children}
        </section>
        {foot && <div className="auth-foot">{foot}</div>}
      </div>
    </div>
  );
}
