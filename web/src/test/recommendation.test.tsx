import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Project } from "../api/types";
import { ProjectContextProvider } from "../components/ProjectContext";
import { NO_NOISE_CHOICE } from "../components/science";
import { quotedList, recommendationSentences, type RecommendationItem, type RecommendationResult } from "../lib/reading";
import { can, DEFAULT_PERMISSIONS, deniedReason } from "../lib/roles";
import { intervalText, RankingTable, recommendationErrors, type RecommendationForm } from "../pages/RecommendationPage";
import { ReportPage } from "../pages/ReportPage";

function item(
  key: string,
  value: number,
  low: number | null,
  high: number | null,
  source: RecommendationItem["source"] = "model",
  margin: number | null = null,
  nParameters = 8,
): RecommendationItem {
  const prediction = { value, low, high, source: "model" as const, interval_reliable: low !== null, interval_message: null, validation_label: "", coverage: 0.8, mae: 0.05 };
  const evidence: RecommendationItem["evidence"] = source === "measured" ? "measured" : low !== null ? "interval" : "margin";
  return {
    key,
    ref: key,
    diagnostic: { expressibility: 0.1, entangling_capability: 0.5, gradient_mean_variance: 0.01, n_parameters: nParameters, n_two_qubit_gates: 3 },
    prediction: { final_tvd: prediction, degradation: null, noisy_tvd: null },
    measured: source === "measured" ? { run_id: 7, tvd: value, noisy_tvd: null } : null,
    value,
    low,
    high,
    source,
    evidence,
    margin,
    interval_message: null,
  };
}

function result(items: RecommendationItem[], decision: Partial<RecommendationResult["decision"]>): RecommendationResult {
  return {
    n_qubits: 4,
    layers: 2,
    noise_profile: null,
    topology: "line",
    budget: 400,
    classical: { best: "chow_liu", best_tvd: 0.1, baselines: { independent: { tvd: 0.3, n_parameters: 4 }, chow_liu: { tvd: 0.1, n_parameters: 7 } } },
    items,
    decision: {
      ranking: items.map((i) => i.key),
      best: items[0].key,
      evidence: items[0].evidence,
      indistinguishable: [],
      verdict: "undetermined",
      to_train: [],
      n_trainings: 2,
      ...decision,
    },
  };
}

