import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { SessionProvider, useSession } from "./auth/session";
import { Layout } from "./components/Layout";
import { Loading, ToastProvider } from "./components/ui";
import { t } from "./i18n";
import { Dashboard } from "./pages/Dashboard";
import { ExamDetail } from "./pages/ExamDetail";
import { ExamForm } from "./pages/ExamForm";
import { Exams } from "./pages/Exams";
import { Login } from "./pages/Login";

function Gate() {
  const { ready, me, org } = useSession();
  if (!ready) return <div className="main"><Loading /></div>;
  if (!me) return <Login />;
  if (!org) {
    return <div className="main"><div className="notice warn">{t("login.noOrg")}</div></div>;
  }
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route index element={<Dashboard />} />
        <Route path="exams" element={<Exams />} />
        <Route path="exams/new" element={<ExamForm />} />
        <Route path="exams/:examId/edit" element={<ExamForm />} />
        <Route path="exams/:examId/*" element={<ExamDetail />} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}

export function App() {
  return (
    <BrowserRouter basename="/admin">
      <ToastProvider>
        <SessionProvider>
          <Gate />
        </SessionProvider>
      </ToastProvider>
    </BrowserRouter>
  );
}
