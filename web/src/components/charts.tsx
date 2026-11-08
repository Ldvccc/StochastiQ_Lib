// Graphiques aux couleurs de la charte. Le paramètre ``width`` fixe la largeur
// (tests) ; sinon le graphique suit la largeur de son conteneur.

import type { ReactElement } from "react";
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  ErrorBar,
  LabelList,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { formatFr, formatMetric } from "../lib/format";
import { ansatzLabel, logTickLabel, logTicks, type CompareRow } from "../lib/reading";

export const COLORS = {
  violet: "#5b4bff",
  violetSoft: "#ece9ff",
  ink: "#14163f",
  inkMuted: "#585b7a",
  coral: "#d42a45",
  line: "#e1dfee",
};

const AXIS = { stroke: COLORS.inkMuted, fontSize: 12 };

function Frame({ width, height, children }: { width?: number; height: number; children: ReactElement }) {
  if (width) return <div style={{ width, height }}>{children}</div>;
  return (
    <ResponsiveContainer width="100%" height={height}>
      {children}
    </ResponsiveContainer>
  );
}

const decimalTick = (value: number) => String(value).replace(".", ",");

// ---- Histogramme des fidélités ----

export interface Histogram {
  edges: number[];
  circuit: number[];
  haar: number[];
}

export function histogramRows(histogram: Histogram) {
  return histogram.circuit.map((circuit, i) => ({
    fidelity: (histogram.edges[i] + histogram.edges[i + 1]) / 2,
    circuit,
    haar: histogram.haar[i],
  }));
}

export function FidelityHistogram({ histogram, width }: { histogram: Histogram; width?: number }) {
  const data = histogramRows(histogram);
  return (
    <Frame width={width} height={300}>
      <ComposedChart data={data} width={width} height={300} margin={{ top: 10, right: 20, bottom: 24, left: 10 }} barCategoryGap={0}>
        <CartesianGrid vertical={false} stroke={COLORS.line} />
        <XAxis
          dataKey="fidelity"
          type="number"
          domain={[0, 1]}
          tickFormatter={decimalTick}
          tick={AXIS}
          label={{ value: "Fidélité", position: "insideBottom", offset: -12, fill: COLORS.inkMuted }}
        />
        <YAxis tickFormatter={decimalTick} tick={AXIS} />
        <Tooltip formatter={(value: number) => formatMetric(value)} labelFormatter={(v: number) => `Fidélité ${formatFr(v, 3)}`} />
        <Legend verticalAlign="top" />
        <Bar dataKey="circuit" name="Circuit" fill={COLORS.violet} isAnimationActive={false} />
        <Line dataKey="haar" name="Référence de Haar" stroke={COLORS.coral} strokeWidth={2} dot={false} isAnimationActive={false} />
      </ComposedChart>
    </Frame>
  );
}

// ---- Distribution d'un problème ----

/** Chaîne de bits de l'indice (qubit n-1 à gauche, convention Qiskit). */
export function bitstring(index: number, nQubits: number): string {
  return index.toString(2).padStart(nQubits, "0");
}

export function DistributionChart({ probabilities, width, compare }: { probabilities: number[]; width?: number; compare?: { label: string; values: number[] } }) {
  const nQubits = Math.log2(probabilities.length);
  const data = probabilities.map((p, i) => ({ state: bitstring(i, nQubits), probability: p, other: compare?.values[i] }));
  const showTicks = nQubits <= 4;
  return (
    <Frame width={width} height={280}>
      <ComposedChart data={data} width={width} height={280} margin={{ top: 10, right: 20, bottom: 24, left: 10 }} barCategoryGap={1}>
        <CartesianGrid vertical={false} stroke={COLORS.line} />
        <XAxis
          dataKey="state"
          tick={showTicks ? AXIS : false}
          interval={0}
          label={{ value: showTicks ? "État (qubit n-1 à gauche)" : `${probabilities.length} états (qubit n-1 à gauche)`, position: "insideBottom", offset: -12, fill: COLORS.inkMuted }}
        />
        <YAxis tickFormatter={decimalTick} tick={AXIS} />
        <Tooltip formatter={(value: number) => formatMetric(value)} labelFormatter={(state: string) => `État ${state}`} />
        {compare && <Legend verticalAlign="top" />}
        <Bar dataKey="probability" name={compare ? "Cible" : "Probabilité"} fill={COLORS.violet} isAnimationActive={false} />
        {compare && <Line dataKey="other" name={compare.label} stroke={COLORS.ink} strokeWidth={2} dot={false} isAnimationActive={false} />}
      </ComposedChart>
    </Frame>
  );
}

// ---- Nuage expressibilité / variance active ----

