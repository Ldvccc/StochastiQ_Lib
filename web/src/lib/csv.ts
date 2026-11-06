// Export CSV côté client : UTF-8, virgule séparatrice, point décimal, noms de
// colonnes techniques, première ligne de commentaire « # » avec les paramètres.

export const CSV_LABEL = "Télécharger en CSV";
export const APP_VERSION = "0.2.0";

function cell(value: unknown): string {
  if (value === null || value === undefined) return "";
  const text = typeof value === "number" ? String(value) : typeof value === "object" ? JSON.stringify(value) : String(value);
  return /[",\n\r]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

export function toCsv(rows: Record<string, unknown>[], params: Record<string, unknown>): string {
  const comment = "# " + Object.entries({ ...params, version: APP_VERSION }).map(([key, value]) => `${key}=${value}`).join("; ");
  const columns = rows.length > 0 ? Object.keys(rows[0]) : [];
  const lines = [comment, columns.join(","), ...rows.map((row) => columns.map((column) => cell(row[column])).join(","))];
  return lines.join("\n") + "\n";
}

export function downloadCsv(filename: string, content: string): void {
  const blob = new Blob([content], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}
