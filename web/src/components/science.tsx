import { useId, useState, type FormEvent, type ReactNode } from "react";

import { api } from "../api/client";
import type { AnsatzInfo, Comment, Run, Topology } from "../api/types";
import { CSV_LABEL, downloadCsv, toCsv } from "../lib/csv";
import { formatDateTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";
import { Empty, ErrorState, GuardedButton, Loading, StatusPill } from "./common";
import { useProject } from "./ProjectContext";

export function useAnsatzCatalog() {
  return useAsync(() => api.get<AnsatzInfo[]>("/ansatz"), []);
}

export function useTopologies() {
  return useAsync(() => api.get<Topology[]>("/topologies"), []);
}

/** Carte d'une métrique, avec une explication accessible (infobulle et lecteur d'écran). */
export function MetricCard({ label, value, help, detail }: { label: string; value: string; help: string; detail?: ReactNode }) {
  const id = useId();
  return (
    <div className="card" style={{ marginBottom: 0 }}>
      <div className="row" style={{ justifyContent: "space-between", alignItems: "center" }}>
        <span className="muted">{label}</span>
        <span
          className="pill"
          tabIndex={0}
          role="note"
          title={help}
          aria-label={`Explication : ${help}`}
          aria-describedby={id}
          style={{ cursor: "help" }}
        >
          ?
        </span>
      </div>
      <div className="num" style={{ fontSize: "1.8rem", marginTop: 8 }}>
        {value}
      </div>
      {detail && <div className="muted" style={{ fontSize: "0.85rem" }}>{detail}</div>}
      <span id={id} className="visually-hidden">
        {help}
      </span>
    </div>
  );
}

export function CsvButton({ filename, rows, params }: { filename: string; rows: Record<string, unknown>[]; params: Record<string, unknown> }) {
  return (
    <button type="button" className="secondary" disabled={rows.length === 0} onClick={() => downloadCsv(filename, toCsv(rows, params))}>
      {CSV_LABEL}
    </button>
  );
}

/** Bandeau d'état d'un run suivi par sondage. */
export function RunStatusBanner({ run, error }: { run: Run<unknown> | null; error: string | null }) {
  if (error) return <ErrorState message={error} />;
  if (!run) return null;
  if (run.status === "failed") return <ErrorState message={`Le run n° ${run.id} a échoué : ${run.error ?? "erreur inconnue"}`} />;
  if (run.status === "done") return null;
  return (
    <div className="info" role="status" aria-live="polite">
      Run n° {run.id} : <StatusPill status={run.status} /> (actualisation toutes les 2 secondes)
    </div>
  );
}

export function CommentsPanel({ runId }: { runId: number }) {
  const { project, can, reason } = useProject();
  const comments = useAsync(() => api.get<Comment[]>(`/projects/${project.id}/runs/${runId}/comments`), [project.id, runId]);
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post(`/projects/${project.id}/runs/${runId}/comments`, { text });
      setText("");
      comments.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="card" aria-labelledby={`commentaires-${runId}`}>
      <h2 id={`commentaires-${runId}`}>Commentaires</h2>
      {comments.loading ? (
        <Loading />
      ) : comments.error ? (
        <ErrorState message={comments.error} onRetry={comments.reload} />
      ) : comments.data!.length === 0 ? (
        <Empty>Aucun commentaire sur ce run.</Empty>
      ) : (
        <ul className="activity">
          {comments.data!.map((c) => (
            <li key={c.id}>
              <span>
                <strong>{c.user?.name ?? "Ancien membre"}</strong> : {c.text}
              </span>
              <time className="muted num">{formatDateTime(c.created_at)}</time>
            </li>
          ))}
        </ul>
      )}
      <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 8, marginTop: 12 }}>
        <label>
          Nouveau commentaire
          <textarea maxLength={2000} value={text} disabled={!can("comment")} onChange={(e) => setText(e.target.value)} />
        </label>
        <div>
          <GuardedButton type="submit" allowed={can("comment")} reason={reason("comment")} disabled={!text.trim()}>
            Publier
          </GuardedButton>
        </div>
        {error && <ErrorState message={error} />}
      </form>
    </section>
  );
}

export function NumberField({
  label,
  value,
  onChange,
  min,
  max,
  error,
  disabled,
  note,
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
  min: number;
  max: number;
  error?: string;
  disabled?: boolean;
  note?: string;
}) {
  const id = useId();
  return (
    <label style={{ minWidth: 120 }}>
      {label}
      <input
        type="number"
        min={min}
        max={max}
        step={1}
        value={Number.isNaN(value) ? "" : value}
        disabled={disabled}
        aria-invalid={Boolean(error)}
        aria-describedby={error || note ? id : undefined}
        onChange={(e) => onChange(e.target.value === "" ? NaN : Number(e.target.value))}
      />
      {(error || note) && (
        <span id={id} className={error ? "field-error" : "muted"} style={{ fontSize: "0.85rem", fontWeight: 400 }}>
          {error ?? note}
        </span>
      )}
    </label>
  );
}
