import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { DistributionInfo, Problem, ProblemSummary } from "../api/types";
import { DistributionChart, bitstring } from "../components/charts";
import { Empty, ErrorState, GuardedButton, Loading } from "../components/common";
import { useProject } from "../components/ProjectContext";
import { CsvButton, NumberField } from "../components/science";
import { formatDateTime, formatFr, formatPercent } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export const MAX_CSV_BYTES = 1_000_000;

/**
 * Lit des intervalles « min:max » séparés par « ; » (une variable par intervalle).
 * Retourne une erreur en français si la saisie est invalide.
 */
export function parseRanges(text: string): { ranges: [number, number][] } | { error: string } {
  const parts = text.split(";").map((p) => p.trim()).filter(Boolean);
  if (parts.length === 0) return { error: "Indiquez au moins un intervalle « min:max »." };
  const ranges: [number, number][] = [];
  for (const part of parts) {
    const bounds = part.split(":").map((b) => Number(b.trim().replace(",", ".")));
    if (bounds.length !== 2 || bounds.some((b) => !Number.isFinite(b))) return { error: `Intervalle invalide : « ${part} ».` };
    if (!(bounds[1] > bounds[0])) return { error: `Intervalle vide : « ${part} » (max doit dépasser min).` };
    ranges.push([bounds[0], bounds[1]]);
  }
  return { ranges };
}

function ReferenceForm({ projectId, onCreated }: { projectId: number; onCreated: (id: number) => void }) {
  const { can, reason } = useProject();
  const catalog = useAsync(() => api.get<DistributionInfo[]>("/distributions"), []);
  const [name, setName] = useState("");
  const [distribution, setDistribution] = useState("gaussian");
  const [nQubits, setNQubits] = useState(4);
  const [seed, setSeed] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const info = catalog.data?.find((d) => d.name === distribution);
  const qubitsOk = info ? info.qubits.includes(nQubits) : true;

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const reference = { distribution, n_qubits: nQubits, ...(info?.random ? { seed } : {}) };
      const created = await api.post<Problem>(`/projects/${projectId}/problems`, { name, reference });
      setName("");
      onCreated(created.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form className="row" onSubmit={submit} aria-label="Problème depuis une référence">
      {catalog.error && <ErrorState message={catalog.error} onRetry={catalog.reload} />}
      <label style={{ flex: "1 1 200px" }}>
        Nom
        <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Distribution
        <select value={distribution} onChange={(e) => setDistribution(e.target.value)}>
          {(catalog.data ?? []).map((d) => (
            <option key={d.name} value={d.name}>
              {d.label}
            </option>
          ))}
        </select>
      </label>
      <NumberField
        label="Qubits"
        value={nQubits}
        min={2}
        max={8}
        onChange={setNQubits}
        error={qubitsOk ? undefined : `Qubits possibles : ${info?.qubits.join(", ")}.`}
      />
      {info?.random && <NumberField label="Graine" value={seed} min={0} max={1_000_000} onChange={setSeed} />}
      <GuardedButton type="submit" allowed={can("problems")} reason={reason("problems")} disabled={!name.trim() || !qubitsOk}>
        Créer le problème
      </GuardedButton>
      {error && <ErrorState message={error} />}
    </form>
  );
}

