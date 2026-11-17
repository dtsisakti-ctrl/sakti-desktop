import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { Field } from "../../components/ui";
import { t } from "../../i18n";
import { AuthShell, PortalError } from "../ui";

export function Signup() {
  const [params] = useSearchParams();
  const fixedEmail = params.get("email");        // from an invitation: the account must use that address
  const [email, setEmail] = useState(fixedEmail ?? "");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/candidate/auth/signup", { email, full_name: name, password });
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <AuthShell title={t("p.signup.title")}>
        <div className="notice ok" role="status">{t("p.signup.done", { email })}</div>
        <Link className="btn" to={`/login?email=${encodeURIComponent(email)}`}>{t("p.toLogin")}</Link>
      </AuthShell>
    );
  }
  return (
    <AuthShell title={t("p.signup.title")} lead={t("p.signup.lead")}
               foot={<><span className="muted">{t("p.signup.haveAccount")}</span> <Link to="/login">{t("p.login.submit")}</Link></>}>
      <form className="stack" onSubmit={submit}>
        <Field label={t("p.signup.name")}>
          <input required maxLength={200} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} autoFocus />
        </Field>
        <Field label={t("p.email")}>
          <input type="email" required autoComplete="email" value={email} readOnly={!!fixedEmail}
                 onChange={(e) => setEmail(e.target.value)} />
        </Field>
        <Field label={t("p.password")} hint={t("p.signup.passwordHint")}>
          <input type="password" required minLength={10} autoComplete="new-password" value={password}
                 onChange={(e) => setPassword(e.target.value)} />
        </Field>
        <PortalError error={error} />
        <button className="btn btn-primary" disabled={busy} type="submit">{t("p.signup.submit")}</button>
      </form>
    </AuthShell>
  );
}
