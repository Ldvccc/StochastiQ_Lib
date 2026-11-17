import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { ProblemSummary } from "../api/types";
import { ErrorState, GuardedButton, Loading } from "../components/common";
import { useProject } from "../components/ProjectContext";
import {
  CommentsPanel,
  CsvButton,
  NO_NOISE_CHOICE,
  NoiseProfileField,
  noiseErrors,
  noiseProfileValue,
  NumberField,
  RunStatusBanner,
  useAnsatzOptions,
  type AnsatzOption,
  type NoiseChoice,
} from "../components/science";
import { formatMetric } from "../lib/format";
import {
  BASELINE_LABELS,
  itemLabel,
  NOISE_TOPOLOGY_LABELS,
  recommendationSentences,
  SOURCE_LABELS,
  type NoiseTopology,
  type RecommendationItem,
  type RecommendationResult,
} from "../lib/reading";
import { boundErrors, launchRun, useRunPolling } from "../lib/runs";
import { useAsync } from "../lib/useAsync";

export interface RecommendationForm {
  problem: number | null;
  ansatz: string[]; // valeurs d'option : "cat:<nom>" ou "custom:<id>"
  layers: number;
  noise: NoiseChoice;
  topology: NoiseTopology;
  budget: number;
}

/** Erreurs du formulaire de recommandation (mêmes bornes que l'API). */
export function recommendationErrors(form: RecommendationForm, problemQubits: number | null, options: AnsatzOption[]): Record<string, string> {
  const errors = { ...boundErrors({ layers: form.layers }), ...noiseErrors(form.noise) };
  if (form.problem === null) errors.problem = "Choisissez un problème (écran Problèmes).";
  if (form.ansatz.length < 2 || form.ansatz.length > 7) errors.ansatz = "Choisissez de 2 à 7 ansatz.";
  const mismatched = options.filter((o) => form.ansatz.includes(o.value) && o.fixedQubits !== null && problemQubits !== null && o.fixedQubits !== problemQubits);
  if (mismatched.length > 0) errors.ansatz = `${mismatched.map((o) => o.label).join(", ")} : nombre de qubits différent de celui du problème (${problemQubits}).`;
  if (!Number.isInteger(form.budget) || form.budget < 200 || form.budget > 7000) errors.budget = "Budget : entier de 200 à 7000 itérations.";
  return errors;
}

/** Intervalle affiché d'un ansatz : bornes, ou motif de leur absence. */
export function intervalText(item: RecommendationItem): string {
  if (item.evidence === "measured") return "mesure, sans intervalle";
  if (item.evidence === "interval" && item.low !== null && item.high !== null) return `[${formatMetric(item.low)} ; ${formatMetric(item.high)}]`;
  const margin = item.margin !== null ? ` Marge retenue : ± ${formatMetric(item.margin)} (deux fois l'erreur moyenne de validation).` : "";
  return `${item.interval_message ?? "Intervalle non affiché."}${margin}`;
}

export function sourceText(item: RecommendationItem): string {
  return item.measured ? `${SOURCE_LABELS[item.source]} (run n° ${item.measured.run_id})` : SOURCE_LABELS[item.source];
}

/** Lignes du classement, pour le tableau et l'export CSV. */
export function rankingRows(result: RecommendationResult) {
  const byKey = new Map(result.items.map((item) => [item.key, item]));
  return result.decision.ranking.map((key, i) => {
    const item = byKey.get(key)!;
    return {
      rank: i + 1,
      ansatz: itemLabel(item),
      value: item.value,
      low: item.low,
      high: item.high,
      source: item.source,
      run_id: item.measured?.run_id ?? null,
      expressibility: item.diagnostic.expressibility,
      entangling_capability: item.diagnostic.entangling_capability,
      gradient_mean_variance: item.diagnostic.gradient_mean_variance,
      n_parameters: item.diagnostic.n_parameters,
      n_two_qubit_gates: item.diagnostic.n_two_qubit_gates,
      item,
    };
  });
}

