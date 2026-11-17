import { BrowserRouter, Navigate, NavLink, Outlet, Route, Routes, useLocation } from "react-router-dom";
import { Loading, ToastProvider } from "../components/ui";
import { t } from "../i18n";
import { Catalog } from "./pages/Catalog";
import { ForgotPassword, ResetPassword } from "./pages/Password";
import { Invitation } from "./pages/Invitation";
import { Login } from "./pages/Login";
import { MyExams } from "./pages/MyExams";
import { Profile } from "./pages/Profile";
import { Signup } from "./pages/Signup";
import { VerifyEmail } from "./pages/VerifyEmail";
import { PortalSessionProvider, usePortal } from "./session";
import { Brand } from "./ui";

function Shell() {
  const { me, logout } = usePortal();
  return (
    <div className="portal">
      <header className="topbar">
        <div className="topbar-inner">
          <Brand />
          <nav className="topnav" aria-label="Menu">
            <NavLink to="/" end>{t("p.nav.mine")}</NavLink>
            <NavLink to="/catalog">{t("p.nav.catalog")}</NavLink>
            <NavLink to="/profile">{t("p.nav.profile")}</NavLink>
          </nav>
          <span className="spacer" />
          <span className="topbar-user">{me?.full_name}</span>
          <button className="btn btn-sm" onClick={() => void logout()}>{t("p.nav.logout")}</button>
        </div>
      </header>
      <main className="portal-main">
        <Outlet />
      </main>
    </div>
  );
}

/** Pages behind sign-in; others redirect to /login and come back afterwards. */
function RequireLogin() {
  const { ready, me } = usePortal();
  const loc = useLocation();
  if (!ready) return <div className="portal-main"><Loading /></div>;
  if (!me) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />;
  return <Shell />;
}

export function PortalApp() {
  return (
    <BrowserRouter basename="/portal">
      <ToastProvider>
        <PortalSessionProvider>
          <Routes>
            <Route path="login" element={<Login />} />
            <Route path="signup" element={<Signup />} />
            <Route path="verify-email" element={<VerifyEmail />} />
            <Route path="forgot-password" element={<ForgotPassword />} />
            <Route path="reset-password" element={<ResetPassword />} />
            <Route path="invitations/accept" element={<Invitation />} />
            <Route element={<RequireLogin />}>
              <Route index element={<MyExams />} />
              <Route path="catalog" element={<Catalog />} />
              <Route path="profile" element={<Profile />} />
            </Route>
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </PortalSessionProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
