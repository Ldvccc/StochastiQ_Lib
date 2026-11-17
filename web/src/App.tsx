import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { Loading } from "./components/common";
import { AppLayout, ProjectLayout } from "./components/Layout";
import { LoginPage, RegisterPage, RequireAuth } from "./pages/AuthPages";
import { InvitationPage } from "./pages/InvitationPage";
import { ProjectPage } from "./pages/ProjectPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { TeamPage } from "./pages/TeamPage";

// Écrans scientifiques chargés à la demande : ils embarquent les graphiques (Recharts).
const ProblemsPage = lazy(() => import("./pages/ProblemsPage").then((m) => ({ default: m.ProblemsPage })));
const CustomAnsatzPage = lazy(() => import("./pages/CustomAnsatzPage").then((m) => ({ default: m.CustomAnsatzPage })));
const RecommendationPage = lazy(() => import("./pages/RecommendationPage").then((m) => ({ default: m.RecommendationPage })));
const ReportPage = lazy(() => import("./pages/ReportPage").then((m) => ({ default: m.ReportPage })));
const TrainingPage = lazy(() => import("./pages/TrainingPage").then((m) => ({ default: m.TrainingPage })));
const DiagnosticPage = lazy(() => import("./pages/DiagnosticPage").then((m) => ({ default: m.DiagnosticPage })));
const ComparePage = lazy(() => import("./pages/ComparePage").then((m) => ({ default: m.ComparePage })));
const AnsatzPage = lazy(() => import("./pages/AnsatzPage").then((m) => ({ default: m.AnsatzPage })));
const BarrenPage = lazy(() => import("./pages/BarrenPage").then((m) => ({ default: m.BarrenPage })));
const JobsPage = lazy(() => import("./pages/JobsPage").then((m) => ({ default: m.JobsPage })));
const RunDetailPage = lazy(() => import("./pages/JobsPage").then((m) => ({ default: m.RunDetailPage })));

function Screen({ children }: { children: ReactNode }) {
  return <Suspense fallback={<Loading label="Chargement de l'écran" />}>{children}</Suspense>;
}

export function AppRoutes() {
  return (
    <AuthProvider>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/invitations/:token" element={<InvitationPage />} />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route path="/projects" element={<ProjectsPage />} />
        </Route>
        <Route
          path="/projects/:projectId"
          element={
            <RequireAuth>
              <ProjectLayout />
            </RequireAuth>
          }
        >
          <Route index element={<ProjectPage />} />
          <Route path="equipe" element={<TeamPage />} />
          <Route path="problemes" element={<Screen><ProblemsPage /></Screen>} />
          <Route path="diagnostic" element={<Screen><DiagnosticPage /></Screen>} />
          <Route path="comparateur" element={<Screen><ComparePage /></Screen>} />
          <Route path="ansatz" element={<Screen><AnsatzPage /></Screen>} />
          <Route path="mes-ansatz" element={<Screen><CustomAnsatzPage /></Screen>} />
          <Route path="entrainement" element={<Screen><TrainingPage /></Screen>} />
          <Route path="recommandation" element={<Screen><RecommendationPage /></Screen>} />
          <Route path="rapport" element={<Screen><ReportPage /></Screen>} />
          <Route path="plateau-sterile" element={<Screen><BarrenPage /></Screen>} />
          <Route path="jobs" element={<Screen><JobsPage /></Screen>} />
          <Route path="jobs/:runId" element={<Screen><RunDetailPage /></Screen>} />
        </Route>
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </AuthProvider>
  );
}
