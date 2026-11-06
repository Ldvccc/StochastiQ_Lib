// Types de l'API, écrits à la main d'après l'OpenAPI (/openapi.json).

export type Role = "viewer" | "editor" | "key_manager" | "owner";

export interface User {
  id: number;
  email: string;
  name: string;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  expires_in: number;
}

export interface Project {
  id: number;
  name: string;
  slug: string;
  description: string;
  created_by: number | null;
  created_at: string;
  role: Role;
}

export interface Member {
  user_id: number;
  email: string;
  name: string;
  role: Role;
  title: string;
  created_at: string;
}

export interface Invitation {
  id: number;
  project_id: number;
  email: string;
  role: Role;
  status: string;
  expires_at: string;
  created_at: string;
  link: string;
}

export interface InvitationPublic {
  project_name: string;
  email: string;
  role: Role;
  status: "pending" | "accepted" | "revoked" | "expired";
  expires_at: string;
}

export interface Permission {
  action: string;
  label: string;
  min_role: Role;
}

export interface RolesInfo {
  roles: { name: Role; label: string }[];
  permissions: Permission[];
}

export interface UserRef {
  id: number;
  name: string;
}

export interface ActivityEvent {
  id: number;
  type: string;
  user: UserRef | null;
  payload: Record<string, unknown>;
  created_at: string;
}

export interface Page<T> {
  items: T[];
  total: number;
}

export type RunKind = "diagnostic" | "compare" | "scaling" | "hardware";
export type RunStatus = "pending" | "running" | "done" | "failed";

export interface RunSummary {
  id: number;
  project_id: number;
  kind: RunKind;
  params: Record<string, unknown>;
  status: RunStatus;
  error: string | null;
  created_by: number | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface Run<R = Record<string, unknown>> extends RunSummary {
  result: R | null;
}

export interface Pin {
  id: number;
  ansatz: string;
  n_qubits: number;
  layers: number;
  pinned_by: number | null;
  created_at: string;
}

export interface Comment {
  id: number;
  run_id: number;
  user: UserRef | null;
  text: string;
  created_at: string;
}

export interface Machine {
  id: number;
  provider: string;
  label: string;
  created_by: number | null;
  created_at: string;
}

export interface AnsatzInfo {
  name: string;
  label: string;
  description: string;
  parameters: string;
}

export interface Topology {
  name: string;
  label: string;
}
