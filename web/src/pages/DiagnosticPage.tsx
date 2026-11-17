import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import { FidelityHistogram, histogramRows, type Histogram } from "../components/charts";
import { ErrorState, GuardedButton } from "../components/common";
import { useProject } from "../components/ProjectContext";
import {
  CommentsPanel,
  CsvButton,
  MetricCard,
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
import { formatMetric, formatPercent } from "../lib/format";
import { degradationSentence, LOW_SAMPLES_THRESHOLD, LOW_SAMPLES_WARNING, refLabel, type NoiseProfile, type NoiseTvdResult } from "../lib/reading";
import { boundErrors, launchRun, useRunPolling } from "../lib/runs";

export interface DiagnosticForm {
  ansatz: string; // valeur d'option : "cat:<nom>" ou "custom:<id>"
  n_qubits: number;
  layers: number;
  n_samples: number;
  seed: number;
  observable: "Z0" | "Zall";
}

export const OBSERVABLE_LABELS = { Z0: "Locale Z0", Zall: "Globale Z⊗n" } as const;

interface DiagnosticResult {
  expressibility: number;
  entangling_capability: number;
  gradient: {
    mean_variance: number;
    active_mean_variance: number | null;
    inactive_fraction: number;
    n_inactive_parameters: number;
    n_parameters: number;
  };
  histogram: Histogram;
  noise?: NoiseTvdResult | null;
}

export function validateDiagnostic(form: DiagnosticForm): Record<string, string> {
  const { n_qubits, layers, n_samples, seed } = form;
  return boundErrors({ n_qubits, layers, n_samples, seed });
}

export function DiagnosticFormFields({
  form,
  setForm,
  errors,
  ansatzOptions,
}: {
  form: DiagnosticForm;
  setForm: (form: DiagnosticForm) => void;
  errors: Record<string, string>;
  ansatzOptions: { value: string; label: string }[];
}) {
  const set = (key: keyof DiagnosticForm) => (value: number) => setForm({ ...form, [key]: value });
  return (
    <div className="row">
      <label>
        Ansatz
        <select value={form.ansatz} onChange={(e) => setForm({ ...form, ansatz: e.target.value })}>
          {ansatzOptions.map((a) => (
            <option key={a.value} value={a.value}>
              {a.label}
            </option>
          ))}
        </select>
      </label>
      <NumberField label="Qubits" value={form.n_qubits} min={2} max={8} onChange={set("n_qubits")} error={errors.n_qubits} />
      <NumberField label="Couches" value={form.layers} min={1} max={8} onChange={set("layers")} error={errors.layers} />
      <NumberField label="Échantillons" value={form.n_samples} min={50} max={5000} onChange={set("n_samples")} error={errors.n_samples} />
      <NumberField label="Graine" value={form.seed} min={0} max={1_000_000} onChange={set("seed")} error={errors.seed} />
      <label>
        Observable
        <select value={form.observable} onChange={(e) => setForm({ ...form, observable: e.target.value as DiagnosticForm["observable"] })}>
          {Object.entries(OBSERVABLE_LABELS).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}

export function DiagnosticPage() {
  const { project, can, reason } = useProject();
  const catalog = useAnsatzOptions(project.id);
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const { run, error: pollError } = useRunPolling<DiagnosticResult>(project.id, runId);
  const [form, setForm] = useState<DiagnosticForm>({ ansatz: "cat:hardware_efficient", n_qubits: 4, layers: 3, n_samples: 1000, seed: 0, observable: "Z0" });
  const [noise, setNoise] = useState<NoiseChoice>(NO_NOISE_CHOICE);
  const [error, setError] = useState<string | null>(null);
  const [pinMessage, setPinMessage] = useState<string | null>(null);
  const options: AnsatzOption[] = catalog.data ?? [];
  const option = options.find((o) => o.value === form.ansatz);
  const errors = { ...validateDiagnostic(form), ...noiseErrors(noise) };
  if (!errors.n_qubits && option?.fixedQubits && form.n_qubits !== option.fixedQubits) {
    errors.n_qubits = `Cet ansatz fixe ${option.fixedQubits} qubits.`;
  }
  const invalid = Object.keys(errors).length > 0 || !option;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (invalid) return;
    setError(null);
    setPinMessage(null);
    try {
      const created = await launchRun(project.id, "diagnostic", { ...form, ansatz: option!.ref, noise_profile: noiseProfileValue(noise) });
      setParams({ run: String(created.id) });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function pin() {
    if (!run) return;
    const p = run.params as unknown as { ansatz: unknown; n_qubits: number; layers: number };
    try {
      await api.post(`/projects/${project.id}/pins`, { ansatz: p.ansatz, n_qubits: p.n_qubits, layers: p.layers });
      setPinMessage("Circuit épinglé : il apparaît dans l'onglet Circuits épinglés du projet.");
    } catch (err) {
      setPinMessage((err as Error).message);
    }
  }

  const result = run?.status === "done" ? run.result : null;
  const runParams = run?.params as unknown as DiagnosticForm | undefined;

  return (
    <>
      <h1>Diagnostic</h1>
      <form className="card" onSubmit={submit} aria-label="Paramètres du diagnostic">
        {catalog.error && <ErrorState message={catalog.error} onRetry={catalog.reload} />}
        <DiagnosticFormFields form={form} setForm={setForm} errors={errors} ansatzOptions={options} />
        <div className="row" style={{ marginTop: 12 }}>
          <NoiseProfileField label="Dégradation sous bruit (facultative)" choice={noise} onChange={setNoise} errors={errors} />
        </div>
        {form.n_samples < LOW_SAMPLES_THRESHOLD && <div className="info" style={{ marginTop: 16 }}>{LOW_SAMPLES_WARNING}</div>}
        <div style={{ marginTop: 16 }}>
          <GuardedButton type="submit" allowed={can("run")} reason={reason("run")} disabled={invalid || options.length === 0}>
            Diagnostiquer
          </GuardedButton>
        </div>
        {error && <ErrorState message={error} />}
      </form>
      <RunStatusBanner run={run} error={pollError} />
      {result && runParams && (
        <>
          <p className="muted">
            Run n° {run!.id} : {refLabel(runParams.ansatz)}, {runParams.n_qubits} qubits, {runParams.layers} couches, {runParams.n_samples} échantillons,
            graine {runParams.seed}, observable {OBSERVABLE_LABELS[runParams.observable as "Z0" | "Zall"] ?? runParams.observable}.
          </p>
          <div className="grid-3" style={{ marginBottom: 20 }}>
            <MetricCard
              label="Expressibilité"
              value={formatMetric(result.expressibility)}
              help="Divergence KL entre l'histogramme des fidélités du circuit et la référence de Haar. Plus bas = plus expressif."
            />
            <MetricCard
              label="Intrication"
              value={formatMetric(result.entangling_capability)}
              help="Mesure de Meyer-Wallach moyenne, entre 0 (états produits) et 1."
            />
            <MetricCard
              label="Variance du gradient"
              value={formatMetric(result.gradient.mean_variance)}
              help="Variance du gradient moyennée sur tous les paramètres (règle du décalage de paramètre). Une valeur qui s'effondre avec le nombre de qubits signale un plateau stérile."
              detail={
                <>
                  Paramètres actifs : {formatMetric(result.gradient.active_mean_variance)}. Inactifs : {result.gradient.n_inactive_parameters} sur{" "}
                  {result.gradient.n_parameters} ({formatPercent(result.gradient.inactive_fraction)}).
                </>
              }
            />
          </div>
          {result.noise && (
            <section className="card" aria-labelledby="degradation-bruit">
              <h2 id="degradation-bruit">Dégradation sous bruit</h2>
              <div className="num" style={{ fontSize: "1.8rem" }}>
                {formatMetric(result.noise.mean_tvd)}
              </div>
              <p>{degradationSentence(result.noise, (run!.params as { noise_profile: NoiseProfile }).noise_profile)}</p>
              <p className="muted">
                Circuit transpilé sur une ligne de {runParams.n_qubits} qubits (portes cx, rz, sx et x), simulé en matrice densité ; rz est supposée sans erreur.
              </p>
            </section>
          )}
          <section className="card" aria-labelledby="histogramme">
            <h2 id="histogramme">Histogramme des fidélités</h2>
            <FidelityHistogram histogram={result.histogram} />
            <p className="muted">Plus bas = plus expressif : l'expressibilité mesure l'écart entre l'histogramme du circuit (barres) et la référence de Haar (courbe).</p>
            <div className="row">
              <CsvButton filename={`diagnostic-${run!.id}.csv`} rows={histogramRows(result.histogram)} params={{ ...runParams }} />
              <GuardedButton
                className="secondary"
                allowed={can("pin") && typeof runParams.ansatz === "string"}
                reason={typeof runParams.ansatz === "string" ? reason("pin") : "Seuls les ansatz du catalogue peuvent être épinglés."}
                onClick={pin}
              >
                Épingler ce circuit
              </GuardedButton>
            </div>
            {pinMessage && <div className="info" style={{ marginTop: 12 }}>{pinMessage}</div>}
          </section>
          <CommentsPanel runId={run!.id} />
        </>
      )}
    </>
  );
}
