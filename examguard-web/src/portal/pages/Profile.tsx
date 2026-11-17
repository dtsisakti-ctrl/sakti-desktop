import { useState, type FormEvent } from "react";
import { api } from "../../api/client";
import { Field, useToast } from "../../components/ui";
import { t } from "../../i18n";
import { dateTime } from "../../lib/time";
import { usePortal } from "../session";
import { PortalError } from "../ui";
import { ResendVerification } from "./VerifyEmail";

export function Profile() {
  const { me, reload } = usePortal();
  const toast = useToast();
  const [name, setName] = useState(me?.full_name ?? "");
  const [nameError, setNameError] = useState<unknown>(null);
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [pwError, setPwError] = useState<unknown>(null);
  const [busy, setBusy] = useState(false);
  if (!me) return null;

  async function saveName(e: FormEvent) {
    e.preventDefault();
    setNameError(null);
    try {
      await api.patch("/api/v1/candidate/me", { full_name: name });
      await reload();
      toast(t("p.profile.saved"));
    } catch (err) {
      setNameError(err);
    }
  }

  async function savePassword(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setPwError(null);
    try {
      await api.post("/api/v1/candidate/me/password", { current_password: current, new_password: next });
      setCurrent("");
      setNext("");
      toast(t("p.profile.passwordSaved"));
    } catch (err) {
      setPwError(err);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="stack narrow" style={{ gap: "1.25rem" }}>
      <h1>{t("p.profile.title")}</h1>
      <form className="panel panel-pad stack" onSubmit={saveName}>
        <h2 className="section-title">{t("p.profile.identity")}</h2>
        <Field label={t("p.signup.name")} hint={t("p.profile.nameHint")}>
          <input required maxLength={200} value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <div className="field">
          <span className="label-like">{t("p.email")}</span>
          <span>{me.email}</span>
          <span className="hint">{me.email_verified_at ? t("p.profile.verified", { time: dateTime(me.email_verified_at) }) : t("p.profile.unverified")}</span>
          {!me.email_verified_at && <ResendVerification initial={me.email} compact />}
        </div>
        <PortalError error={nameError} />
        <div><button className="btn btn-primary" type="submit" disabled={name.trim() === me.full_name}>{t("common.save")}</button></div>
      </form>
      <form className="panel panel-pad stack" onSubmit={savePassword}>
        <h2 className="section-title">{t("p.profile.password")}</h2>
        <Field label={t("p.profile.current")}>
          <input type="password" required autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
        </Field>
        <Field label={t("p.newPassword")} hint={t("p.signup.passwordHint")}>
          <input type="password" required minLength={10} autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
        </Field>
        <PortalError error={pwError} />
        <div><button className="btn btn-primary" type="submit" disabled={busy}>{t("p.profile.password")}</button></div>
      </form>
    </div>
  );
}
