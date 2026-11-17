import { useEffect, useRef, useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { t } from "../../i18n";
import { usePortal } from "../session";
import { AuthShell } from "../ui";

export function VerifyEmail() {
  const [params] = useSearchParams();
  const token = params.get("token");
  const { me, reload } = usePortal();
  const [state, setState] = useState<"working" | "ok" | "failed">(token ? "working" : "failed");
  const once = useRef(false);

  useEffect(() => {
    if (!token || once.current) return;
    once.current = true;                         // StrictMode runs effects twice; the token is single use
    api.post("/api/v1/candidate/auth/verify-email", { token })
      .then(() => { setState("ok"); void reload(); })
      .catch(() => setState("failed"));
  }, [token, reload]);

  return (
    <AuthShell title={t("p.verify.title")}>
      {state === "working" && <p className="muted">{t("p.verify.working")}</p>}
      {state === "ok" && (
        <>
          <div className="notice ok" role="status">{t("p.verify.ok")}</div>
          <Link className="btn btn-primary" to={me ? "/" : "/login"}>{me ? t("p.nav.mine") : t("p.toLogin")}</Link>
        </>
      )}
      {state === "failed" && (
        <>
          <div className="notice warn" role="alert">{t("p.verify.failed")}</div>
          <ResendVerification initial={me?.email ?? ""} />
        </>
      )}
    </AuthShell>
  );
}

export function ResendVerification({ initial = "", compact = false }: { initial?: string; compact?: boolean }) {
  const [email, setEmail] = useState(initial);
  const [sent, setSent] = useState(false);
  async function submit(e: FormEvent) {
    e.preventDefault();
    await api.post("/api/v1/candidate/auth/resend-verification", { email }).catch(() => undefined);
    setSent(true);
  }
  if (sent) return <p className="small" role="status">{t("p.verify.sent")}</p>;
  return (
    <form className={compact ? "row" : "stack"} onSubmit={submit}>
      {!compact && (
        <label className="field">
          <span>{t("p.email")}</span>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
        </label>
      )}
      <button className="btn btn-sm" type="submit">{t("p.verify.resend")}</button>
    </form>
  );
}
