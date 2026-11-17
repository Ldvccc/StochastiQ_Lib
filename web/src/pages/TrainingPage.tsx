import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { ProblemSummary } from "../api/types";
import { bitstring, DistributionChart, LossChart } from "../components/charts";
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
  type NoiseChoice,
} from "../components/science";
import { formatFr, formatMetric } from "../lib/format";
import {
  BASELINE_LABELS,
  LOSS_LABELS,
  NOISE_TOPOLOGY_LABELS,
  noiseEvaluationSentence,
  OPTIMIZER_LABELS,
  profileLabel,
  refLabel,
  trainingSentence,
  type NoiseTopology,
  type TrainingResult,
} from "../lib/reading";
import { boundErrors, launchRun, useRunPolling } from "../lib/runs";
import { useAsync } from "../lib/useAsync";

export interface TrainingForm {
  problem: number | null;
  ansatz: string; // valeur d'option : "cat:<nom>" ou "custom:<id>"
  layers: number;
  loss: "kl" | "mmd" | "tvd";
  optimizer: "adam" | "spsa" | "cobyla";
  max_iter: number;
  learning_rate: number;
  exact: boolean;
  shots: number;
  seed: number;
  noise: NoiseChoice; // évaluation finale sous bruit (facultative)
  noiseTopology: NoiseTopology;
}

/** Erreurs du formulaire d'entraînement (mêmes bornes que l'API). */
export function trainingErrors(form: TrainingForm, problemQubits: number | null, fixedQubits: number | null): Record<string, string> {
  const errors = boundErrors({ layers: form.layers, seed: form.seed });
  if (form.problem === null) errors.problem = "Choisissez un problème (écran Problèmes).";
  if (!Number.isInteger(form.max_iter) || form.max_iter < 10 || form.max_iter > 1000) errors.max_iter = "Itérations : entier de 10 à 1000.";
  if (!(form.learning_rate > 0 && form.learning_rate <= 5)) errors.learning_rate = "Pas d'apprentissage : nombre strictement positif, 5 au plus.";
  if (!form.exact && (!Number.isInteger(form.shots) || form.shots < 100 || form.shots > 100_000)) errors.shots = "Tirages : entier de 100 à 100 000.";
  if (form.loss === "tvd" && form.optimizer === "adam") errors.optimizer = "La TVD n'est pas dérivable : choisissez SPSA ou COBYLA.";
  if (problemQubits !== null && fixedQubits !== null && problemQubits !== fixedQubits) {
    errors.ansatz = `Cet ansatz fixe ${fixedQubits} qubits, le problème en a ${problemQubits}.`;
  }
  return { ...errors, ...noiseErrors(form.noise) };
}

