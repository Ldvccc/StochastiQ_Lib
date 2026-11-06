import { useState } from "react";

import type { Member, Role } from "../api/types";
import { ROLE_LABELS, ROLES } from "../lib/roles";
import { GuardedButton } from "./common";

interface Props {
  members: Member[];
  currentUserId: number;
  canManage: boolean;
  deniedReason: string;
  onChange: (userId: number, change: { role?: Role; title?: string }) => Promise<void>;
  onRemove: (userId: number) => Promise<void>;
}

function MemberRow({ member, isSelf, canManage, deniedReason, onChange, onRemove }: Omit<Props, "members" | "currentUserId"> & {
  member: Member;
  isSelf: boolean;
}) {
  const [title, setTitle] = useState(member.title);
  const titleId = `titre-${member.user_id}`;
  const roleId = `role-${member.user_id}`;
  return (
    <tr>
      <td>
        {member.name}
        {isSelf && <span className="muted"> (vous)</span>}
        <div className="muted" style={{ fontSize: "0.85rem" }}>
          {member.email}
        </div>
      </td>
      <td>
        <select
          id={roleId}
          aria-label={`Rôle de ${member.name}`}
          value={member.role}
          disabled={!canManage}
          title={canManage ? undefined : deniedReason}
          onChange={(event) => onChange(member.user_id, { role: event.target.value as Role })}
        >
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {ROLE_LABELS[role]}
            </option>
          ))}
        </select>
      </td>
      <td>
        <input
          id={titleId}
          aria-label={`Titre de ${member.name}`}
          value={title}
          maxLength={50}
          placeholder="CEO, CTO..."
          disabled={!canManage}
          title={canManage ? undefined : deniedReason}
          onChange={(event) => setTitle(event.target.value)}
          onBlur={() => title !== member.title && onChange(member.user_id, { title })}
        />
      </td>
      <td>
        <GuardedButton
          className="secondary"
          allowed={canManage}
          reason={deniedReason}
          onClick={() => onRemove(member.user_id)}
        >
          Retirer
        </GuardedButton>
      </td>
    </tr>
  );
}

/** Tableau des membres : rôle et titre modifiables par le propriétaire seulement. */
export function MembersTable({ members, currentUserId, ...rest }: Props) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Membre</th>
            <th scope="col">Rôle</th>
            <th scope="col">Titre (sans effet sur les droits)</th>
            <th scope="col">
              <span className="visually-hidden">Actions</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {members.map((member) => (
            <MemberRow key={member.user_id} member={member} isSelf={member.user_id === currentUserId} {...rest} />
          ))}
        </tbody>
      </table>
    </div>
  );
}
