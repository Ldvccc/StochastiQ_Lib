// Phrases de lecture : copie fidèle des règles du dashboard Streamlit (dashboard/ui.py).
// Aucune valeur n'est inventée : tout vient des résultats de l'API.

import { formatFr, formatMetric } from "./format";

export const ANSATZ_LABELS: Record<string, string> = {
  basic_entangler: "BasicEntangler",
  strongly_entangling: "StronglyEntangling",
  hardware_efficient: "HardwareEfficient",
  rotation_only: "RotationOnly",
  all_to_all: "AllToAll",
  brick_wall: "BrickWall",
  data_reuploading: "DataReuploading",
};

export function ansatzLabel(name: string): string {
  return ANSATZ_LABELS[name] ?? name;
}

/** Libellé d'un ansatz dans les paramètres d'un run : nom du catalogue ou ansatz personnalisé. */
export function refLabel(ref: unknown): string {
  if (typeof ref === "string") return ansatzLabel(ref);
  const custom = (ref as { custom?: { name?: string } } | null)?.custom;
  if (custom?.name) return `${custom.name} (personnalisé)`;
  const id = (ref as { custom_id?: number } | null)?.custom_id;
  return id !== undefined ? `Ansatz personnalisé n° ${id}` : String(ref);
}

export const LOW_SAMPLES_THRESHOLD = 1000;
export const LOW_SAMPLES_WARNING =
  "Avec moins de 1000 échantillons, l'expressibilité est surestimée. Comparez uniquement des résultats obtenus avec le même nombre d'échantillons.";

// ---- Comparateur ----

export interface CompareRow {
  ansatz: string;
  expressibility: number;
  entangling_capability: number;
  gradient_variance: number;
  gradient_variance_active: number | null;
  inactive_fraction: number;
  pareto: boolean;
  [key: string]: unknown;
}

const METRIC_LABELS: Record<string, string> = {
  expressibility: "Expressibilité",
  entangling_capability: "Intrication",
};

function metricSentence(rows: CompareRow[], metric: "expressibility" | "entangling_capability", lowerIsBetter: boolean, winner: (n1: string, v1: string, n2: string, v2: string) => string): string {
  const ordered = [...rows].sort((a, b) => (lowerIsBetter ? a[metric] - b[metric] : b[metric] - a[metric]));
  const [first, second] = ordered;
  const name1 = ansatzLabel(first.ansatz);
  const name2 = ansatzLabel(second.ansatz);
  const v1 = first[metric];
  const v2 = second[metric];
  const gap = Math.abs(v1 - v2);
  const label = METRIC_LABELS[metric];
  const stdKey = `${metric}_std`;
  if (stdKey in first) {
    const noise = (first[stdKey] as number) + (second[stdKey] as number);
    if (gap <= noise) {
      return `${label} : « ${name1} » et « ${name2} » sont indistinguables sur cette métrique (écart ${formatMetric(gap)}, inférieur à la somme des écarts-types ${formatMetric(noise)}).`;
    }
  } else if (gap <= 0.1 * Math.abs(v1)) {
    return `${label} : les différences sont du même ordre que le bruit d'échantillonnage ; relancez avec plusieurs graines.`;
  }
  return winner(name1, formatMetric(v1), name2, formatMetric(v2));
}

/**
 * Phrase de lecture du Comparateur. Un gagnant n'est désigné que si l'écart
 * avec le deuxième dépasse 10 % (une graine) ou la somme des écarts-types
 * (plusieurs graines). Chaîne vide s'il y a moins de deux circuits.
 */
export function compareSentence(rows: CompareRow[]): string {
  if (rows.length < 2) return "";
  const sentences = [
    metricSentence(rows, "expressibility", true, (n1, v1, n2, v2) => `Le circuit le plus expressif est « ${n1} » (expressibilité ${v1}, contre ${v2} pour « ${n2} »).`),
    metricSentence(rows, "entangling_capability", false, (n1, v1, n2, v2) => `La plus forte intrication est obtenue par « ${n1} » (${v1}, contre ${v2} pour « ${n2} »).`),
  ];
  if ("expressibility_std" in rows[0]) sentences.push("Valeurs moyennes sur les graines.");
  return sentences.join(" ");
}

export const PARETO_NOTE =
  "Ordonnée : variance du gradient moyennée sur les seuls paramètres actifs, pour ne pas pénaliser un circuit dont beaucoup de paramètres sont sans effet sur l'observable Z0.";