function ResultTable({ result }: { result: TrainingResult }) {
  const rows = [
    { label: "Ansatz entraîné", metrics: result.metrics, params: result.n_parameters },
    ...(result.noise
      ? [{ label: `Ansatz entraîné, sous bruit ${profileLabel(result.noise.profile)}`, metrics: result.noise.metrics, params: result.n_parameters }]
      : []),
    ...Object.entries(result.baselines).map(([name, b]) => ({ label: `Référence : ${BASELINE_LABELS[name]}`, metrics: b.metrics, params: b.n_parameters })),
  ];
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Modèle</th>
            <th scope="col">KL</th>
            <th scope="col">TVD</th>
            <th scope="col">Hellinger</th>
            <th scope="col">Paramètres</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label}>
              <th scope="row">{row.label}</th>
              <td className="num">{formatMetric(row.metrics.kl)}</td>
              <td className="num">{formatMetric(row.metrics.tvd)}</td>
              <td className="num">{formatMetric(row.metrics.hellinger)}</td>
              <td className="num">{row.params}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function TrainingPage() {
  const { project, can, reason } = useProject();
  const problems = useAsync(() => api.get<ProblemSummary[]>(`/projects/${project.id}/problems`), [project.id]);
  const options = useAnsatzOptions(project.id);
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const { run, error: pollError } = useRunPolling<TrainingResult>(project.id, runId);
  const [form, setForm] = useState<TrainingForm>({
    problem: null,
    ansatz: "cat:hardware_efficient",
    layers: 2,
    loss: "kl",
    optimizer: "adam",
    max_iter: 200,
    learning_rate: 0.1,
    exact: true,
    shots: 1000,
    seed: 0,
    noise: NO_NOISE_CHOICE,
    noiseTopology: "line",
  });
  const [error, setError] = useState<string | null>(null);

  const problem = problems.data?.find((p) => p.id === form.problem) ?? null;
  const option = options.data?.find((o) => o.value === form.ansatz) ?? null;
  const errors = trainingErrors(form, problem?.n_qubits ?? null, option?.fixedQubits ?? null);
  const invalid = Object.keys(errors).length > 0 || !option;
  const set = (key: keyof TrainingForm) => (value: number) => setForm({ ...form, [key]: value });

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (invalid || !option) return;
    setError(null);
    try {
      const created = await launchRun(project.id, "training", {
        problem_id: form.problem,
        ansatz: option.ref,
        layers: form.layers,
        loss: form.loss,
        optimizer: form.optimizer,
        max_iter: form.max_iter,
        learning_rate: form.learning_rate,
        shots: form.exact ? null : form.shots,
        seed: form.seed,
        evaluate_noise: form.noise.mode === "none" ? null : { profile: noiseProfileValue(form.noise), topology: form.noiseTopology },
      });
      setParams({ run: String(created.id) });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const result = run?.status === "done" ? run.result : null;
  const runParams = run?.params as Record<string, unknown> | undefined;
  const target = (runParams?.target as number[] | undefined) ?? [];
  const nQubits = Number(runParams?.n_qubits ?? 0);

  return (
    <>
      <h1>Entraînement</h1>
      <p className="muted">Entraîne un ansatz à reproduire la distribution d'un problème, en simulation, et le compare à deux références classiques simples.</p>
      <form className="card" onSubmit={submit} aria-label="Paramètres de l'entraînement">
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
          <label style={{ flex: "1 1 220px" }}>
            Ansatz
            <select value={form.ansatz} onChange={(e) => setForm({ ...form, ansatz: e.target.value })} aria-invalid={Boolean(errors.ansatz)}>
              {(options.data ?? []).map((o) => (
                <option key={o.value} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
            {errors.ansatz && <span className="field-error">{errors.ansatz}</span>}
          </label>
          <NumberField label="Couches" value={form.layers} min={1} max={8} onChange={set("layers")} error={errors.layers} />
        </div>
        <div className="row" style={{ marginTop: 12 }}>
          <label>
            Perte
            <select value={form.loss} onChange={(e) => setForm({ ...form, loss: e.target.value as TrainingForm["loss"] })}>
              <option value="kl">KL (gradient exact)</option>
              <option value="mmd">MMD, noyau gaussien (gradient exact)</option>
              <option value="tvd">TVD (non dérivable)</option>
            </select>
          </label>
          <label>
            Optimiseur
            <select value={form.optimizer} onChange={(e) => setForm({ ...form, optimizer: e.target.value as TrainingForm["optimizer"] })} aria-invalid={Boolean(errors.optimizer)}>
              <option value="adam" disabled={form.loss === "tvd"}>Adam</option>
              <option value="spsa">SPSA</option>
              <option value="cobyla">COBYLA</option>
            </select>
            {errors.optimizer && <span className="field-error">{errors.optimizer}</span>}
          </label>
          <NumberField label="Itérations" value={form.max_iter} min={10} max={1000} onChange={set("max_iter")} error={errors.max_iter} />
          <label style={{ minWidth: 120 }}>
            Pas d'apprentissage
            <input type="number" step="0.01" min={0.01} max={5} value={form.learning_rate} onChange={(e) => setForm({ ...form, learning_rate: Number(e.target.value) })} aria-invalid={Boolean(errors.learning_rate)} />
            {errors.learning_rate && <span className="field-error">{errors.learning_rate}</span>}
          </label>
          <label style={{ flexDirection: "row", alignItems: "center", minHeight: 44 }}>
            <input type="checkbox" checked={form.exact} onChange={(e) => setForm({ ...form, exact: e.target.checked })} style={{ minHeight: 0, width: 20, height: 20 }} />
            Probabilités exactes
          </label>
          <NumberField label="Tirages" value={form.shots} min={100} max={100000} onChange={set("shots")} disabled={form.exact} error={errors.shots} note={form.exact ? "Sans objet en mode exact." : undefined} />
          <NumberField label="Graine" value={form.seed} min={0} max={1_000_000} onChange={set("seed")} error={errors.seed} />
        </div>
        <fieldset className="row" style={{ marginTop: 12, border: 0, padding: 0 }}>
          <legend className="muted" style={{ marginBottom: 4 }}>Évaluation finale sous bruit (facultative, mêmes paramètres appris)</legend>
          <NoiseProfileField label="Bruit" choice={form.noise} onChange={(noise) => setForm({ ...form, noise })} errors={errors} />
          <label>
            Topologie
            <select value={form.noiseTopology} disabled={form.noise.mode === "none"} onChange={(e) => setForm({ ...form, noiseTopology: e.target.value as NoiseTopology })}>
              {Object.entries(NOISE_TOPOLOGY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label[0].toUpperCase() + label.slice(1)}
                </option>
              ))}
            </select>
          </label>
        </fieldset>
        <div style={{ marginTop: 16 }}>
          <GuardedButton type="submit" allowed={can("run")} reason={reason("run")} disabled={invalid}>
            Lancer l'entraînement
          </GuardedButton>
        </div>
        {error && <ErrorState message={error} />}
      </form>
      <RunStatusBanner run={run} error={pollError} />
      {result && runParams && (
        <>
          <p className="muted">
            Run n° {run!.id} : {refLabel(runParams.ansatz)}, {String(runParams.layers)} couche(s), problème « {String(runParams.problem_name)} » ({nQubits} qubits),
            perte {LOSS_LABELS[String(runParams.loss)]}, {OPTIMIZER_LABELS[String(runParams.optimizer)]}, pas {formatFr(Number(runParams.learning_rate), 2)}, graine {String(runParams.seed)}.
          </p>
          <section className="card" aria-labelledby="comparaison-classique">
            <h2 id="comparaison-classique">Quantique contre classique</h2>
            <ResultTable result={result} />
            <p>{trainingSentence(result, (runParams.shots as number | null) ?? null)}</p>
            {result.noise && <p>{noiseEvaluationSentence(result)}</p>}
          </section>
          <section className="card" aria-labelledby="courbe-perte">
            <h2 id="courbe-perte">Courbe de perte</h2>
            <LossChart history={result.history} />
            <CsvButton filename={`entrainement-${run!.id}-perte.csv`} rows={result.history.map((loss, i) => ({ iteration: i + 1, loss }))} params={{ ...runParams, target: undefined }} />
          </section>
          <section className="card" aria-labelledby="distribution-apprise">
            <h2 id="distribution-apprise">Distribution apprise contre distribution cible</h2>
            <DistributionChart probabilities={target} compare={{ label: "Apprise", values: result.probabilities }} />
            <CsvButton
              filename={`entrainement-${run!.id}-distributions.csv`}
              rows={target.map((t, i) => ({
                bitstring: bitstring(i, nQubits),
                target: t,
                learned: result.probabilities[i],
                independent: result.baselines.independent.probabilities[i],
                chow_liu: result.baselines.chow_liu.probabilities[i],
                ...(result.noise ? { learned_noisy: result.noise.probabilities[i] } : {}),
              }))}
              params={{ ...runParams, target: undefined }}
            />
          </section>
          <CommentsPanel runId={run!.id} />
        </>
      )}
    </>
  );
}
