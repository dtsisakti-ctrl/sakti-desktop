import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { Field } from "../../components/ui";
import { t } from "../../i18n";
import { AuthShell, PortalError } from "../ui";

export function ForgotPassword() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    await api.post("/api/v1/candidate/auth/password-reset/request", { email }).catch(() => undefined);
    setBusy(false);
    setSent(true);
  }
  return (
    <AuthShell title={t("p.forgot.title")} lead={sent ? undefined : t("p.forgot.lead")}
               foot={<Link to="/login">{t("p.toLogin")}</Link>}>
      {sent ? <div className="notice ok" role="status">{t("p.forgot.sent")}</div> : (
        <form className="stack" onSubmit={submit}>
          <label className="field">
            <span>{t("p.email")}</span>
            <input type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
          </label>
          <button className="btn btn-primary" disabled={busy} type="submit">{t("p.forgot.submit")}</button>
        </form>
      )}
    </AuthShell>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const mismatch = confirm.length > 0 && confirm !== password;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (mismatch) return;
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/candidate/auth/password-reset/confirm", { token, password });
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }
  if (!token) {
    return (
      <AuthShell title={t("p.reset.title")} foot={<Link to="/forgot-password">{t("p.login.forgot")}</Link>}>
        <div className="notice warn">{t("p.reset.missing")}</div>
      </AuthShell>
    );
  }
  return (
    <AuthShell title={t("p.reset.title")}>
      {done ? (
        <>
          <div className="notice ok" role="status">{t("p.reset.ok")}</div>
          <Link className="btn btn-primary" to="/login">{t("p.toLogin")}</Link>
        </>
      ) : (
        <form className="stack" onSubmit={submit}>
          <Field label={t("p.newPassword")} hint={t("p.signup.passwordHint")}>
            <input type="password" required minLength={10} autoComplete="new-password" value={password}
                   onChange={(e) => setPassword(e.target.value)} autoFocus />
          </Field>
          <Field label={t("p.reset.confirm")} hint={mismatch ? t("p.reset.mismatch") : undefined}>
            <input type="password" required autoComplete="new-password" value={confirm}
                   aria-invalid={mismatch} onChange={(e) => setConfirm(e.target.value)} />
          </Field>
          <PortalError error={error} />
          {error ? <Link to="/forgot-password">{t("p.login.forgot")}</Link> : null}
          <button className="btn btn-primary" disabled={busy || mismatch} type="submit">{t("p.reset.submit")}</button>
        </form>
      )}
    </AuthShell>
  );
}
