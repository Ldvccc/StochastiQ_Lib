import { useEffect, useState } from "react";

import { api } from "../api/client";
import type { Run, RunKind } from "../api/types";

export const POLL_INTERVAL_MS = 2000;

export interface Bounds {
  min: number;
  max: number;
}

export const LIMITS: Record<string, Bounds> = {
  n_qubits: { min: 2, max: 8 },
  layers: { min: 1, max: 8 },
  n_samples: { min: 50, max: 5000 },
  n_seeds: { min: 1, max: 10 },
  seed: { min: 0, max: 1_000_000 },
};

const FIELD_LABELS: Record<string, string> = {
  n_qubits: "Qubits",
  layers: "Couches",
  n_samples: "Échantillons",
  n_seeds: "Nombre de graines",
  seed: "Graine",
};

/** Erreurs de bornes des champs numériques (mêmes limites que l'API). */
export function boundErrors(values: Record<string, number>): Record<string, string> {
  const errors: Record<string, string> = {};
  for (const [field, value] of Object.entries(values)) {
    const bounds = LIMITS[field];
    if (!bounds) continue;
    if (!Number.isInteger(value) || value < bounds.min || value > bounds.max) {
      errors[field] = `${FIELD_LABELS[field]} : entier de ${bounds.min} à ${bounds.max.toLocaleString("fr-FR")}.`;
    }
  }
  return errors;
}

export function launchRun(projectId: number, kind: RunKind, params: Record<string, unknown>): Promise<Run> {
  return api.post<Run>(`/projects/${projectId}/runs`, { kind, params });
}

/**
 * Suit un run en interrogeant l'API toutes les 2 s jusqu'à « done » ou
 * « failed ». Le sondage s'arrête au démontage du composant.
 */
export function useRunPolling<R>(projectId: number, runId: number | null): { run: Run<R> | null; error: string | null } {
  const [run, setRun] = useState<Run<R> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setRun(null);
    setError(null);
    if (runId === null) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const poll = async () => {
      try {
        const current = await api.get<Run<R>>(`/projects/${projectId}/runs/${runId}`);
        if (!active) return;
        setRun(current);
        if (current.status === "pending" || current.status === "running") timer = setTimeout(poll, POLL_INTERVAL_MS);
      } catch (err) {
        if (active) setError((err as Error).message);
      }
    };
    poll();
    return () => {
      active = false;
      if (timer !== undefined) clearTimeout(timer);
    };
  }, [projectId, runId]);

  return { run, error };
}
