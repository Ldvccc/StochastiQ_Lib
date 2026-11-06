import { Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./auth/AuthContext";
import { Empty } from "./components/common";
import { AppLayout, ProjectLayout } from "./components/Layout";
import { LoginPage, RegisterPage, RequireAuth } from "./pages/AuthPages";
import { InvitationPage } from "./pages/InvitationPage";
import { ProjectPage } from "./pages/ProjectPage";
import { ProjectsPage } from "./pages/ProjectsPage";
import { TeamPage } from "./pages/TeamPage";

function Pending({ name }: { name: string }) {
  return (
    <>
      <h1>{name}</h1>
      <Empty>Écran prévu au jalon suivant (M4).</Empty>
    </>
  );
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
          <Route path="diagnostic" element={<Pending name="Diagnostic" />} />
          <Route path="comparateur" element={<Pending name="Comparateur" />} />
          <Route path="ansatz" element={<Pending name="Ansatz" />} />
          <Route path="plateau-sterile" element={<Pending name="Plateau stérile" />} />
          <Route path="jobs" element={<Pending name="Jobs et matériel" />} />
          <Route path="jobs/:runId" element={<Pending name="Détail du run" />} />
        </Route>
        <Route path="*" element={<Navigate to="/projects" replace />} />
      </Routes>
    </AuthProvider>
  );
}
