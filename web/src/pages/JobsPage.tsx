import { useState, type FormEvent } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { Machine, Page, Run, RunKind, RunStatus, RunSummary } from "../api/types";
import { Empty, ErrorState, GuardedButton, Loading, StatusPill } from "../components/common";
import { useProject } from "../components/ProjectContext";
import { CommentsPanel, CsvButton, NumberField, RunStatusBanner, useAnsatzOptions, useTopologies } from "../components/science";
import { formatDateTime, formatFactor } from "../lib/format";
import { ansatzLabel, NOISE_TOPOLOGY_LABELS, profileLabel, refLabel, type NoiseProfile, type NoiseRates, type NoiseTopology } from "../lib/reading";
import { boundErrors, launchRun, useRunPolling } from "../lib/runs";
import { useAsync } from "../lib/useAsync";
import { KIND_LABELS } from "./ProjectPage";

const STATUSES: { value: RunStatus; label: string }[] = [
  { value: "pending", label: "En attente" },
  { value: "running", label: "En cours" },
  { value: "done", label: "Terminé" },
  { value: "failed", label: "Échec" },
];

function RunsList({ projectId }: { projectId: number }) {
  const [status, setStatus] = useState<RunStatus | "">("");
  const [kind, setKind] = useState<RunKind | "">("");
  const [limit, setLimit] = useState(20);
  const query = new URLSearchParams({ limit: String(limit) });
  if (status) query.set("status", status);
  if (kind) query.set("kind", kind);
  const runs = useAsync(() => api.get<Page<RunSummary>>(`/projects/${projectId}/runs?${query}`), [projectId, status, kind, limit]);
  return (
    <>
      <div className="row" style={{ marginBottom: 16 }}>
        <label>
          État
          <select value={status} onChange={(e) => setStatus(e.target.value as RunStatus | "")}>
            <option value="">Tous</option>
            {STATUSES.map((s) => (
              <option key={s.value} value={s.value}>
                {s.label}
              </option>
            ))}
          </select>
        </label>
        <label>
          Type
          <select value={kind} onChange={(e) => setKind(e.target.value as RunKind | "")}>
            <option value="">Tous</option>
            {Object.entries(KIND_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className="secondary" onClick={runs.reload}>
          Actualiser
        </button>
      </div>
      {runs.loading && !runs.data ? (
        <Loading />
      ) : runs.error ? (
        <ErrorState message={runs.error} onRetry={runs.reload} />
      ) : runs.data!.items.length === 0 ? (
        <Empty>Aucun run ne correspond à ces filtres.</Empty>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">N°</th>
                <th scope="col">Type</th>
                <th scope="col">État</th>
                <th scope="col">Lancé le</th>
                <th scope="col">Terminé le</th>
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
                  <td className="num">{run.finished_at ? formatDateTime(run.finished_at) : "n/a"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {runs.data!.total > runs.data!.items.length && (
            <button type="button" className="secondary" onClick={() => setLimit(limit + 20)}>
              Afficher plus
            </button>
          )}
        </div>
      )}
    </>
  );
}

interface HardwareResult {
  topology: string;
  before: { n_two_qubit_gates: number; depth: number };
  basis_only: { n_two_qubit_gates: number; depth: number };
  after: { n_two_qubit_gates: number; depth: number };
  routing_overhead_two_qubit: number;
}

export function hardwareRows(result: HardwareResult) {
  return [
    { level: "Circuit d'origine", key: "before", ...result.before },
    { level: "Après traduction", key: "basis_only", ...result.basis_only },
    { level: "Après routage", key: "after", ...result.after },
  ];
}

function HardwareTab({ projectId }: { projectId: number }) {
  const { can, reason } = useProject();
  const catalog = useAnsatzOptions(projectId);
  const topologies = useTopologies();
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const { run, error: pollError } = useRunPolling<HardwareResult>(projectId, runId);
  const [form, setForm] = useState({ ansatz: "cat:data_reuploading", n_qubits: 4, layers: 3, topology: "line", seed: 0 });
  const [error, setError] = useState<string | null>(null);
  const errors = boundErrors({ n_qubits: form.n_qubits, layers: form.layers, seed: form.seed });
  const fixed = catalog.data?.find((o) => o.value === form.ansatz)?.fixedQubits ?? null;
  if (!errors.n_qubits && fixed !== null && form.n_qubits !== fixed) errors.n_qubits = `Cet ansatz fixe ${fixed} qubits.`;
  const invalid = Object.keys(errors).length > 0;
  const topologyLabel = (name: string) => topologies.data?.find((t) => t.name === name)?.label ?? name;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (invalid) return;
    setError(null);
    try {
      const option = catalog.data?.find((o) => o.value === form.ansatz);
      if (!option) return;
      const created = await launchRun(projectId, "hardware", { ...form, ansatz: option.ref });
      setParams({ tab: "materiel", run: String(created.id) });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const result = run?.status === "done" && run.kind === "hardware" ? run.result : null;
  return (
    <>
      <form onSubmit={submit} aria-label="Paramètres du coût matériel">
        <div className="row">
          <label>
            Ansatz
            <select value={form.ansatz} onChange={(e) => setForm({ ...form, ansatz: e.target.value })}>
              {(catalog.data ?? []).map((a) => (
                <option key={a.value} value={a.value}>
                  {a.label}
                </option>
              ))}
            </select>
          </label>
          <NumberField label="Qubits" value={form.n_qubits} min={2} max={8} onChange={(v) => setForm({ ...form, n_qubits: v })} error={errors.n_qubits} />
          <NumberField label="Couches" value={form.layers} min={1} max={8} onChange={(v) => setForm({ ...form, layers: v })} error={errors.layers} />
          <label>
            Topologie
            <select value={form.topology} onChange={(e) => setForm({ ...form, topology: e.target.value })}>
              {(topologies.data ?? []).map((t) => (
                <option key={t.name} value={t.name}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
          <NumberField label="Graine du transpileur" value={form.seed} min={0} max={1_000_000} onChange={(v) => setForm({ ...form, seed: v })} error={errors.seed} />
          <GuardedButton type="submit" allowed={can("run")} reason={reason("run")} disabled={invalid}>
            Calculer le coût
          </GuardedButton>
        </div>
        {error && <ErrorState message={error} />}
      </form>
      <p className="muted">Transpilation hors ligne avec Qiskit, vers les portes cx, rz, sx et x : aucune connexion à une vraie machine.</p>
      <RunStatusBanner run={run} error={pollError} />
      {result && (
        <>
          <div className="table-wrap">
            <table>
              <caption style={{ textAlign: "left", fontWeight: 600, padding: "8px 0" }}>Topologie : {topologyLabel(result.topology)}</caption>
              <thead>
                <tr>
                  <th scope="col">Niveau</th>
                  <th scope="col">Portes à 2 qubits</th>
                  <th scope="col">Profondeur</th>
                </tr>
              </thead>
              <tbody>
                {hardwareRows(result).map((row) => (
                  <tr key={row.key}>
                    <th scope="row">{row.level}</th>
                    <td className="num">{row.n_two_qubit_gates}</td>
                    <td className="num">{row.depth}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>
            Surcoût du routage : <span className="num">{formatFactor(result.routing_overhead_two_qubit)}</span> (portes à 2 qubits après routage, rapportées à la
            traduction seule).
          </p>
          <CsvButton
            filename={`materiel-${run!.id}.csv`}
            rows={hardwareRows(result).map(({ key, n_two_qubit_gates, depth }) => ({ level: key, n_two_qubit_gates, depth }))}
            params={{ ...run!.params }}
          />
        </>
      )}
    </>
  );
}

function MachinesSection({ projectId }: { projectId: number }) {
  const { can, reason } = useProject();
  const allowed = can("machines");
  const machines = useAsync(() => (allowed ? api.get<Machine[]>(`/projects/${projectId}/machines`) : Promise.resolve([])), [projectId, allowed]);
  const [form, setForm] = useState({ provider: "", label: "" });
  const [error, setError] = useState<string | null>(null);

  async function add(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await api.post(`/projects/${projectId}/machines`, form);
      setForm({ provider: "", label: "" });
      machines.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function remove(id: number) {
    try {
      await api.delete(`/projects/${projectId}/machines/${id}`);
      machines.reload();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="card" aria-labelledby="machines">
      <h2 id="machines">Machines</h2>
      <div className="info">Aucune clé n'est stockée dans ce prototype : une entrée ne contient qu'un fournisseur et un libellé, et aucun calcul n'est envoyé à une vraie machine.</div>
      <ul className="activity">
        <li>
          <span>Simulateur local (vecteur d'état, sans bruit)</span>
          <span className="pill done">Disponible</span>
        </li>
        {allowed && machines.data?.map((m) => (
          <li key={m.id}>
            <span>
              {m.provider} · {m.label}
            </span>
            <button type="button" className="secondary" onClick={() => remove(m.id)}>
              Retirer
            </button>
          </li>
        ))}
      </ul>
      {!allowed && <p className="muted">{reason("machines")} La liste des machines déclarées est visible à partir de ce rôle.</p>}
      {machines.error && <ErrorState message={machines.error} onRetry={machines.reload} />}
      <form className="row" onSubmit={add} style={{ marginTop: 12 }}>
        <label>
          Fournisseur
          <input value={form.provider} maxLength={50} disabled={!allowed} onChange={(e) => setForm({ ...form, provider: e.target.value })} />
        </label>
        <label>
          Libellé
          <input value={form.label} maxLength={100} disabled={!allowed} onChange={(e) => setForm({ ...form, label: e.target.value })} />
        </label>
        <GuardedButton type="submit" allowed={allowed} reason={reason("machines")} disabled={!form.provider.trim() || !form.label.trim()}>
          Ajouter
        </GuardedButton>
      </form>
      {error && <ErrorState message={error} />}
    </section>
  );
}

export function JobsPage() {
  const { project } = useProject();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "materiel" ? "materiel" : "runs";
  return (
    <>
      <h1>Jobs et matériel</h1>
      <div className="card">
        <div className="tabs" role="tablist" aria-label="Sections">
          <button type="button" role="tab" aria-selected={tab === "runs"} onClick={() => setParams({})}>
            Runs
          </button>
          <button type="button" role="tab" aria-selected={tab === "materiel"} onClick={() => setParams({ tab: "materiel" })}>
            Matériel
          </button>
        </div>
        <div role="tabpanel">{tab === "runs" ? <RunsList projectId={project.id} /> : <HardwareTab projectId={project.id} />}</div>
      </div>
      {tab === "materiel" && <MachinesSection projectId={project.id} />}
    </>
  );
}

const PARAM_LABELS: Record<string, string> = {
  ansatz: "Ansatz",
  n_qubits: "Qubits",
  layers: "Couches",
  n_samples: "Échantillons",
  n_seeds: "Nombre de graines",
  seed: "Graine",
  observable: "Observable",
  topology: "Topologie",
  qubit_min: "Qubits min",
  qubit_max: "Qubits max",
  layers_mode: "Mode de couches",
  compare_observables: "Comparer local et global",
  problem_id: "Problème (n°)",
  problem_name: "Problème",
  loss: "Perte",
  optimizer: "Optimiseur",
  max_iter: "Itérations",
  learning_rate: "Pas d'apprentissage",
  shots: "Tirages",
  profile: "Profil de bruit",
  noise_profile: "Bruit",
  evaluate_noise: "Évaluation sous bruit",
  budget: "Budget d'itérations",
  problem_family: "Famille du problème",
};

function paramValue(value: unknown): string {
  if (value === null || value === undefined) return "aucun";
  if (Array.isArray(value)) return value.map(refLabel).join(", ");
  if (typeof value === "object" && "p1" in value) return profileLabel(value as NoiseRates);
  if (typeof value === "object" && "profile" in value) {
    const evaluation = value as { profile: NoiseProfile; topology: NoiseTopology };
    return `${profileLabel(evaluation.profile)}, topologie ${NOISE_TOPOLOGY_LABELS[evaluation.topology]}`;
  }
  if (typeof value === "object" && value !== null) return refLabel(value);
  if (typeof value === "boolean") return value ? "oui" : "non";
  if (typeof value === "string") return ansatzLabel(value);
  return String(value);
}

// Le run « noise » (TVD idéal / bruité) n'a pas d'écran dédié : son résultat s'affiche ici, en JSON.
const SCREENS: Partial<Record<RunKind, string>> = {
  diagnostic: "diagnostic",
  compare: "comparateur",
  scaling: "plateau-sterile",
  hardware: "jobs?tab=materiel&",
  training: "entrainement",
  recommendation: "recommandation",
};

// Paramètres recopiés pour la reproductibilité, trop longs pour être affichés (vecteur cible).
const HIDDEN_PARAMS = new Set(["target", "existing"]);

export function RunDetailPage() {
  const { project } = useProject();
  const { runId } = useParams();
  const { run, error } = useRunPolling<Record<string, unknown>>(project.id, Number(runId));
  if (error) return <ErrorState message={error} />;
  if (!run) return <Loading label="Chargement du run" />;
  const screen = SCREENS[run.kind];
  const resultLink = !screen ? null : screen.endsWith("&") ? `/projects/${project.id}/${screen}run=${run.id}` : `/projects/${project.id}/${screen}?run=${run.id}`;
  return (
    <>
      <h1>
        Run n° {run.id} : {KIND_LABELS[run.kind]}
      </h1>
      <RunStatusBanner run={run as Run<unknown>} error={null} />
      <section className="card" aria-labelledby="parametres">
        <h2 id="parametres">Paramètres</h2>
        <table>
          <tbody>
            {Object.entries(run.params)
              .filter(([key]) => !HIDDEN_PARAMS.has(key))
              .map(([key, value]) => (
              <tr key={key}>
                <th scope="row">{PARAM_LABELS[key] ?? key}</th>
                <td>{paramValue(value)}</td>
              </tr>
            ))}
            <tr>
              <th scope="row">État</th>
              <td>
                <StatusPill status={run.status} />
              </td>
            </tr>
            <tr>
              <th scope="row">Lancé le</th>
              <td className="num">{formatDateTime(run.created_at)}</td>
            </tr>
            <tr>
              <th scope="row">Terminé le</th>
              <td className="num">{run.finished_at ? formatDateTime(run.finished_at) : "n/a"}</td>
            </tr>
          </tbody>
        </table>
        {run.status === "done" && resultLink && (
          <p>
            <Link to={resultLink}>Voir le résultat dans l'écran {KIND_LABELS[run.kind]}</Link>
          </p>
        )}
        {run.status === "failed" && <ErrorState message={run.error ?? "Erreur inconnue."} />}
        {run.result && (
          <details>
            <summary>Résultat brut (JSON)</summary>
            <pre className="num" style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>
              {JSON.stringify(run.result, null, 2)}
            </pre>
          </details>
        )}
      </section>
      <CommentsPanel runId={run.id} />
    </>
  );
}
