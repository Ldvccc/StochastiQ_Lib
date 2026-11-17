import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { ScalingChart, SERIES_STYLES, type ScalingLine } from "../components/charts";
import { ErrorState, GuardedButton } from "../components/common";
import { useProject } from "../components/ProjectContext";
import { CommentsPanel, CsvButton, NumberField, RunStatusBanner, useAnsatzOptions } from "../components/science";
import { formatFactor, formatFr, formatPercent } from "../lib/format";
import { ansatzLabel, layersLine, observablesSentence, PROPORTIONAL_LAYERS_NOTE, scalingSentence, type Fit } from "../lib/reading";
import { boundErrors, launchRun, useRunPolling } from "../lib/runs";

interface Series {
  ansatz: string;
  observable: "Z0" | "Zmean" | "Zall";
  rows: { n_qubits: number; layers: number; mean_variance: number; active_mean_variance: number | null; inactive_fraction: number }[];
  fit_active: Fit;
  fit_all: Fit;
}

const MAX_ANSATZ = 4;

function factor(fit: Fit): string {
  return fit.factor_per_qubit === null ? "données insuffisantes" : formatFactor(fit.factor_per_qubit);
}

function r2(fit: Fit): string {
  return fit.r2 === null ? "n/a" : formatFr(fit.r2, 3);
}

/** Courbes : actifs (trait plein) et tous (pointillé), ou coût local (plein) et global (mixte). */
export function scalingLines(series: Series[], compareObservables: boolean): ScalingLine[] {
  const names = [...new Set(series.map((s) => s.ansatz))];
  return names.flatMap<ScalingLine>((name, i) => {
    const style = SERIES_STYLES[i % SERIES_STYLES.length];
    const of = (observable: string) => series.find((s) => s.ansatz === name && s.observable === observable)!;
    const points = (s: Series, key: "active_mean_variance" | "mean_variance") => s.rows.map((r) => ({ n_qubits: r.n_qubits, value: r[key] }));
    if (compareObservables) {
      return [
        { key: `${name}-local`, name: ansatzLabel(name), ...style, dash: "solid" as const, data: points(of("Z0"), "active_mean_variance") },
        { key: `${name}-global`, name: `${ansatzLabel(name)} (global)`, ...style, dash: "dashdot" as const, data: points(of("Zall"), "active_mean_variance") },
      ];
    }
    const s = series.find((x) => x.ansatz === name)!;
    return [
      { key: `${name}-actifs`, name: ansatzLabel(name), ...style, dash: "solid" as const, data: points(s, "active_mean_variance") },
      { key: `${name}-tous`, name: `${ansatzLabel(name)} (tous)`, ...style, dash: "dashed" as const, data: points(s, "mean_variance") },
    ];
  });
}

