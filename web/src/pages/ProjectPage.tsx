import { useState } from "react";
import { Link } from "react-router-dom";

import { api } from "../api/client";
import type { ActivityEvent, Member, Page, Pin, RunSummary } from "../api/types";
import { ActivityList } from "../components/ActivityList";
import { Empty, ErrorState, GuardedButton, Loading, StatusPill } from "../components/common";
import { useProject } from "../components/ProjectContext";
import { formatDateTime } from "../lib/format";
import { ROLE_LABELS } from "../lib/roles";
import { useAsync } from "../lib/useAsync";

const TABS = ["Activité", "Circuits épinglés", "Runs", "Membres"] as const;
type Tab = (typeof TABS)[number];

export const KIND_LABELS: Record<string, string> = {
  diagnostic: "Diagnostic",
  compare: "Comparaison",
  scaling: "Plateau stérile",
  hardware: "Coût matériel",
  training: "Entraînement",
};

const PAGE_SIZE = 20;

function ActivityTab({ projectId }: { projectId: number }) {
  const [limit, setLimit] = useState(PAGE_SIZE);
  const page = useAsync(() => api.get<Page<ActivityEvent>>(`/projects/${projectId}/activity?limit=${limit}`), [projectId, limit]);
  if (page.loading && !page.data) return <Loading />;
  if (page.error) return <ErrorState message={page.error} onRetry={page.reload} />;
  return (
    <>
      <ActivityList events={page.data!.items} />
      {page.data!.total > page.data!.items.length && (
        <p>
          <button type="button" className="secondary" onClick={() => setLimit(limit + PAGE_SIZE)}>
            Afficher plus
          </button>
        </p>
      )}
    </>
  );
}

function PinsTab({ projectId }: { projectId: number }) {
  const { can, reason } = useProject();
  const pins = useAsync(() => api.get<Pin[]>(`/projects/${projectId}/pins`), [projectId]);
  const [error, setError] = useState<string | null>(null);
  if (pins.loading) return <Loading />;
  if (pins.error) return <ErrorState message={pins.error} onRetry={pins.reload} />;
  if (pins.data!.length === 0) {
    return <Empty>Aucun circuit épinglé. Épinglez un circuit depuis l'écran Diagnostic.</Empty>;
  }
  async function unpin(pin: Pin) {
    try {
      await api.delete(`/projects/${projectId}/pins/${pin.id}`);
      pins.reload();
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
              <th scope="col">Ansatz</th>
              <th scope="col">Qubits</th>
              <th scope="col">Couches</th>
              <th scope="col">Épinglé le</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {pins.data!.map((pin) => (
              <tr key={pin.id}>
                <td>{pin.ansatz}</td>
                <td className="num">{pin.n_qubits}</td>
                <td className="num">{pin.layers}</td>
                <td className="num">{formatDateTime(pin.created_at)}</td>
                <td>
                  <GuardedButton className="secondary" allowed={can("pin")} reason={reason("pin")} onClick={() => unpin(pin)}>
                    Désépingler
                  </GuardedButton>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}

function RunsTab({ projectId }: { projectId: number }) {
  const runs = useAsync(() => api.get<Page<RunSummary>>(`/projects/${projectId}/runs?limit=${PAGE_SIZE}`), [projectId]);
  if (runs.loading) return <Loading />;
  if (runs.error) return <ErrorState message={runs.error} onRetry={runs.reload} />;
  if (runs.data!.items.length === 0) return <Empty>Aucun run. Lancez un diagnostic pour commencer.</Empty>;
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">N°</th>
            <th scope="col">Type</th>
            <th scope="col">État</th>
            <th scope="col">Lancé le</th>
          </tr>
        </thead>
        <tbody>
          {runs.data!.items.map((run) => (
            <tr key={run.id}>
              <td className="num">
                <Link to={`/projects/${projectId}/jobs/${run.id}`}>{run.id}</Link>
              </td>
              <td>{KIND_LABELS[run.kind]}</td>
              <td>
                <StatusPill status={run.status} />
              </td>
              <td className="num">{formatDateTime(run.created_at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {runs.data!.total > runs.data!.items.length && (
        <p>
          <Link to={`/projects/${projectId}/jobs`}>Voir tous les runs ({runs.data!.total})</Link>
        </p>
      )}
    </div>
  );
}

function MembersTab({ projectId }: { projectId: number }) {
  const members = useAsync(() => api.get<Member[]>(`/projects/${projectId}/members`), [projectId]);
  if (members.loading) return <Loading />;
  if (members.error) return <ErrorState message={members.error} onRetry={members.reload} />;
  return (
    <>
      <ul className="activity">
        {members.data!.map((m) => (
          <li key={m.user_id}>
            <span>
              {m.name}
              {m.title && <span className="muted"> · {m.title}</span>}
            </span>
            <span className="pill">{ROLE_LABELS[m.role]}</span>
          </li>
        ))}
      </ul>
      <p>
        <Link to={`/projects/${projectId}/equipe`}>Gérer l'équipe</Link>
      </p>
    </>
  );
}

export function ProjectPage() {
  const { project } = useProject();
  const [tab, setTab] = useState<Tab>("Activité");
  return (
    <>
      <h1>{project.name}</h1>
      <p className="muted">
        {project.description || "Sans description"} · Votre rôle : {ROLE_LABELS[project.role]}
      </p>
      <div className="card">
        <div className="tabs" role="tablist" aria-label="Sections du projet">
          {TABS.map((name) => (
            <button
              key={name}
              type="button"
              role="tab"
              aria-selected={tab === name}
              aria-controls={`panneau-${name}`}
              onClick={() => setTab(name)}
            >
              {name}
            </button>
          ))}
        </div>
        <div role="tabpanel" id={`panneau-${tab}`} aria-label={tab}>
          {tab === "Activité" && <ActivityTab projectId={project.id} />}
          {tab === "Circuits épinglés" && <PinsTab projectId={project.id} />}
          {tab === "Runs" && <RunsTab projectId={project.id} />}
          {tab === "Membres" && <MembersTab projectId={project.id} />}
        </div>
      </div>
    </>
  );
}
