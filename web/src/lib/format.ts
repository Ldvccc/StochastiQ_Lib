// Formatage français à l'affichage (l'API renvoie des nombres JSON standard).

/** Nombre avec virgule décimale et ``decimals`` décimales ; « n/a » si non défini. */
export function formatFr(value: number | null | undefined, decimals: number): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "n/a";
  return value.toFixed(decimals).replace(".", ",").replace(/^-(0,0*)$/, "$1");
}

/** Métrique : 4 décimales, sans notation scientifique. */
export function formatMetric(value: number | null | undefined): string {
  return formatFr(value, 4);
}

/** Rapport de nombres de portes : « ×1,00 ». */
export function formatFactor(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "n/a" : `×${formatFr(value, 2)}`;
}

/** Proportion en pourcentage : « 33,3 % ». */
export function formatPercent(value: number | null | undefined): string {
  return value === null || value === undefined || !Number.isFinite(value) ? "n/a" : `${formatFr(100 * value, 1)} %`;
}

/** Date et heure locales, en français. Les dates de l'API sont en UTC sans fuseau. */
export function formatDateTime(iso: string): string {
  const date = new Date(/[zZ]|[+-]\d\d:\d\d$/.test(iso) ? iso : `${iso}Z`);
  return date.toLocaleString("fr-FR", { dateStyle: "short", timeStyle: "short" });
}
