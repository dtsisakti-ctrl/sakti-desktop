import { useState, type FormEvent } from "react";
import { ApiError } from "../api/client";
import { useSession } from "../auth/session";
import { errorText } from "../components/ui";
import { t } from "../i18n";

// The left side shows what the product is for: an attendance register where the rows that need
// an invigilator are highlighted.
const SAMPLE = [
  ["1", "Budi Santoso", "Mengerjakan"],
  ["2", "Rina Amalia", "Menunggu persetujuan"],
  ["3", "Dewi Lestari", "Mengerjakan"],
  ["4", "Agus Pratama", "Terputus"],
  ["5", "Sari Wulandari", "Mengerjakan"],
];

export function Login() {
  const { login } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await login(email, password);
    } catch (err) {
      setError(err instanceof ApiError && err.status === 401 ? t("login.failed") : errorText(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login-side">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M3 8.5l3 3L13 4.5" stroke="currentColor" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </span>
          {t("app.name")} {t("app.admin")}
        </div>
        <div className="stack">
          <h1>{t("login.title")}</h1>
          <p style={{ maxWidth: "42ch" }}>{t("login.lead")}</p>
        </div>
        <div className="login-sheet" aria-hidden>
          {SAMPLE.map(([n, name, st]) => (
            <div key={n} className={st === "Mengerjakan" ? "" : "hl"}>
              <span>{n}</span>
              <span>{name}</span>
              <span>{st}</span>
            </div>
          ))}
        </div>
      </section>
      <form className="login-form" onSubmit={submit}>
        <h2>{t("login.submit")}</h2>
        <label className="field">
          <span>{t("login.email")}</span>
          <input type="email" autoComplete="username" required value={email} onChange={(e) => setEmail(e.target.value)} autoFocus />
        </label>
        <label className="field">
          <span>{t("login.password")}</span>
          <input type="password" autoComplete="current-password" required value={password} onChange={(e) => setPassword(e.target.value)} />
        </label>
        {error && <div className="notice error" role="alert">{error}</div>}
        <button className="btn btn-primary" disabled={busy} type="submit">{t("login.submit")}</button>
      </form>
    </div>
  );
}
