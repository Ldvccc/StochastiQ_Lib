import type { ActivityEvent, Role } from "../api/types";
import { ROLE_LABELS } from "./roles";

const KIND_LABELS: Record<string, string> = {
  diagnostic: "diagnostic",
  compare: "comparaison",
  scaling: "étude de plateau stérile",
  hardware: "coût matériel",
  training: "entraînement",
};

function role(value: unknown): string {
  return ROLE_LABELS[value as Role] ?? String(value);
}

/** Phrase française décrivant un événement du fil d'activité. */
export function describeEvent(event: ActivityEvent): string {
  const who = event.user?.name ?? "Un ancien membre";
  const p = event.payload;
  const kind = KIND_LABELS[String(p.kind)] ?? String(p.kind);
  switch (event.type) {
    case "run_launched":
      return `${who} a lancé un run de ${kind} (n° ${p.run_id}).`;
    case "run_done":
      return `Le run de ${kind} n° ${p.run_id} est terminé.`;
    case "run_failed":
      return `Le run de ${kind} n° ${p.run_id} a échoué.`;
    case "comment_added":
      return `${who} a commenté le run n° ${p.run_id} : « ${p.excerpt} »`;
    case "circuit_pinned":
      return `${who} a épinglé ${p.ansatz} (${p.n_qubits} qubits, ${p.layers} couches).`;
    case "member_invited":
      return `${who} a invité ${p.email} comme ${role(p.role).toLowerCase()}.`;
    case "member_joined":
      return `${p.name} a rejoint le projet comme ${role(p.role).toLowerCase()}.`;
    case "role_changed":
      return `${who} a changé le rôle de ${p.name} : ${role(p.old_role).toLowerCase()} vers ${role(p.new_role).toLowerCase()}.`;
    case "problem_added":
      return `${who} a ajouté le problème « ${p.name} » (${p.n_qubits} qubits, ${p.origin === "csv" ? "fichier CSV" : "référence"}).`;
    case "machine_added":
      return `${who} a ajouté la machine ${p.provider} « ${p.label} ».`;
    default:
      return `${who} : ${event.type}.`;
  }
}
