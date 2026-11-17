import { useState, type FormEvent } from "react";
import { Link, Navigate, useLocation, useSearchParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { t } from "../../i18n";
import { usePortal } from "../session";
import { AuthShell, portalError } from "../ui";

export function Login() {
  const { me, ready, login, pendingInvite } = usePortal();
  const [params] = useSearchParams();
  const loc = useLocation();
  const [email, setEmail] = useState(params.get("email") ?? "");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  if (ready && me) {
    const from = (loc.state as { from?: string } | null)?.from;
    const to = pendingInvite ? `/invitations/accept?token=${encodeURIComponent(pendingInvite)}` : from ?? "/";
    return <Navigate to={to} replace />;
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t("p.login.failed") : portalError(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell title={t("p.login.title")} lead={t("p.login.lead")}
               foot={<a href="/admin/">{t("p.login.staff")}</a>}>
      <form className="stack" onSubmit={submit}>
        <label className="field">
          <span>{t("p.email")}</span>
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus={!email} />
        </label>
        <label className="field">
          <span>{t("p.password")}</span>
          <input type="password" autoComplete="current-password" required value={password}
                 onChange={(e) => setPassword(e.target.value)} autoFocus={!!email} />
        </label>
        {error && <div className="notice error" role="alert">{error}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">{t("p.login.submit")}</button>
        <div className="row auth-links">
          <Link to="/forgot-password">{t("p.login.forgot")}</Link>
          <span className="spacer" />
          <span className="muted">{t("p.login.noAccount")}</span> <Link to="/signup">{t("p.login.signup")}</Link>
        </div>
      </form>
    </AuthShell>
  );
}