/** Phrase du nuage de points : liste les ansatz du front de Pareto (indicateur calculé par l'API). */
export function paretoSentence(rows: CompareRow[]): string {
  if (rows.length === 0) return "";
  const quoted = rows.filter((r) => r.pareto).map((r) => `« ${ansatzLabel(r.ansatz)} »`);
  const first =
    quoted.length === 1
      ? `Le front de Pareto ne contient que ${quoted[0]}.`
      : `Le front de Pareto contient ${quoted.slice(0, -1).join(", ")} et ${quoted[quoted.length - 1]}.`;
  return `${first} Un circuit du front n'est battu par aucun autre sur les deux critères (expressibilité plus basse et variance du gradient des paramètres actifs plus élevée).`;
}

// ---- Plateau stérile ----

export interface Fit {
  factor_per_qubit: number | null;
  r2: number | null;
  n_points: number;
}

export const BARREN_FACTOR = 0.8;
export const BARREN_R2 = 0.9;
export const DILUTION_GAP = 0.1;
export const DILUTION_SENTENCE =
  "Une partie de la baisse de la moyenne sur tous les paramètres vient de paramètres sans effet sur l'observable (dilution), pas d'une perte de signal.";
export const LOCAL_VS_GLOBAL_SENTENCE =
  "Le circuit reste entraînable avec un coût local, mais pas avec un coût global ; l'entraînement d'un QCBM sur une distribution complète se rapproche du cas global.";
export const PROPORTIONAL_LAYERS_NOTE = "En mode proportionnel, le nombre de couches est égal au nombre de qubits.";

export function isNetDecay(fit: Fit): boolean {
  return fit.factor_per_qubit !== null && fit.r2 !== null && fit.factor_per_qubit < BARREN_FACTOR && fit.r2 > BARREN_R2;
}

export function layersLine(mode: "fixed" | "linear", layers: number): string {
  return mode === "linear" ? "Couches : égales au nombre de qubits." : `Couches : ${layers} (fixe).`;
}

/** Phrase d'une étude, fondée sur les paramètres actifs, avec la mention de dilution. */
export function scalingSentence(name: string, active: Fit, all: Fit): string {
  const label = `« ${ansatzLabel(name)} »`;
  if (active.factor_per_qubit === null || active.r2 === null) {
    return `${label} : données insuffisantes pour un ajustement sur les paramètres actifs (${active.n_points} point(s) valide(s), 3 nécessaires).`;
  }
  const factor = active.factor_per_qubit;
  let sentence = `${label}, paramètres actifs : la variance est multipliée par ${formatFr(factor, 2)} à chaque qubit ajouté (ajustement exponentiel, R² = ${formatFr(active.r2, 3)})`;
  sentence += isNetDecay(active)
    ? " ; décroissance exponentielle nette : plateau stérile sur cette plage de qubits, avec cette observable."
    : " ; pas de décroissance exponentielle nette sur cette plage.";
  // La dilution ne peut qu'accélérer la baisse de la moyenne sur tous les paramètres.
  if (all.factor_per_qubit !== null && all.factor_per_qubit < factor - DILUTION_GAP) {
    sentence += ` Sur tous les paramètres, le facteur est ${formatFr(all.factor_per_qubit, 2)}. ${DILUTION_SENTENCE}`;
  }
  return sentence;
}

/** Phrase de la comparaison coût local / coût global, sur les paramètres actifs. */
export function observablesSentence(name: string, local: Fit, global: Fit): string {
  const label = `« ${ansatzLabel(name)} »`;
  if (local.factor_per_qubit === null || global.factor_per_qubit === null || local.r2 === null || global.r2 === null) {
    return `${label} : données insuffisantes pour comparer les coûts local et global (3 points valides nécessaires par série).`;
  }
  const sentence = `${label}, paramètres actifs : facteur par qubit ${formatFr(local.factor_per_qubit, 2)} en local (R² = ${formatFr(local.r2, 3)}) et ${formatFr(global.factor_per_qubit, 2)} en global (R² = ${formatFr(global.r2, 3)}).`;
  const netLocal = isNetDecay(local);
  const netGlobal = isNetDecay(global);
  if (netGlobal && !netLocal) return `${sentence} ${LOCAL_VS_GLOBAL_SENTENCE}`;
  if (netGlobal) return `${sentence} Décroissance exponentielle nette avec les deux coûts sur cette plage.`;
  if (netLocal) return `${sentence} Décroissance exponentielle nette avec le coût local seulement sur cette plage.`;
  return `${sentence} Pas de décroissance exponentielle nette sur cette plage, ni en local ni en global.`;
}

