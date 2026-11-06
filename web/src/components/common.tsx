import { useId, type ButtonHTMLAttributes, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { RunStatus } from "../api/types";

export function Logo({ to = "/projects" }: { to?: string }) {
  return (
    <Link to={to} className="logo" aria-label="StochastiQ, accueil">
      Stochasti<span>Q</span>
    </Link>
  );
}

export function Loading({ label = "Chargement" }: { label?: string }) {
  return (
    <div className="state" role="status" aria-live="polite">
      {label}…
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="alert" role="alert">
      <p style={{ margin: "0 0 8px" }}>{message}</p>
      {onRetry && (
        <button type="button" className="secondary" onClick={onRetry}>
          Réessayer
        </button>
      )}
    </div>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="state">{children}</div>;
}

const STATUS_LABELS: Record<RunStatus, string> = {
  pending: "En attente",
  running: "En cours",
  done: "Terminé",
  failed: "Échec",
};

export function StatusPill({ status }: { status: RunStatus }) {
  return <span className={`pill ${status}`}>{STATUS_LABELS[status]}</span>;
}

interface GuardedButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  allowed: boolean;
  reason: string;
}

/**
 * Bouton désactivé (jamais masqué) quand le rôle ne permet pas l'action,
 * avec la raison en infobulle et pour les lecteurs d'écran.
 */
export function GuardedButton({ allowed, reason, disabled, children, ...props }: GuardedButtonProps) {
  const id = useId();
  if (allowed) {
    return (
      <button type="button" disabled={disabled} {...props}>
        {children}
      </button>
    );
  }
  return (
    <span title={reason} style={{ display: "inline-flex" }}>
      <button type="button" {...props} disabled aria-describedby={id}>
        {children}
      </button>
      <span id={id} hidden>
        {reason}
      </span>
    </span>
  );
}