/** Tableau du classement, partagé par l'écran et par le rapport imprimable. */
export function RankingTable({ result }: { result: RecommendationResult }) {
  const quantity = result.noise_profile ? "TVD sous bruit" : "TVD";
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Rang</th>
            <th scope="col">Ansatz</th>
            <th scope="col">{quantity}</th>
            <th scope="col">Intervalle 10-90 %</th>
            <th scope="col">Source</th>
            <th scope="col">Expressibilité</th>
            <th scope="col">Intrication</th>
            <th scope="col">Variance du gradient</th>
            <th scope="col">Paramètres</th>
            <th scope="col">CNOT</th>
          </tr>
        </thead>
        <tbody>
          {rankingRows(result).map((row) => (
            <tr key={row.item.key}>
              <td className="num">{row.rank}</td>
              <th scope="row">{row.ansatz}</th>
              <td className="num">{formatMetric(row.value)}</td>
              <td>{intervalText(row.item)}</td>
              <td>{sourceText(row.item)}</td>
              <td className="num">{formatMetric(row.expressibility)}</td>
              <td className="num">{formatMetric(row.entangling_capability)}</td>
              <td className="num">{formatMetric(row.gradient_mean_variance)}</td>
              <td className="num">{row.n_parameters}</td>
              <td className="num">{row.n_two_qubit_gates}</td>
            </tr>
          ))}
          {Object.entries(result.classical.baselines).map(([name, b]) => (
            <tr key={name}>
              <td />
              <th scope="row">Référence classique : {BASELINE_LABELS[name]}</th>
              <td className="num">{formatMetric(b.tvd)}</td>
              <td>calcul exact</td>
              <td>Référence classique</td>
              <td colSpan={3} />
              <td className="num">{b.n_parameters}</td>
              <td />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function csvRows(result: RecommendationResult) {
  return rankingRows(result).map(({ item: _item, ...row }) => row);
}

export function RecommendationPage() {
  const { project, can, reason } = useProject();
  const problems = useAsync(() => api.get<ProblemSummary[]>(`/projects/${project.id}/problems`), [project.id]);
  const options = useAnsatzOptions(project.id);
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const { run, error: pollError } = useRunPolling<RecommendationResult>(project.id, runId);
  const [form, setForm] = useState<RecommendationForm>({
    problem: null,
    ansatz: ["cat:hardware_efficient", "cat:strongly_entangling"],
    layers: 2,
    noise: NO_NOISE_CHOICE,
    topology: "line",
    budget: 400,
  });
  const [error, setError] = useState<string | null>(null);

  const problem = problems.data?.find((p) => p.id === form.problem) ?? null;
  const allOptions = options.data ?? [];
  const errors = recommendationErrors(form, problem?.n_qubits ?? null, allOptions);
  const invalid = Object.keys(errors).length > 0;

  function toggle(value: string, checked: boolean) {
    setForm({ ...form, ansatz: checked ? [...form.ansatz, value] : form.ansatz.filter((v) => v !== value) });
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (invalid) return;
    setError(null);
    try {
      const created = await launchRun(project.id, "recommendation", {
        problem_id: form.problem,
        ansatz: form.ansatz.map((value) => allOptions.find((o) => o.value === value)!.ref),
        layers: form.layers,
        noise_profile: noiseProfileValue(form.noise),
        topology: form.topology,
        budget: form.budget,
      });
      setParams({ run: String(created.id) });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const result = run?.status === "done" ? run.result : null;
  const runParams = run?.params as Record<string, unknown> | undefined;

  return (
    <>
      <h1>Recommandation</h1>
      <p className="muted">
        Classe de 2 à 7 ansatz sur un problème : diagnostic, TVD prédite par l'IA (ou mesurée si un entraînement existe déjà dans le projet), et comparaison avec les
        références classiques.
      </p>
      <form className="card" onSubmit={submit} aria-label="Paramètres de la recommandation">
        {problems.loading || options.loading ? <Loading /> : null}
        {problems.error && <ErrorState message={problems.error} onRetry={problems.reload} />}
        {options.error && <ErrorState message={options.error} onRetry={options.reload} />}
        <div className="row">
          <label style={{ flex: "1 1 220px" }}>
            Problème
            <select value={form.problem ?? ""} onChange={(e) => setForm({ ...form, problem: e.target.value ? Number(e.target.value) : null })} aria-invalid={Boolean(errors.problem)}>
              <option value="">Choisir…</option>
              {(problems.data ?? []).map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name} ({p.n_qubits} qubits)
                </option>
              ))}
            </select>
            {errors.problem && <span className="field-error">{errors.problem}</span>}
          </label>
          <NumberField label="Couches" value={form.layers} min={1} max={8} onChange={(layers) => setForm({ ...form, layers })} error={errors.layers} />
          <NumberField label="Budget d'itérations" value={form.budget} min={200} max={7000} onChange={(budget) => setForm({ ...form, budget })} error={errors.budget} note="200 itérations par entraînement conseillé." />
        </div>
        <fieldset style={{ border: 0, padding: 0, marginTop: 12 }} aria-invalid={Boolean(errors.ansatz)}>
          <legend>Ansatz à classer (2 à 7)</legend>
          <div className="row">
            {allOptions.map((o) => (
              <label key={o.value} style={{ flexDirection: "row", alignItems: "center", minHeight: 44 }}>
                <input type="checkbox" checked={form.ansatz.includes(o.value)} onChange={(e) => toggle(o.value, e.target.checked)} style={{ minHeight: 0, width: 20, height: 20 }} />
                {o.label}
              </label>
            ))}
          </div>
          {errors.ansatz && <span className="field-error">{errors.ansatz}</span>}
        </fieldset>
        <div className="row" style={{ marginTop: 12 }}>
          <NoiseProfileField label="Bruit (facultatif)" choice={form.noise} onChange={(noise) => setForm({ ...form, noise })} errors={errors} />
          <label>
            Topologie
            <select value={form.topology} disabled={form.noise.mode === "none"} onChange={(e) => setForm({ ...form, topology: e.target.value as NoiseTopology })}>
              {Object.entries(NOISE_TOPOLOGY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label[0].toUpperCase() + label.slice(1)}
                </option>
              ))}
            </select>
          </label>
        </div>
        <div style={{ marginTop: 16 }}>
          <GuardedButton type="submit" allowed={can("run")} reason={reason("run")} disabled={invalid}>
            Recommander
          </GuardedButton>
        </div>
        {error && <ErrorState message={error} />}
      </form>
      <RunStatusBanner run={run} error={pollError} />
      {result && runParams && (
        <>
          <section className="card" aria-labelledby="verdict">
            <h2 id="verdict">Verdict</h2>
            {recommendationSentences(result).map((sentence) => (
              <p key={sentence}>{sentence}</p>
            ))}
            <p className="muted">
              Problème « {String(runParams.problem_name)} » ({result.n_qubits} qubits), {result.layers} couche(s), budget {result.budget} itérations
              {result.noise_profile ? `, bruit sur topologie ${NOISE_TOPOLOGY_LABELS[result.topology]}` : ", sans bruit"}.
            </p>
            <Link to={`/projects/${project.id}/rapport?run=${run!.id}`}>Ouvrir le rapport imprimable</Link>
          </section>
          <section className="card" aria-labelledby="classement">
            <h2 id="classement">Classement</h2>
            <RankingTable result={result} />
            <CsvButton filename={`recommandation-${run!.id}.csv`} rows={csvRows(result)} params={{ ...runParams, target: undefined, existing: undefined }} />
          </section>
          <CommentsPanel runId={run!.id} />
        </>
      )}
    </>
  );
}
