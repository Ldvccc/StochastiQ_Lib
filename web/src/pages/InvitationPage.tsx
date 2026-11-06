import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";

import { api } from "../api/client";
import type { InvitationPublic } from "../api/types";
import { useAuth } from "../auth/AuthContext";
import { ErrorState, Loading, Logo } from "../components/common";
import { formatDateTime } from "../lib/format";
import { ROLE_LABELS } from "../lib/roles";
import { useAsync } from "../lib/useAsync";

const STATUS_MESSAGES: Record<string, string> = {
  accepted: "Cette invitation a déjà été acceptée.",
  revoked: "Cette invitation a été révoquée par le propriétaire du projet.",
  expired: "Cette invitation a expiré. Demandez un nouveau lien au propriétaire du projet.",
};

export function InvitationPage() {
  const { token } = useParams();
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const invitation = useAsync(() => api.get<InvitationPublic>(`/invitations/${token}`), [token]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const here = encodeURIComponent(`/invitations/${token}`);

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      const { project_id } = await api.post<{ project_id: number }>(`/invitations/${token}/accept`);
      navigate(`/projects/${project_id}`, { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  let body;
  if (invitation.loading || authLoading) body = <Loading />;
  else if (invitation.error || !invitation.data) body = <ErrorState message={invitation.error ?? "Invitation introuvable."} />;
  else {
    const data = invitation.data;
    body = (
      <>
        <p>
          Vous êtes invité à rejoindre le projet <strong>{data.project_name}</strong> comme{" "}
          <strong>{ROLE_LABELS[data.role].toLowerCase()}</strong>, avec l'adresse <strong>{data.email}</strong>.
        </p>
        <p className="muted">Valable jusqu'au {formatDateTime(data.expires_at)}.</p>
        {error && <ErrorState message={error} />}
        {data.status !== "pending" ? (
          <div className="info">{STATUS_MESSAGES[data.status]}</div>
        ) : !user ? (
          <p>
            <Link className="button" to={`/login?next=${here}`}>
              Se connecter
            </Link>{" "}
            <Link className="button secondary" to={`/register?next=${here}`}>
              Créer un compte
            </Link>
          </p>
        ) : user.email !== data.email ? (
          <div className="alert" role="alert">
            Vous êtes connecté avec {user.email}. Connectez-vous avec {data.email} pour accepter cette invitation.
          </div>
        ) : (
          <button type="button" onClick={accept} disabled={busy}>
            {busy ? "Acceptation…" : "Accepter l'invitation"}
          </button>
        )}
      </>
    );
  }

  return (
    <div className="auth-page">
      <div className="card">
        <Logo />
        <h1>Invitation</h1>
        {body}
      </div>
    </div>
  );
}
