import type { Permission, Role } from "../api/types";

export const ROLES: Role[] = ["viewer", "editor", "key_manager", "owner"];

export const ROLE_LABELS: Record<Role, string> = {
  viewer: "Lecteur",
  editor: "Éditeur",
  key_manager: "Gestionnaire des machines",
  owner: "Propriétaire",
};

// Copie de la matrice de l'API (GET /roles), utilisée tant qu'elle n'est pas chargée.
export const DEFAULT_PERMISSIONS: Permission[] = [
  { action: "read", label: "Lire le projet, les runs, les rapports et les membres", min_role: "viewer" },
  { action: "comment", label: "Commenter les runs", min_role: "viewer" },
  { action: "run", label: "Lancer des runs", min_role: "editor" },
  { action: "pin", label: "Épingler et désépingler des circuits", min_role: "editor" },
  { action: "problems", label: "Créer, renommer et supprimer des problèmes", min_role: "editor" },
  { action: "machines", label: "Gérer les machines (fournisseur et libellé, sans clé)", min_role: "key_manager" },
  { action: "edit_project", label: "Modifier le nom et la description du projet", min_role: "owner" },
  { action: "invite", label: "Inviter des membres et révoquer des invitations", min_role: "owner" },
  { action: "manage_members", label: "Changer les rôles et les titres, retirer des membres", min_role: "owner" },
  { action: "delete_project", label: "Supprimer le projet", min_role: "owner" },
];

export function hasRole(role: Role, minRole: Role): boolean {
  return ROLES.indexOf(role) >= ROLES.indexOf(minRole);
}

export function minRoleFor(action: string, permissions: Permission[] = DEFAULT_PERMISSIONS): Role {
  const permission = permissions.find((p) => p.action === action);
  if (!permission) throw new Error(`Action inconnue : ${action}`);
  return permission.min_role;
}

export function can(role: Role, action: string, permissions: Permission[] = DEFAULT_PERMISSIONS): boolean {
  return hasRole(role, minRoleFor(action, permissions));
}

/** Infobulle expliquant pourquoi une action est désactivée. */
export function deniedReason(action: string, permissions: Permission[] = DEFAULT_PERMISSIONS): string {
  return `Réservé au rôle « ${ROLE_LABELS[minRoleFor(action, permissions)]} » ou supérieur.`;
}