describe("recommandation", () => {
  it("liste entre guillemets", () => {
    expect(quotedList(["A"])).toBe("« A »");
    expect(quotedList(["A", "B"])).toBe("« A » et « B »");
    expect(quotedList(["A", "B", "C"])).toBe("« A », « B » et « C »");
  });

  it("le quantique se justifie", () => {
    const r = result([item("hardware_efficient", 0.05, 0.02, 0.08), item("rotation_only", 0.3, 0.25, 0.35)], { verdict: "justified" });
    expect(recommendationSentences(r)).toEqual([
      "Le quantique se justifie sur ce problème : la borne haute de « HardwareEfficient » (TVD 0,0800) est sous la meilleure TVD classique (0,1000, arbre de Chow-Liu).",
    ]);
  });

  it("le quantique ne se justifie pas, avec des indistinguables, sous bruit", () => {
    const r = result([item("hardware_efficient", 0.3, 0.2, 0.4), item("brick_wall", 0.32, 0.25, 0.45)], {
      verdict: "not_justified",
      indistinguishable: ["brick_wall"],
    });
    r.noise_profile = { p1: 0.01, p2: 0.02, readout: 0.05 };
    expect(recommendationSentences(r)).toEqual([
      "« HardwareEfficient » et « BrickWall » sont indistinguables : leurs intervalles se recouvrent.",
      "Le quantique ne se justifie pas : la borne basse de « HardwareEfficient » (TVD sous bruit 0,2000) est au-dessus de la meilleure TVD classique (0,1000, arbre de Chow-Liu).",
    ]);
  });

  it("cas réel : valeur mesurée équivalente au classique (0,0585 contre 0,0588)", () => {
    const r = result([item("hardware_efficient", 0.0585, null, null, "measured", null, 16), item("rotation_only", 0.3, 0.25, 0.35)], {
      verdict: "equivalent",
    });
    r.classical = { best: "chow_liu", best_tvd: 0.0588, baselines: { independent: { tvd: 0.3, n_parameters: 4 }, chow_liu: { tvd: 0.0588, n_parameters: 7 } } };
    const sentences = recommendationSentences(r);
    expect(sentences).toEqual([
      "Équivalent au classique (écart inférieur à 10 %) : le quantique n'apporte rien sur ce problème. « HardwareEfficient » atteint une TVD mesurée de 0,0585 avec 16 paramètres, la meilleure référence classique (arbre de Chow-Liu) 0,0588 avec 7 paramètres.",
    ]);
    expect(sentences.join(" ")).not.toContain("borne");
  });

  it("valeur mesurée : justifié et non justifié, sans parler de borne", () => {
    const justified = result([item("hardware_efficient", 0.05, null, null, "measured", null, 16), item("rotation_only", 0.3, 0.25, 0.35)], { verdict: "justified" });
    expect(recommendationSentences(justified)).toEqual([
      "Le quantique se justifie sur ce problème : « HardwareEfficient » atteint une TVD mesurée de 0,0500, plus de 10 % sous la meilleure TVD classique (0,1000, arbre de Chow-Liu ; 16 paramètres pour l'ansatz, 7 pour la référence).",
    ]);
    const not = result([item("hardware_efficient", 0.2, null, null, "measured", null, 16), item("rotation_only", 0.3, 0.25, 0.35)], { verdict: "not_justified" });
    expect(recommendationSentences(not)[0]).toBe(
      "Le quantique ne se justifie pas : « HardwareEfficient » atteint une TVD mesurée de 0,2000, plus de 10 % au-dessus de la meilleure TVD classique (0,1000, arbre de Chow-Liu ; 16 paramètres pour l'ansatz, 7 pour la référence).",
    );
  });

  it("valeur prédite sans intervalle : verdicts probables avec la marge", () => {
    const probable = result([item("hardware_efficient", 0.05, null, null, "model", 0.03), item("rotation_only", 0.3, 0.25, 0.35)], { verdict: "probably_justified" });
    expect(recommendationSentences(probable)).toEqual([
      "Le quantique se justifie probablement sur ce problème : la TVD prédite de « HardwareEfficient » (0,0500), même augmentée de deux fois l'erreur moyenne de validation (0,0300), reste sous la meilleure TVD classique (0,1000, arbre de Chow-Liu).",
    ]);
    const improbable = result([item("hardware_efficient", 0.2, null, null, "model", 0.04), item("rotation_only", 0.3, null, null, "model", 0.04)], {
      verdict: "probably_not_justified",
    });
    expect(recommendationSentences(improbable)[0]).toBe(
      "Le quantique ne se justifie probablement pas : la TVD prédite de « HardwareEfficient » (0,2000), même diminuée de deux fois l'erreur moyenne de validation (0,0400), reste au-dessus de la meilleure TVD classique (0,1000, arbre de Chow-Liu).",
    );
  });

  it("indéterminé : ansatz à entraîner", () => {
    const r = result([item("hardware_efficient", 0.08, 0.02, 0.2), item("brick_wall", 0.09, 0.03, 0.25)], {
      indistinguishable: ["brick_wall"],
      to_train: ["hardware_efficient", "brick_wall"],
    });
    expect(recommendationSentences(r)[1]).toBe("Indéterminé : entraînez « HardwareEfficient » et « BrickWall » pour trancher.");
    expect(recommendationSentences({ ...r, decision: { ...r.decision, to_train: [] } })[1]).toBe(
      "Indéterminé : aucun entraînement supplémentaire ne permet de trancher.",
    );
  });
});