export function ParetoScatter({ rows, width }: { rows: CompareRow[]; width?: number }) {
  const withStd = rows.length > 0 && "expressibility_std" in rows[0];
  const points = rows
    .filter((r) => r.gradient_variance_active !== null)
    .map((r) => ({
      x: r.expressibility,
      y: r.gradient_variance_active as number,
      label: ansatzLabel(r.ansatz),
      errorX: withStd ? (r.expressibility_std as number) : 0,
      errorY: withStd ? (r.gradient_variance_active_std as number) : 0,
      pareto: r.pareto,
    }));
  const series = [
    { name: "Front de Pareto", data: points.filter((p) => p.pareto), fill: COLORS.violet },
    { name: "Autres", data: points.filter((p) => !p.pareto), fill: COLORS.violetSoft },
  ];
  return (
    <Frame width={width} height={340}>
      <ScatterChart width={width} height={340} margin={{ top: 10, right: 90, bottom: 30, left: 20 }}>
        <CartesianGrid stroke={COLORS.line} />
        <XAxis
          dataKey="x"
          type="number"
          name="Expressibilité"
          tickFormatter={decimalTick}
          tick={AXIS}
          label={{ value: "Expressibilité (plus bas = plus expressif)", position: "insideBottom", offset: -18, fill: COLORS.inkMuted }}
        />
        <YAxis
          dataKey="y"
          type="number"
          name="Variance active"
          tickFormatter={decimalTick}
          tick={AXIS}
          label={{ value: "Variance du gradient (actifs)", angle: -90, position: "insideLeft", fill: COLORS.inkMuted }}
        />
        <Tooltip formatter={(value: number) => formatMetric(value)} />
        <Legend verticalAlign="top" />
        {series.map((s) => (
          <Scatter key={s.name} name={s.name} data={s.data} fill={s.fill} stroke={COLORS.violet} isAnimationActive={false}>
            {withStd && <ErrorBar dataKey="errorY" direction="y" stroke={COLORS.inkMuted} />}
            {withStd && <ErrorBar dataKey="errorX" direction="x" stroke={COLORS.inkMuted} />}
            <LabelList dataKey="label" position="right" fill={COLORS.ink} fontSize={11} />
          </Scatter>
        ))}
      </ScatterChart>
    </Frame>
  );
}

// ---- Variance du gradient en fonction du nombre de qubits (échelle log) ----

export type Dash = "solid" | "dashed" | "dashdot";
export type Marker = "circle" | "square" | "triangle" | "diamond";

export interface ScalingLine {
  key: string;
  name: string;
  color: string;
  marker: Marker;
  dash: Dash;
  data: { n_qubits: number; value: number | null }[];
}

// Une couleur et un marqueur par ansatz : la couleur n'est jamais le seul repère.
export const SERIES_STYLES: { color: string; marker: Marker }[] = [
  { color: COLORS.violet, marker: "circle" },
  { color: COLORS.ink, marker: "square" },
  { color: COLORS.coral, marker: "triangle" },
  { color: COLORS.inkMuted, marker: "diamond" },
];

const DASHES: Record<Dash, string | undefined> = { solid: undefined, dashed: "6 4", dashdot: "9 3 2 3" };

function MarkerShape({ cx, cy, marker, color, hollow }: { cx?: number; cy?: number; marker: Marker; color: string; hollow: boolean }) {
  if (cx === undefined || cy === undefined) return null;
  const fill = hollow ? "#ffffff" : color;
  const props = { fill, stroke: color, strokeWidth: 1.5 };
  if (marker === "square") return <rect x={cx - 4.5} y={cy - 4.5} width={9} height={9} {...props} />;
  if (marker === "triangle") return <polygon points={`${cx},${cy - 6} ${cx - 5.5},${cy + 4} ${cx + 5.5},${cy + 4}`} {...props} />;
  if (marker === "diamond") return <polygon points={`${cx},${cy - 6} ${cx + 6},${cy} ${cx},${cy + 6} ${cx - 6},${cy}`} {...props} />;
  return <circle cx={cx} cy={cy} r={4.5} {...props} />;
}

export function ScalingChart({ lines, legend, width }: { lines: ScalingLine[]; legend: { label: string; dash: Dash }[]; width?: number }) {
  const positive = lines.flatMap((line) => line.data.map((d) => d.value).filter((v): v is number => v !== null && v > 0));
  const ticks = positive.length > 0 ? logTicks(Math.min(...positive), Math.max(...positive)) : [0.01, 0.1];
  const domain: [number, number] = positive.length
    ? [Math.min(ticks[0], ...positive) / 1.15, Math.max(ticks[ticks.length - 1], ...positive) * 1.15]
    : [0.01, 0.1];
  const qubits = lines.flatMap((line) => line.data.map((d) => d.n_qubits));
  const legendPayload = [
    ...lines
      .filter((line) => line.dash !== "dashed" && line.dash !== "dashdot")
      .map((line) => ({ value: line.name, type: "line" as const, color: line.color, id: line.key })),
    ...legend.map((item) => ({ value: item.label, type: "line" as const, color: COLORS.inkMuted, id: item.label })),
  ];
  return (
    <Frame width={width} height={340}>
      <LineChart width={width} height={340} margin={{ top: 10, right: 20, bottom: 24, left: 10 }}>
        <CartesianGrid vertical={false} stroke={COLORS.line} />
        <XAxis
          dataKey="n_qubits"
          type="number"
          domain={[Math.min(...qubits), Math.max(...qubits)]}
          allowDecimals={false}
          tick={AXIS}
          label={{ value: "Nombre de qubits", position: "insideBottom", offset: -12, fill: COLORS.inkMuted }}
        />
        <YAxis scale="log" domain={domain} ticks={ticks} allowDataOverflow tickFormatter={logTickLabel} tick={AXIS} width={64} />
        <Tooltip formatter={(value: number) => formatMetric(value)} labelFormatter={(n: number) => `${n} qubits`} />
        <Legend verticalAlign="top" payload={legendPayload} />
        {lines.map((line) => (
          <Line
            key={line.key}
            data={line.data.filter((d) => d.value !== null && d.value > 0)}
            dataKey="value"
            name={line.name}
            stroke={line.color}
            strokeWidth={1.8}
            strokeDasharray={DASHES[line.dash]}
            isAnimationActive={false}
            dot={(props: { cx?: number; cy?: number; key?: string }) => (
              <MarkerShape key={props.key} cx={props.cx} cy={props.cy} marker={line.marker} color={line.color} hollow={line.dash !== "solid"} />
            )}
          />
        ))}
      </LineChart>
    </Frame>
  );
}
