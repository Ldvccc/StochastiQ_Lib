import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { ParetoScatter } from "../components/charts";
import { ErrorState, GuardedButton } from "../components/common";
import { useProject } from "../components/ProjectContext";
import { CommentsPanel, CsvButton, NumberField, RunStatusBanner, useAnsatzCatalog } from "../components/science";
import { formatMetric, formatPercent } from "../lib/format";
import { ansatzLabel, compareSentence, LOW_SAMPLES_THRESHOLD, LOW_SAMPLES_WARNING, PARETO_NOTE, paretoSentence, type CompareRow } from "../lib/reading";
import { boundErrors, launchRun, useRunPolling } from "../lib/runs";

const METRICS: { key: string; label: string }[] = [
  { key: "expressibility", label: "Expressibilité" },
  { key: "entangling_capability", label: "Intrication" },
  { key: "gradient_variance", label: "Variance du gradient" },
  { key: "gradient_variance_active", label: "Variance (actifs)" },
];

function cell(row: CompareRow, key: string): string {
  const value = row[key] as number | null;
  const std = row[`${key}_std`] as number | undefined;
  return std === undefined ? formatMetric(value) : `${formatMetric(value)} ± ${formatMetric(std)}`;
}

export function CompareTable({ rows }: { rows: CompareRow[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th scope="col">Ansatz</th>
            <th scope="col">Paramètres</th>
            <th scope="col">Profondeur</th>
            <th scope="col">Portes à 2 qubits</th>
            {METRICS.map((m) => (
              <th key={m.key} scope="col">
                {m.label}
              </th>
            ))}
            <th scope="col">Paramètres inactifs</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.ansatz}>
              <th scope="row" style={{ color: "var(--ink)" }}>
                {ansatzLabel(row.ansatz)}
              </th>
              <td className="num">{String(row.n_parameters)}</td>
              <td className="num">{String(row.depth)}</td>
              <td className="num">{String(row.n_two_qubit_gates)}</td>
              {METRICS.map((m) => (
                <td key={m.key} className="num">
                  {cell(row, m.key)}
                </td>
              ))}
              <td className="num">{formatPercent(row.inactive_fraction)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ComparePage() {
  const { project, can, reason } = useProject();
  const catalog = useAnsatzCatalog();
  const [params, setParams] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const { run, error: pollError } = useRunPolling<{ rows: CompareRow[] }>(project.id, runId);
  const [selected, setSelected] = useState<string[]>(["hardware_efficient", "strongly_entangling", "data_reuploading"]);
  const [form, setForm] = useState({ n_qubits: 4, layers: 3, n_samples: 1000, n_seeds: 1, seed: 0 });
  const [error, setError] = useState<string | null>(null);
  const errors = boundErrors(form);
  const invalid = Object.keys(errors).length > 0 || selected.length === 0;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (invalid) return;
    setError(null);
    try {
      const created = await launchRun(project.id, "compare", { ansatz: selected, ...form });
      setParams({ run: String(created.id) });
    } catch (err) {
      setError((err as Error).message);
    }
  }

  const toggle = (name: string) => setSelected(selected.includes(name) ? selected.filter((n) => n !== name) : [...selected, name]);
  const set = (key: keyof typeof form) => (value: number) => setForm({ ...form, [key]: value });
  const rows = run?.status === "done" ? (run.result?.rows ?? []) : [];
  const runParams = run?.params as Record<string, unknown> | undefined;

  return (
    <>
      <h1>Comparateur</h1>
      <form className="card" onSubmit={submit} aria-label="Paramètres de la comparaison">
        {catalog.error && <ErrorState message={catalog.error} onRetry={catalog.reload} />}
        <fieldset style={{ border: "none", padding: 0, margin: "0 0 16px" }}>
          <legend style={{ fontWeight: 500, marginBottom: 8 }}>Ansatz à comparer</legend>
          <div className="row">
            {(catalog.data ?? []).map((a) => (
              <label key={a.name} style={{ flexDirection: "row", alignItems: "center", minHeight: 44 }}>
                <input type="checkbox" checked={selected.includes(a.name)} onChange={() => toggle(a.name)} style={{ minHeight: 0, width: 20, height: 20 }} />
                {a.label}
              </label>
            ))}
          </div>
          {selected.length === 0 && <span className="field-error">Sélectionnez au moins un ansatz.</span>}
        </fieldset>
        <div className="row">
          <NumberField label="Qubits" value={form.n_qubits} min={2} max={8} onChange={set("n_qubits")} error={errors.n_qubits} />
          <NumberField label="Couches" value={form.layers} min={1} max={8} onChange={set("layers")} error={errors.layers} />
          <NumberField label="Échantillons" value={form.n_samples} min={50} max={5000} onChange={set("n_samples")} error={errors.n_samples} />
          <NumberField label="Nombre de graines" value={form.n_seeds} min={1} max={10} onChange={set("n_seeds")} error={errors.n_seeds} />
          <NumberField label="Graine" value={form.seed} min={0} max={1_000_000} onChange={set("seed")} error={errors.seed} />
        </div>
        {form.n_samples < LOW_SAMPLES_THRESHOLD && <div className="info" style={{ marginTop: 16 }}>{LOW_SAMPLES_WARNING}</div>}
        <div style={{ marginTop: 16 }}>
          <GuardedButton type="submit" allowed={can("run")} reason={reason("run")} disabled={invalid}>
            Comparer
          </GuardedButton>
        </div>
        {error && <ErrorState message={error} />}
      </form>
      <RunStatusBanner run={run} error={pollError} />
      {rows.length > 0 && runParams && (
        <>
          <section className="card" aria-labelledby="tableau-comparaison">
            <h2 id="tableau-comparaison">Résultats</h2>
            <CompareTable rows={rows} />
            <p className="muted">
              Calcul effectué avec {String(runParams.n_samples)} échantillons, graine {String(runParams.seed)},{" "}
              {runParams.n_seeds === 1 ? "1 graine" : `${String(runParams.n_seeds)} graines`}.
            </p>
            <p>{compareSentence(rows)}</p>
            <CsvButton filename={`comparaison-${run!.id}.csv`} rows={rows} params={runParams} />
          </section>
          <section className="card" aria-labelledby="pareto">
            <h2 id="pareto">Expressibilité et variance du gradient</h2>
            <ParetoScatter rows={rows} />
            <p>{paretoSentence(rows)}</p>
            <p className="muted">{PARETO_NOTE}</p>
          </section>
          <CommentsPanel runId={run!.id} />
        </>
      )}
    </>
  );
}