export function BarrenPage() {
  const { project, can, reason } = useProject();
  // Un ansatz à nombre de qubits fixe ne se prête pas à une étude de scaling : il n'est pas proposé.
  const options = useAnsatzOptions(project.id);
  const catalog = { ...options, data: options.data?.filter((o) => o.fixedQubits === null) ?? null };
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const { run, error: pollError } = useRunPolling<{ series: Series[] }>(project.id, runId);
  const [selected, setSelected] = useState<string[]>(["cat:hardware_efficient", "cat:strongly_entangling", "cat:data_reuploading"]);
  const [form, setForm] = useState({ qubit_min: 2, qubit_max: 6, layers: 3, n_samples: 100, seed: 0 });
  const [mode, setMode] = useState<"fixed" | "linear">("fixed");
  const [observable, setObservable] = useState<"Z0" | "Zall">("Z0");
  const [compareObservables, setCompareObservables] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const errors = boundErrors({ n_qubits: form.qubit_min, layers: form.layers, n_samples: form.n_samples, seed: form.seed });
  const maxErrors = boundErrors({ n_qubits: form.qubit_max });
  if (maxErrors.n_qubits) errors.qubit_max = maxErrors.n_qubits;
  if (errors.n_qubits) errors.qubit_min = errors.n_qubits;
  if (!errors.qubit_min && !errors.qubit_max && form.qubit_min > form.qubit_max) errors.qubit_max = "Le maximum doit être supérieur ou égal au minimum.";
  delete errors.n_qubits;
  const invalid = Object.keys(errors).length > 0 || selected.length === 0;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (invalid) return;
    setError(null);
    try {
      const created = await launchRun(project.id, "scaling", {
        ansatz: (catalog.data ?? []).filter((o) => selected.includes(o.value)).map((o) => o.ref),
        ...form,
        layers_mode: mode,
        observable,
        compare_observables: compareObservables,
      });
      setParams({ run: String(created.id) });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const toggle = (name: string) =>
    setSelected(selected.includes(name) ? selected.filter((n) => n !== name) : selected.length < MAX_ANSATZ ? [...selected, name] : selected);
  const set = (key: keyof typeof form) => (value: number) => setForm({ ...form, [key]: value });

  const series = run?.status === "done" ? (run.result?.series ?? []) : [];
  const runParams = run?.params as Record<string, unknown> | undefined;
  const ranCompare = Boolean(runParams?.compare_observables);
  const names = [...new Set(series.map((s) => s.ansatz))];
  const csvRows = series.flatMap((s) => s.rows.map((r) => ({ ansatz: s.ansatz, observable: s.observable, ...r })));

  return (
    <>
      <h1>Plateau stérile</h1>
      <form className="card" onSubmit={submit} aria-label="Paramètres de l'étude">
        {catalog.error && <ErrorState message={catalog.error} onRetry={catalog.reload} />}
        <fieldset style={{ border: "none", padding: 0, margin: "0 0 16px" }}>
          <legend style={{ fontWeight: 500, marginBottom: 8 }}>Ansatz ({MAX_ANSATZ} au plus)</legend>
          <div className="row">
            {(catalog.data ?? []).map((a) => {
              const checked = selected.includes(a.value);
              const blocked = !checked && selected.length >= MAX_ANSATZ;
              return (
                <label key={a.value} style={{ flexDirection: "row", alignItems: "center", minHeight: 44 }} title={blocked ? "4 ansatz au plus" : undefined}>
                  <input type="checkbox" checked={checked} disabled={blocked} onChange={() => toggle(a.value)} style={{ minHeight: 0, width: 20, height: 20 }} />
                  {a.label}
                </label>
              );
            })}
          </div>
        </fieldset>
        <div className="row">
          <NumberField label="Qubits min" value={form.qubit_min} min={2} max={8} onChange={set("qubit_min")} error={errors.qubit_min} />
          <NumberField label="Qubits max" value={form.qubit_max} min={2} max={8} onChange={set("qubit_max")} error={errors.qubit_max} />
          <label>
            Mode de couches
            <select value={mode} onChange={(e) => setMode(e.target.value as "fixed" | "linear")}>
              <option value="fixed">Fixe</option>
              <option value="linear">Proportionnel aux qubits</option>
            </select>
          </label>
          <NumberField
            label="Couches"
            value={form.layers}
            min={1}
            max={8}
            onChange={set("layers")}
            error={errors.layers}
            disabled={mode === "linear"}
            note={mode === "linear" ? PROPORTIONAL_LAYERS_NOTE : undefined}
          />
          <NumberField label="Échantillons" value={form.n_samples} min={50} max={5000} onChange={set("n_samples")} error={errors.n_samples} />
          <NumberField label="Graine" value={form.seed} min={0} max={1_000_000} onChange={set("seed")} error={errors.seed} />
          <label>
            Observable
            <select value={observable} disabled={compareObservables} onChange={(e) => setObservable(e.target.value as "Z0" | "Zall")}>
              <option value="Z0">Locale Z0</option>
              <option value="Zall">Globale Z⊗n</option>
            </select>
          </label>
          <label style={{ flexDirection: "row", alignItems: "center", minHeight: 44 }}>
            <input type="checkbox" checked={compareObservables} onChange={(e) => setCompareObservables(e.target.checked)} style={{ minHeight: 0, width: 20, height: 20 }} />
            Comparer local et global
          </label>
        </div>
        {form.qubit_max > 6 && <div className="info" style={{ marginTop: 16 }}>Plage au-delà de 6 qubits : calcul plus long.</div>}
        <div style={{ marginTop: 16 }}>
          <GuardedButton type="submit" allowed={can("run")} reason={reason("run")} disabled={invalid}>
            Lancer l'étude
          </GuardedButton>
        </div>
        {error && <ErrorState message={error} />}
      </form>
      <RunStatusBanner run={run} error={pollError} />
      {series.length > 0 && runParams && (
        <>
          <section className="card" aria-labelledby="courbes">
            <h2 id="courbes">Variance du gradient en fonction du nombre de qubits</h2>
            <ScalingChart
              lines={scalingLines(series, ranCompare)}
              legend={
                ranCompare
                  ? [
                      { label: "Trait plein : coût local Z0 (actifs)", dash: "solid" },
                      { label: "Trait mixte : coût global Z⊗n (actifs)", dash: "dashdot" },
                    ]
                  : [
                      { label: "Trait plein : paramètres actifs", dash: "solid" },
                      { label: "Pointillé : tous les paramètres", dash: "dashed" },
                    ]
              }
            />
            <div className="table-wrap">
              <table>
                <thead>
                  {ranCompare ? (
                    <tr>
                      <th scope="col">Ansatz</th>
                      <th scope="col">Facteur par qubit (local)</th>
                      <th scope="col">R² (local)</th>
                      <th scope="col">Facteur par qubit (global)</th>
                      <th scope="col">R² (global)</th>
                    </tr>
                  ) : (
                    <tr>
                      <th scope="col">Ansatz</th>
                      <th scope="col">Facteur par qubit (actifs)</th>
                      <th scope="col">R² (actifs)</th>
                      <th scope="col">Facteur par qubit (tous)</th>
                      <th scope="col">R² (tous)</th>
                      <th scope="col">Paramètres inactifs (moyenne)</th>
                    </tr>
                  )}
                </thead>
                <tbody>
                  {names.map((name) => {
                    if (ranCompare) {
                      const local = series.find((s) => s.ansatz === name && s.observable === "Z0")!.fit_active;
                      const global = series.find((s) => s.ansatz === name && s.observable === "Zall")!.fit_active;
                      return (
                        <tr key={name}>
                          <th scope="row">{ansatzLabel(name)}</th>
                          <td className="num">{factor(local)}</td>
                          <td className="num">{r2(local)}</td>
                          <td className="num">{factor(global)}</td>
                          <td className="num">{r2(global)}</td>
                        </tr>
                      );
                    }
                    const s = series.find((x) => x.ansatz === name)!;
                    const inactive = s.rows.reduce((sum, r) => sum + r.inactive_fraction, 0) / s.rows.length;
                    return (
                      <tr key={name}>
                        <th scope="row">{ansatzLabel(name)}</th>
                        <td className="num">{factor(s.fit_active)}</td>
                        <td className="num">{r2(s.fit_active)}</td>
                        <td className="num">{factor(s.fit_all)}</td>
                        <td className="num">{r2(s.fit_all)}</td>
                        <td className="num">{formatPercent(inactive)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <div style={{ marginTop: 16 }}>
              <p>{layersLine(runParams.layers_mode as "fixed" | "linear", runParams.layers as number)}</p>
              {names.map((name) => {
                if (ranCompare) {
                  const local = series.find((s) => s.ansatz === name && s.observable === "Z0")!.fit_active;
                  const global = series.find((s) => s.ansatz === name && s.observable === "Zall")!.fit_active;
                  return <p key={name}>{observablesSentence(name, local, global)}</p>;
                }
                const s = series.find((x) => x.ansatz === name)!;
                return <p key={name}>{scalingSentence(name, s.fit_active, s.fit_all)}</p>;
              })}
            </div>
            <p className="muted">
              {ranCompare
                ? "Comparaison d'un coût local (Z0) et d'un coût global (Z⊗n), sur les paramètres actifs ; le résultat dépend du nombre de couches."
                : runParams.observable === "Zall"
                  ? "Résultat sur une observable globale Z⊗n ; il dépend de l'observable et du nombre de couches."
                  : "Résultat sur une observable locale Z0 ; il dépend de l'observable et du nombre de couches."}
            </p>
            <CsvButton filename={`plateau-sterile-${run!.id}.csv`} rows={csvRows} params={runParams} />
          </section>
          <CommentsPanel runId={run!.id} />
        </>
      )}
    </>
  );
}
