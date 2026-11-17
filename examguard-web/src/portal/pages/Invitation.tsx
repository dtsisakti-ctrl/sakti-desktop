import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../../api/client";
import { Loading, useToast } from "../../components/ui";
import { t, type Key } from "../../i18n";
import { useLoad } from "../../lib/hooks";
import { longDate, time, zoneLabel } from "../../lib/time";
import { usePortal } from "../session";
import type { InvitationPreview } from "../types";
import { AuthShell, PortalError } from "../ui";
import { ResendVerification } from "./VerifyEmail";

/** Invitation link from the email (PRD §28.3): shows what it is for, then accepts it for the signed-in account. */
export function Invitation() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const { me, ready, logout, setPendingInvite } = usePortal();
  const nav = useNavigate();
  const toast = useToast();
  const q = useLoad(() => api.post<InvitationPreview>("/api/v1/public/invitations/preview", { token }), [token]);
  const [error, setError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  const inv = q.data;
  const matches = !!me && !!inv && me.email.toLowerCase() === inv.email.toLowerCase();

  // remember the link across sign-up, email verification and sign-in
  useEffect(() => {
    if (inv?.status === "PENDING" && ready && !me) setPendingInvite(token);
    if (inv && inv.status !== "PENDING") setPendingInvite(null);
  }, [inv, ready, me, token, setPendingInvite]);

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      await api.post("/api/v1/candidate/invitations/accept", { token });
      setPendingInvite(null);
      toast(t("p.inv.accepted"));
      nav("/", { replace: true });
    } catch (e) {
      setError(e);
    } finally {
      setBusy(false);
    }
  }

  if (!token) return <AuthShell title={t("p.inv.title")}><div className="notice warn">{t("p.inv.invalid")}</div></AuthShell>;
  return (
    <AuthShell title={t("p.inv.title")} foot={me ? <Link to="/">{t("p.nav.mine")}</Link> : undefined}>
      {(q.loading || !ready) && !inv && !q.error && <Loading />}
      {q.error ? <div className="notice warn" role="alert">{t("p.inv.invalid")}</div> : null}
      {inv && (
        <div className="stack">
          <div className="invite-card">
            <span className="muted small">{inv.org_name}</span>
            <strong>{inv.exam_name}</strong>
            {inv.window_start && (
              <span className="num">{longDate(inv.window_start)}, {time(inv.window_start)}–{time(inv.window_end)} {zoneLabel()}</span>
            )}
          </div>
          <p>{t("p.inv.lead", { org: inv.org_name, exam: inv.exam_name })} {t("p.inv.sentTo", { email: inv.email })}</p>
          {inv.status !== "PENDING" && <div className="notice warn">{t(`p.inv.${inv.status}` as Key)}</div>}
          {inv.status === "PENDING" && ready && !me && (
            inv.account_exists ? (
              <>
                <p className="muted">{t("p.inv.loginFirst", { email: inv.email })}</p>
                <Link className="btn btn-primary" to={`/login?email=${encodeURIComponent(inv.email)}`}>{t("p.login.submit")}</Link>
              </>
            ) : (
              <>
                <p className="muted">{t("p.inv.signupFirst", { email: inv.email })}</p>
                <Link className="btn btn-primary" to={`/signup?email=${encodeURIComponent(inv.email)}`}>{t("p.login.signup")}</Link>
              </>
            )
          )}
          {inv.status === "PENDING" && me && !matches && (
            <>
              <div className="notice warn">{t("p.inv.mismatch", { me: me.email, email: inv.email })}</div>
              <button className="btn" onClick={() => void logout()}>{t("p.nav.logout")}</button>
            </>
          )}
          {inv.status === "PENDING" && me && matches && (
            me.email_verified_at ? (
              <button className="btn btn-primary" disabled={busy} onClick={() => void accept()}>{t("p.inv.accept")}</button>
            ) : (
              <>
                <div className="notice warn">{t("p.verify.banner")}</div>
                <ResendVerification initial={me.email} compact />
              </>
            )
          )}
          <PortalError error={error} />
        </div>
      )}
    </AuthShell>
  );
}
