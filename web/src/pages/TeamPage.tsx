import { useState, type FormEvent } from "react";

import { api } from "../api/client";
import type { Invitation, Member, Permission, Role } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { Empty, ErrorState, GuardedButton, Loading } from "../components/common";
import { MembersTable } from "../components/MembersTable";
import { useProject } from "../components/ProjectContext";
import { formatDateTime } from "../lib/format";
import { hasRole, ROLE_LABELS, ROLES } from "../lib/roles";
import { useAsync } from "../lib/useAsync";

/** Matrice « ce que chaque rôle permet », lue depuis l'API (GET /roles). */
export function PermissionMatrix({ permissions }: { permissions: Permission[] }) {
  return (
    <div className="table-wrap">
      <table>
        <caption className="visually-hidden">Droits de chaque rôle</caption>
        <thead>
          <tr>
            <th scope="col">Action</th>
            {ROLES.map((role) => (
              <th key={role} scope="col">
                {ROLE_LABELS[role]}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {permissions.map((permission) => (
            <tr key={permission.action}>
              <th scope="row" style={{ fontWeight: 400, color: "var(--ink)" }}>
                {permission.label}
              </th>
              {ROLES.map((role) => (
                <td key={role}>{hasRole(role, permission.min_role) ? "Oui" : "Non"}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function InviteForm({ projectId, onCreated }: { projectId: number; onCreated: () => void }) {
  const { can, reason } = useProject();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<Role>("viewer");
  const [link, setLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const allowed = can("invite");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setCopied(false);
    try {
      const invitation = await api.post<Invitation>(`/projects/${projectId}/invitations`, { email, role });
      setLink(invitation.link);
      setEmail("");
      onCreated();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function copy() {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link);
      setCopied(true);
    } catch {
      setError("Copie impossible : sélectionnez le lien et copiez-le à la main.");
    }
  }

  return (
    <>
      <form className="row" onSubmit={submit}>
        <label style={{ flex: "1 1 240px" }}>
          Adresse e-mail
          <input type="email" required value={email} disabled={!allowed} onChange={(e) => setEmail(e.target.value)} />
        </label>
        <label>
          Rôle
          <select value={role} disabled={!allowed} onChange={(e) => setRole(e.target.value as Role)}>
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {ROLE_LABELS[r]}
              </option>
            ))}
          </select>
        </label>
        <GuardedButton type="submit" allowed={allowed} reason={reason("invite")} disabled={!email}>
          Créer le lien d'invitation
        </GuardedButton>
      </form>
      <p className="muted">Aucun e-mail n'est envoyé : transmettez vous-même le lien à la personne invitée.</p>
      {error && <ErrorState message={error} />}
      {link && (
        <div className="info row" style={{ alignItems: "center" }}>
          <label style={{ flex: "1 1 320px" }}>
            Lien d'invitation (valable 7 jours)
            <input readOnly value={link} onFocus={(e) => e.target.select()} />
          </label>
          <button type="button" className="secondary" onClick={copy}>
            {copied ? "Lien copié" : "Copier le lien"}
          </button>
        </div>
      )}
    </>
  );
}

function PendingInvitations({ projectId, version }: { projectId: number; version: number }) {
  const invitations = useAsync(() => api.get<Invitation[]>(`/projects/${projectId}/invitations`), [projectId, version]);
  const [error, setError] = useState<string | null>(null);
  if (invitations.loading) return <Loading />;
  if (invitations.error) return <ErrorState message={invitations.error} onRetry={invitations.reload} />;
  if (invitations.data!.length === 0) return <Empty>Aucune invitation en attente.</Empty>;
  async function revoke(id: number) {
    try {
      await api.delete(`/projects/${projectId}/invitations/${id}`);
      invitations.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }
  return (
    <>
      {error && <ErrorState message={error} />}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">E-mail</th>
              <th scope="col">Rôle</th>
              <th scope="col">Expire le</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {invitations.data!.map((invitation) => (
              <tr key={invitation.id}>
                <td>{invitation.email}</td>
                <td>{ROLE_LABELS[invitation.role]}</td>
                <td className="num">{formatDateTime(invitation.expires_at)}</td>
                <td>
                  <button type="button" className="secondary" onClick={() => revoke(invitation.id)}>
                    Révoquer
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

export function TeamPage() {
  const { project, permissions, can, reason } = useProject();
  const { user } = useAuth();
  const members = useAsync(() => api.get<Member[]>(`/projects/${project.id}/members`), [project.id]);
  const [error, setError] = useState<string | null>(null);
  const [version, setVersion] = useState(0);

  async function change(userId: number, patch: { role?: Role; title?: string }) {
    setError(null);
    try {
      await api.patch(`/projects/${project.id}/members/${userId}`, patch);
      members.reload();
    } catch (err) {
      setError((err as Error).message);
      members.reload();
    }
  }

  async function remove(userId: number) {
    setError(null);
    try {
      await api.delete(`/projects/${project.id}/members/${userId}`);
      members.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <>
      <h1>Équipe</h1>
      <section className="card" aria-labelledby="membres">
        <h2 id="membres">Membres</h2>
        {error && <ErrorState message={error} />}
        {members.loading ? (
          <Loading />
        ) : members.error ? (
          <ErrorState message={members.error} onRetry={members.reload} />
        ) : (
          <MembersTable
            members={members.data!}
            currentUserId={user!.id}
            canManage={can("manage_members")}
            deniedReason={reason("manage_members")}
            onChange={change}
            onRemove={remove}
          />
        )}
      </section>
      <section className="card" aria-labelledby="inviter">
        <h2 id="inviter">Inviter un membre</h2>
        <InviteForm projectId={project.id} onCreated={() => setVersion((v) => v + 1)} />
      </section>
      <section className="card" aria-labelledby="en-attente">
        <h2 id="en-attente">Invitations en attente</h2>
        {can("invite") ? (
          <PendingInvitations projectId={project.id} version={version} />
        ) : (
          <Empty>{reason("invite")} Les invitations en attente sont visibles par le propriétaire.</Empty>
        )}
      </section>
      <section className="card" aria-labelledby="droits">
        <h2 id="droits">Ce que chaque rôle permet</h2>
        <p className="muted">Le titre (CEO, CTO...) est une simple étiquette, sans effet sur les droits.</p>
        <PermissionMatrix permissions={permissions} />
      </section>
    </>
  );
}