// ---- Entraînement (règle propre au web) ----

export interface DistributionMetrics {
  kl: number;
  tvd: number;
  hellinger: number;
}

export interface TrainingResult {
  history: number[];
  metrics: DistributionMetrics;
  n_parameters: number;
  n_iterations: number;
  loss: string;
  optimizer: string;
  probabilities: number[];
  baselines: Record<"independent" | "chow_liu", { probabilities: number[]; metrics: DistributionMetrics; n_parameters: number }>;
}

export const BASELINE_LABELS: Record<string, string> = {
  independent: "marginales indépendantes",
  chow_liu: "arbre de Chow-Liu",
};

export const LOSS_LABELS: Record<string, string> = { kl: "KL", mmd: "MMD", tvd: "TVD" };
export const OPTIMIZER_LABELS: Record<string, string> = { adam: "Adam", spsa: "SPSA", cobyla: "COBYLA" };

// Écart de TVD en dessous duquel l'ansatz et la référence sont dits à égalité.
export const TVD_TIE = 1e-4;

/**
 * Phrase factuelle : TVD atteinte par l'ansatz et comparaison avec la meilleure
 * référence classique (TVD la plus basse), avec les nombres de paramètres.
 */
export function trainingSentence(result: TrainingResult, shots: number | null): string {
  const tvd = result.metrics.tvd;
  const [bestName, best] = Object.entries(result.baselines).sort(([, a], [, b]) => a.metrics.tvd - b.metrics.tvd)[0];
  const bestLabel = BASELINE_LABELS[bestName];
  const opening = `Après ${result.n_iterations} itérations (perte ${LOSS_LABELS[result.loss]}, ${OPTIMIZER_LABELS[result.optimizer]}), l'ansatz atteint une TVD de ${formatMetric(tvd)} avec ${result.n_parameters} paramètres.`;
  let comparison: string;
  if (Math.abs(tvd - best.metrics.tvd) <= TVD_TIE) {
    comparison = `La meilleure référence classique (${bestLabel}, ${best.n_parameters} paramètres) atteint la même TVD à 0,0001 près.`;
  } else if (tvd < best.metrics.tvd) {
    comparison = `Il fait mieux que les deux références classiques ; la meilleure (${bestLabel}, ${best.n_parameters} paramètres) atteint ${formatMetric(best.metrics.tvd)}.`;
  } else {
    comparison = `La référence classique « ${bestLabel} » fait mieux : TVD de ${formatMetric(best.metrics.tvd)} avec ${best.n_parameters} paramètres.`;
  }
  const scope = shots
    ? `Une seule initialisation, entraînée avec ${shots} tirages par évaluation ; TVD calculée sur les probabilités exactes.`
    : "Une seule initialisation, en simulation exacte sans bruit.";
  return `${opening} ${comparison} ${scope}`;
}

// ---- Axe logarithmique ----

/**
 * Puissances de dix couvrant [vmin, vmax], étendues d'une décade (côté le
 * plus proche des données) tant qu'il y en a moins de deux. Lève une erreur
 * si une borne est négative ou nulle.
 */
export function logTicks(vmin: number, vmax: number): number[] {
  if (vmin <= 0 || vmax <= 0) throw new Error("logTicks attend des valeurs strictement positives.");
  if (vmin > vmax) throw new Error("logTicks attend vmin <= vmax.");
  const loLog = Math.log10(vmin);
  const hiLog = Math.log10(vmax);
  let lo = Math.ceil(loLog - 1e-9);
  let hi = Math.floor(hiLog + 1e-9);
  while (hi - lo + 1 < 2) {
    if (loLog - (lo - 1) <= hi + 1 - hiLog) lo -= 1;
    else hi += 1;
  }
  const ticks: number[] = [];
  for (let k = lo; k <= hi; k += 1) ticks.push(Number(`1e${k}`));
  return ticks;
}

/** Étiquette d'une graduation logarithmique : « 0,01 », ou « 1e-5 » sous 0,0001. */
export function logTickLabel(value: number): string {
  if (value <= 0) return "";
  const exponent = Math.floor(Math.log10(value) + 1e-9);
  if (value < 1e-4) {
    const mantissa = Number((value / 10 ** exponent).toPrecision(2));
    return `${String(mantissa).replace(".", ",")}e${exponent}`;
  }
  return formatFr(value, Math.max(0, -exponent));
}
