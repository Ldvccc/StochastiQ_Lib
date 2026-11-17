import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LossChart } from "../components/charts";
import { NO_NOISE_CHOICE, NoiseProfileField } from "../components/science";
import { degradationSentence, noiseEvaluationSentence, profileLabel, trainingSentence, type TrainingResult } from "../lib/reading";
import { trainingErrors, type TrainingForm } from "../pages/TrainingPage";

function result(tvd: number, chowLiu: number): TrainingResult {
  const metrics = (t: number) => ({ kl: t, tvd: t, hellinger: t });
  return {
    history: [1, 0.5, 0.1],
    metrics: metrics(tvd),
    n_parameters: 8,
    n_iterations: 200,
    loss: "kl",
    optimizer: "adam",
    probabilities: [0.25, 0.25, 0.25, 0.25],
    baselines: {
      independent: { probabilities: [], metrics: metrics(0.3), n_parameters: 2 },
      chow_liu: { probabilities: [], metrics: metrics(chowLiu), n_parameters: 3 },
    },
  };
}

const FORM: TrainingForm = { problem: 1, ansatz: "cat:hardware_efficient", layers: 2, loss: "kl", optimizer: "adam", max_iter: 200, learning_rate: 0.1, exact: true, shots: 1000, seed: 0, noise: NO_NOISE_CHOICE, noiseTopology: "line" };

describe("entraînement", () => {
  it("phrase : l'ansatz fait mieux que les références", () => {
    const s = trainingSentence(result(0.01, 0.05), null);
    expect(s).toBe(
      "Après 200 itérations (perte KL, Adam), l'ansatz atteint une TVD de 0,0100 avec 8 paramètres. " +
        "Il fait mieux que les deux références classiques, de plus de 10 % ; la meilleure (arbre de Chow-Liu, 3 paramètres) atteint 0,0500. " +
        "Une seule initialisation, en simulation exacte sans bruit.",
    );
  });

  it("phrase : une référence classique fait mieux", () => {
    const s = trainingSentence(result(0.2, 0.05), 1000);
    expect(s).toContain("La référence classique « arbre de Chow-Liu » fait mieux : TVD de 0,0500 avec 3 paramètres.");
    expect(s).toContain("1000 tirages par évaluation");
  });

  it("phrase : équivalence sous 10 % d'écart, dont le cas réel 0,0585 contre 0,0588", () => {
    const s = trainingSentence(result(0.0585, 0.0588), null);
    expect(s).toContain(
      "Équivalent à la meilleure référence classique (écart inférieur à 10 %) : « arbre de Chow-Liu » atteint 0,0588 avec 3 paramètres, contre 8 pour l'ansatz.",
    );
    expect(s).not.toContain("fait mieux");
    expect(trainingSentence(result(0.0529, 0.0588), null)).toContain("Il fait mieux"); // 0,0529 < 0,9 × 0,0588
    expect(trainingSentence(result(0.065, 0.0588), null)).toContain("fait mieux : TVD de 0,0588"); // 0,065 > 1,1 × 0,0588
  });

  it("validation du formulaire", () => {
    expect(trainingErrors(FORM, 2, null)).toEqual({});
    expect(trainingErrors({ ...FORM, loss: "tvd" }, 2, null).optimizer).toBe("La TVD n'est pas dérivable : choisissez SPSA ou COBYLA.");
    expect(trainingErrors({ ...FORM, max_iter: 9 }, 2, null).max_iter).toBeDefined();
    expect(trainingErrors({ ...FORM, exact: false, shots: 50 }, 2, null).shots).toBeDefined();
    expect(trainingErrors({ ...FORM, problem: null }, null, null).problem).toBeDefined();
    expect(trainingErrors(FORM, 2, 3).ansatz).toBe("Cet ansatz fixe 3 qubits, le problème en a 2.");
  });

  it("taux personnalisés validés entre 0 et 0,5", () => {
    const custom = { mode: "custom" as const, rates: { p1: 0.6, p2: 0.01, readout: NaN } };
    const errors = trainingErrors({ ...FORM, noise: custom }, 2, null);
    expect(errors.p1).toBe("Taux entre 0 et 0,5.");
    expect(errors.readout).toBe("Taux entre 0 et 0,5.");
    expect(errors.p2).toBeUndefined();
    expect(trainingErrors({ ...FORM, noise: { ...custom, mode: "fort" } }, 2, null)).toEqual({});
  });

  it("phrases du bruit", () => {
    expect(profileLabel("fort")).toBe("« fort »");
    expect(profileLabel({ p1: 0.001, p2: 0.01, readout: 0.02 })).toBe("personnalisé (p1 0,001 ; p2 0,01 ; lecture 0,02)");
    const trained = { ...result(0.01, 0.05), noise: { profile: "fort" as const, topology: "line" as const, probabilities: [], metrics: { kl: 0, tvd: 0.0821, hellinger: 0 } } };
    expect(noiseEvaluationSentence(trained)).toBe(
      "Avec les mêmes paramètres appris, sous le bruit « fort » (topologie ligne), la TVD passe de 0,0100 à 0,0821. " +
        "Les profils de bruit sont des ordres de grandeur, pas des calibrations de machines réelles.",
    );
    const noise = { mean_tvd: 0.1234, std_tvd: 0.02, tvds: Array(20).fill(0.1234), profile: { p1: 0.001, p2: 0.005, readout: 0.01 }, topology: "line" as const };
    expect(degradationSentence(noise, "moyen")).toContain("s'écarte en moyenne de 0,1234 en TVD de la sortie idéale (écart type 0,0200, 20 jeux de paramètres aléatoires)");
  });

  it("liste de bruit : les taux n'apparaissent qu'en mode personnalisé", () => {
    const { rerender } = render(<NoiseProfileField label="Bruit" choice={NO_NOISE_CHOICE} onChange={() => {}} errors={{}} />);
    expect(screen.getByRole("option", { name: "Fort (p1 0,01, p2 0,02, lecture 0,05)" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Erreur de lecture")).not.toBeInTheDocument();
    rerender(<NoiseProfileField label="Bruit" choice={{ ...NO_NOISE_CHOICE, mode: "custom" }} onChange={() => {}} errors={{ p2: "Taux entre 0 et 0,5." }} />);
    expect(screen.getByLabelText("Erreur de lecture")).toHaveValue(0.01);
    expect(screen.getByText("Taux entre 0 et 0,5.")).toBeInTheDocument();
  });

  it("courbe de perte en échelle log, graduations françaises", () => {
    const { container } = render(<LossChart width={600} history={[0.8, 0.2, 0.05, 0.004, 0]} />);
    expect(container.querySelector(".recharts-line-curve")).toBeInTheDocument();
    expect(screen.getByText("0,01")).toBeInTheDocument();
    expect(screen.getByText("0,1")).toBeInTheDocument();
  });
});
