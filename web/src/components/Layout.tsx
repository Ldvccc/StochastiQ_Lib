import { NavLink, Outlet, useParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { Logo } from "./common";
import { ProjectProvider, useProject } from "./ProjectContext";

const PROJECT_NAV = [
  { to: "", label: "Projet", end: true },
  { to: "diagnostic", label: "Diagnostic" },
  { to: "comparateur", label: "Comparateur" },
  { to: "ansatz", label: "Ansatz" },
  { to: "plateau-sterile", label: "Plateau stérile" },
  { to: "jobs", label: "Jobs et matériel" },
  { to: "equipe", label: "Équipe" },
];

function Sidebar({ projectNav }: { projectNav: boolean }) {
  const { user, logout } = useAuth();
  const { projectId } = useParams();
  return (
    <nav className="sidebar" aria-label="Navigation principale">
      <Logo />
      <NavLink to="/projects" end className="nav">
        Tous les projets
      </NavLink>
      {projectNav && <ProjectLinks projectId={projectId!} />}
      <div className="spacer" />
      {user && (
        <div className="project-name muted" aria-label="Utilisateur connecté">
          {user.name}
        </div>
      )}
      <button type="button" className="secondary" onClick={logout}>
        Se déconnecter
      </button>
    </nav>
  );
}

function ProjectLinks({ projectId }: { projectId: string }) {
  const { project } = useProject();
  return (
    <>
      <div className="project-name muted">{project.name}</div>
      {PROJECT_NAV.map((item) => (
        <NavLink
          key={item.label}
          to={`/projects/${projectId}${item.to ? `/${item.to}` : ""}`}
          end={item.end}
          className="nav"
        >
          {item.label}
        </NavLink>
      ))}
    </>
  );
}

/** Mise en page hors projet (liste des projets). */
export function AppLayout() {
  return (
    <div className="app">
      <Sidebar projectNav={false} />
      <main className="content">
        <Outlet />
      </main>
    </div>
  );
}

/** Mise en page d'un projet : charge le projet et le rôle de l'utilisateur. */
export function ProjectLayout() {
  return (
    <ProjectProvider>
      <div className="app">
        <Sidebar projectNav />
        <main className="content">
          <Outlet />
        </main>
      </div>
    </ProjectProvider>
  );
}
