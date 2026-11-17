import { NavLink, Outlet } from "react-router-dom";
import { useSession } from "../auth/session";
import { t } from "../i18n";

export function Layout() {
  const { me, org, switchOrg, logout } = useSession();
  if (!me) return null;
  return (
    <div className="shell">
      <aside className="nav">
        <div className="brand">
          <span className="brand-mark" aria-hidden>
            <svg width="14" height="14" viewBox="0 0 16 16"><path d="M3 8.5l3 3L13 4.5" stroke="currentColor" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" /></svg>
          </span>
          {t("app.name")}
        </div>
        <div className="org-block">
          <label className="org-label" htmlFor="org">{t("nav.org")}</label>
          {me.memberships.length > 1 ? (
            <select id="org" className="org-switch" value={org?.org_id ?? ""} onChange={(e) => switchOrg(e.target.value)}>
              {me.memberships.map((m) => <option key={m.org_id} value={m.org_id}>{m.org_name}</option>)}
            </select>
          ) : (
            <div id="org" className="org-switch">{org?.org_name}</div>
          )}
        </div>
        <nav className="nav-links" aria-label="Menu">
          <NavLink to="/" end>{t("nav.dashboard")}</NavLink>
          <NavLink to="/exams">{t("nav.exams")}</NavLink>
        </nav>
        <div className="nav-foot">
          <span>{t("nav.signedInAs", { name: me.full_name })}</span>
          <span>{org?.roles.join(", ")}</span>
          <button className="btn btn-sm btn-ghost-dark" onClick={() => void logout()}>{t("nav.logout")}</button>
        </div>
      </aside>
      <main className="main" key={org?.org_id}>
        <Outlet />
      </main>
    </div>
  );
}
