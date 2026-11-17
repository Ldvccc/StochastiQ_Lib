import { createContext, useContext, type ReactNode } from "react";
import { useParams } from "react-router-dom";

import { api } from "../api/client";
import type { Permission, Project, RolesInfo } from "../api/types";
import { can, deniedReason, DEFAULT_PERMISSIONS } from "../lib/roles";
import { useAsync } from "../lib/useAsync";
import { ErrorState, Loading } from "./common";

interface ProjectState {
  project: Project;
  permissions: Permission[];
  can: (action: string) => boolean;
  reason: (action: string) => string;
  reload: () => void;
}

const ProjectContext = createContext<ProjectState | null>(null);

export function ProjectProvider({ children }: { children: ReactNode }) {
  const { projectId } = useParams();
  const project = useAsync(() => api.get<Project>(`/projects/${projectId}`), [projectId]);
  const roles = useAsync(() => api.get<RolesInfo>("/roles"), []);

  if (project.loading) return <Loading label="Chargement du projet" />;
  if (project.error || !project.data) {
    return <ErrorState message={project.error ?? "Projet introuvable."} onRetry={project.reload} />;
  }
  const permissions = roles.data?.permissions ?? DEFAULT_PERMISSIONS;
  const role = project.data.role;
  const value: ProjectState = {
    project: project.data,
    permissions,
    can: (action) => can(role, action, permissions),
    reason: (action) => deniedReason(action, permissions),
    reload: project.reload,
  };
  return <ProjectContext.Provider value={value}>{children}</ProjectContext.Provider>;
}

export function useProject(): ProjectState {
  const context = useContext(ProjectContext);
  if (!context) throw new Error("useProject doit être utilisé dans ProjectProvider");
  return context;
}

/** Variante pour les tests et les composants autonomes. */
export const ProjectContextProvider = ProjectContext.Provider;