describe("écran et rapport de recommandation", () => {
  afterEach(() => vi.unstubAllGlobals());

  const FORM: RecommendationForm = { problem: 1, ansatz: ["cat:a", "cat:b"], layers: 2, noise: NO_NOISE_CHOICE, topology: "line", budget: 400 };
  const OPTIONS = [
    { value: "cat:a", label: "A", ref: "a", fixedQubits: null },
    { value: "cat:b", label: "B", ref: "b", fixedQubits: null },
    { value: "custom:3", label: "Q (personnalisé, 5 qubits)", ref: { custom_id: 3 }, fixedQubits: 5 },
  ];

  it("validation du formulaire", () => {
    expect(recommendationErrors(FORM, 4, OPTIONS)).toEqual({});
    expect(recommendationErrors({ ...FORM, ansatz: ["cat:a"] }, 4, OPTIONS).ansatz).toBe("Choisissez de 2 à 7 ansatz.");
    expect(recommendationErrors({ ...FORM, budget: 100 }, 4, OPTIONS).budget).toBe("Budget : entier de 200 à 7000 itérations.");
    expect(recommendationErrors({ ...FORM, ansatz: ["cat:a", "custom:3"] }, 4, OPTIONS).ansatz).toBe(
      "Q (personnalisé, 5 qubits) : nombre de qubits différent de celui du problème (4).",
    );
    expect(recommendationErrors({ ...FORM, problem: null }, null, OPTIONS).problem).toBeDefined();
  });

  it("intervalle : bornes, mesure ou message", () => {
    expect(intervalText(item("a", 0.1, 0.05, 0.2))).toBe("[0,0500 ; 0,2000]");
    expect(intervalText(item("a", 0.1, 0.1, 0.1, "measured"))).toBe("mesure, sans intervalle");
    expect(intervalText({ ...item("a", 0.1, null, null, "model", 0.06), interval_message: "Intervalle non fiable pour ce cas : couverture mesurée 52,4 %." })).toBe(
      "Intervalle non fiable pour ce cas : couverture mesurée 52,4 %. Marge retenue : ± 0,0600 (deux fois l'erreur moyenne de validation).",
    );
  });

  it("tableau : ordre du classement, source mesurée et références classiques", () => {
    const r = result([item("rotation_only", 0.3, 0.25, 0.35), item("hardware_efficient", 0.05, 0.05, 0.05, "measured")], {
      ranking: ["hardware_efficient", "rotation_only"],
      best: "hardware_efficient",
    });
    render(<RankingTable result={r} />);
    const rows = screen.getAllByRole("row");
    expect(within(rows[1]).getByText("HardwareEfficient")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Entraînement mesuré (run n° 7)")).toBeInTheDocument();
    expect(within(rows[2]).getByText("RotationOnly")).toBeInTheDocument();
    expect(screen.getByText("Référence classique : arbre de Chow-Liu")).toBeInTheDocument();
  });

  it("rapport imprimable : verdict, classement et exports", async () => {
    const r = result([item("hardware_efficient", 0.05, 0.02, 0.08), item("rotation_only", 0.3, 0.25, 0.35)], { verdict: "justified" });
    const run = { id: 12, project_id: 1, kind: "recommendation", status: "done", params: { problem_name: "Gauss" }, result: r, error: null, created_by: 1, created_at: "2026-11-08T09:00:00", started_at: null, finished_at: "2026-11-08T09:01:00" };
    vi.stubGlobal("fetch", vi.fn(() => Promise.resolve(new Response(JSON.stringify(run), { status: 200 }))));
    const project: Project = { id: 1, name: "Démo", slug: "demo", description: "", share_results: false, created_by: 1, created_at: "", role: "viewer" };
    render(
      <MemoryRouter initialEntries={["/projects/1/rapport?run=12"]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ProjectContextProvider value={{ project, permissions: DEFAULT_PERMISSIONS, can: (a) => can("viewer", a), reason: (a) => deniedReason(a), reload: () => {} }}>
          <ReportPage />
        </ProjectContextProvider>
      </MemoryRouter>,
    );
    expect(await screen.findByRole("heading", { name: "Rapport de recommandation" })).toBeInTheDocument();
    expect(screen.getByText(/Le quantique se justifie sur ce problème/)).toBeInTheDocument();
    expect(screen.getByText(/Problème « Gauss » : 4 qubits/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Imprimer" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Exporter en JSON" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /CSV/ })).toBeEnabled();
  });
});