function CsvForm({ projectId, onCreated }: { projectId: number; onCreated: (id: number) => void }) {
  const { can, reason } = useProject();
  const [name, setName] = useState("");
  const [format, setFormat] = useState<"probabilities" | "samples">("probabilities");
  const [content, setContent] = useState<string | null>(null);
  const [fileLabel, setFileLabel] = useState("");
  const [nQubits, setNQubits] = useState(4);
  const [rangesText, setRangesText] = useState("0:1");
  const [encoding, setEncoding] = useState<"binary" | "gray">("binary");
  const [error, setError] = useState<string | null>(null);
  const parsed = parseRanges(rangesText);

  async function readFile(file: File | undefined) {
    setError(null);
    setContent(null);
    if (!file) return;
    if (file.size > MAX_CSV_BYTES) {
      setError("Le fichier dépasse 1 Mo.");
      return;
    }
    setContent(await file.text());
    setFileLabel(`${file.name} (${formatFr(file.size / 1024, 1)} Ko)`);
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!content) return;
    setError(null);
    try {
      const body =
        format === "probabilities"
          ? { name, format, content }
          : { name, format, content, n_qubits: nQubits, ranges: "ranges" in parsed ? parsed.ranges : [], encoding };
      const created = await api.post<Problem>(`/projects/${projectId}/problems/csv`, body);
      setName("");
      onCreated(created.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const samplesInvalid = format === "samples" && "error" in parsed;
  return (
    <form onSubmit={submit} aria-label="Problème depuis un fichier CSV">
      <div className="row">
        <label style={{ flex: "1 1 200px" }}>
          Nom
          <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        <label>
          Format
          <select value={format} onChange={(e) => setFormat(e.target.value as "probabilities" | "samples")}>
            <option value="probabilities">Probabilités (bitstring,probabilite)</option>
            <option value="samples">Échantillons bruts (une colonne par variable)</option>
          </select>
        </label>
        <label>
          Fichier CSV (1 Mo et 100 000 lignes au plus)
          <input type="file" accept=".csv,text/csv" onChange={(e) => readFile(e.target.files?.[0])} />
        </label>
      </div>
      {format === "samples" && (
        <div className="row" style={{ marginTop: 12 }}>
          <NumberField label="Qubits" value={nQubits} min={2} max={8} onChange={setNQubits} />
          <label style={{ flex: "1 1 220px" }}>
            Intervalles min:max, séparés par « ; »
            <input value={rangesText} onChange={(e) => setRangesText(e.target.value)} aria-invalid={"error" in parsed} />
            {"error" in parsed && <span className="field-error">{parsed.error}</span>}
          </label>
          <label>
            Encodage
            <select value={encoding} onChange={(e) => setEncoding(e.target.value as "binary" | "gray")}>
              <option value="binary">Binaire</option>
              <option value="gray">Code de Gray</option>
            </select>
          </label>
        </div>
      )}
      <p className="muted">
        {format === "probabilities"
          ? "Une ligne par état : chaîne de bits (qubit n-1 à gauche), probabilité avec un point décimal. La somme doit valoir 1 à 1e-6 près."
          : "Chaque variable reçoit n/d qubits ; le nombre de qubits doit être divisible par le nombre de variables. Un échantillon hors intervalle est refusé."}
        {fileLabel && ` Fichier : ${fileLabel}.`}
      </p>
      <GuardedButton type="submit" allowed={can("problems")} reason={reason("problems")} disabled={!name.trim() || !content || samplesInvalid}>
        Importer le CSV
      </GuardedButton>
      {error && <ErrorState message={error} />}
    </form>
  );
}

function ProblemDetail({ projectId, problemId, onDeleted }: { projectId: number; problemId: number; onDeleted: () => void }) {
  const { can, reason } = useProject();
  const problem = useAsync(() => api.get<Problem>(`/projects/${projectId}/problems/${problemId}`), [projectId, problemId]);
  const [error, setError] = useState<string | null>(null);
  if (problem.loading) return <Loading label="Chargement du problème" />;
  if (problem.error || !problem.data) return <ErrorState message={problem.error ?? "Problème introuvable."} onRetry={problem.reload} />;
  const p = problem.data;
  const f = p.features;

  async function remove() {
    try {
      await api.delete(`/projects/${projectId}/problems/${problemId}`);
      onDeleted();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="card" aria-labelledby="detail-probleme">
      <h2 id="detail-probleme">{p.name}</h2>
      <DistributionChart probabilities={p.probabilities} />
      <div className="table-wrap">
        <table>
          <tbody>
            <tr><th scope="row">Qubits</th><td className="num">{f.n_qubits}</td></tr>
            <tr><th scope="row">Entropie normalisée</th><td className="num">{formatFr(f.entropy, 4)}</td></tr>
            <tr><th scope="row">Part du support non nul</th><td className="num">{formatPercent(f.support_fraction)}</td></tr>
            <tr><th scope="row">Probabilité maximale</th><td className="num">{formatFr(f.max_probability, 4)}</td></tr>
            <tr><th scope="row">Information mutuelle moyenne entre bits</th><td className="num">{formatFr(f.mean_mutual_information, 4)} bit</td></tr>
          </tbody>
        </table>
      </div>
      <div className="row" style={{ marginTop: 16 }}>
        <CsvButton
          filename={`probleme-${p.id}.csv`}
          rows={p.probabilities.map((probability, i) => ({ bitstring: bitstring(i, p.n_qubits), probability }))}
          params={{ probleme: p.name, qubits: p.n_qubits, origine: p.origin }}
        />
        <GuardedButton className="secondary" allowed={can("problems")} reason={reason("problems")} onClick={remove}>
          Supprimer
        </GuardedButton>
      </div>
      {error && <ErrorState message={error} />}
    </section>
  );
}

export function ProblemsPage() {
  const { project } = useProject();
  const problems = useAsync(() => api.get<ProblemSummary[]>(`/projects/${project.id}/problems`), [project.id]);
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<"reference" | "csv">("reference");
  const selected = params.get("problem") ? Number(params.get("problem")) : null;

  const select = (id: number | null) => setParams(id === null ? {} : { problem: String(id) });
  const created = (id: number) => {
    problems.reload();
    select(id);
  };

  return (
    <>
      <h1>Problèmes</h1>
      <p className="muted">Un problème est la distribution de probabilité que le client veut apprendre, sur 2 à 8 qubits.</p>
      <section className="card" aria-labelledby="nouveau-probleme">
        <h2 id="nouveau-probleme">Nouveau problème</h2>
        <div className="tabs" role="tablist" aria-label="Origine du problème">
          <button type="button" role="tab" aria-selected={tab === "reference"} onClick={() => setTab("reference")}>
            Distribution de référence
          </button>
          <button type="button" role="tab" aria-selected={tab === "csv"} onClick={() => setTab("csv")}>
            Fichier CSV
          </button>
        </div>
        <div role="tabpanel">
          {tab === "reference" ? <ReferenceForm projectId={project.id} onCreated={created} /> : <CsvForm projectId={project.id} onCreated={created} />}
        </div>
      </section>
      <section className="card" aria-labelledby="liste-problemes">
        <h2 id="liste-problemes">Problèmes du projet</h2>
        {problems.loading ? (
          <Loading />
        ) : problems.error ? (
          <ErrorState message={problems.error} onRetry={problems.reload} />
        ) : problems.data!.length === 0 ? (
          <Empty>Aucun problème. Créez-en un depuis une distribution de référence ou un fichier CSV.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Nom</th>
                  <th scope="col">Qubits</th>
                  <th scope="col">Origine</th>
                  <th scope="col">Entropie</th>
                  <th scope="col">Créé le</th>
                </tr>
              </thead>
              <tbody>
                {problems.data!.map((p) => (
                  <tr key={p.id} aria-selected={p.id === selected}>
                    <td>
                      <button type="button" className={p.id === selected ? "" : "secondary"} onClick={() => select(p.id)}>
                        {p.name}
                      </button>
                    </td>
                    <td className="num">{p.n_qubits}</td>
                    <td>{p.origin === "csv" ? "Fichier CSV" : "Référence"}</td>
                    <td className="num">{formatFr(p.features.entropy, 4)}</td>
                    <td className="num">{formatDateTime(p.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {selected !== null && (
        <ProblemDetail
          projectId={project.id}
          problemId={selected}
          onDeleted={() => {
            select(null);
            problems.reload();
          }}
        />
      )}
    </>
  );
}
