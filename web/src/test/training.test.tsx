import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LossChart } from "../components/charts";
import { trainingSentence, type TrainingResult } from "../lib/reading";
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

const FORM: TrainingForm = { problem: 1, ansatz: "cat:hardware_efficient", layers: 2, loss: "kl", optimizer: "adam", max_iter: 200, learning_rate: 0.1, exact: true, shots: 1000, seed: 0 };

describe("entraînement", () => {
  it("phrase : l'ansatz fait mieux que les références", () => {
    const s = trainingSentence(result(0.01, 0.05), null);
    expect(s).toBe(
      "Après 200 itérations (perte KL, Adam), l'ansatz atteint une TVD de 0,0100 avec 8 paramètres. " +
        "Il fait mieux que les deux références classiques ; la meilleure (arbre de Chow-Liu, 3 paramètres) atteint 0,0500. " +
        "Une seule initialisation, en simulation exacte sans bruit.",
    );
  });

  it("phrase : une référence classique fait mieux", () => {
    const s = trainingSentence(result(0.2, 0.05), 1000);
    expect(s).toContain("La référence classique « arbre de Chow-Liu » fait mieux : TVD de 0,0500 avec 3 paramètres.");
    expect(s).toContain("1000 tirages par évaluation");
  });

  it("phrase : égalité à 0,0001 près", () => {
    expect(trainingSentence(result(0.05, 0.05005), null)).toContain("atteint la même TVD à 0,0001 près");
  });

  it("validation du formulaire", () => {
    expect(trainingErrors(FORM, 2, null)).toEqual({});
    expect(trainingErrors({ ...FORM, loss: "tvd" }, 2, null).optimizer).toBe("La TVD n'est pas dérivable : choisissez SPSA ou COBYLA.");
    expect(trainingErrors({ ...FORM, max_iter: 9 }, 2, null).max_iter).toBeDefined();
    expect(trainingErrors({ ...FORM, exact: false, shots: 50 }, 2, null).shots).toBeDefined();
    expect(trainingErrors({ ...FORM, problem: null }, null, null).problem).toBeDefined();
    expect(trainingErrors(FORM, 2, 3).ansatz).toBe("Cet ansatz fixe 3 qubits, le problème en a 2.");
  });

  it("courbe de perte en échelle log, graduations françaises", () => {
    const { container } = render(<LossChart width={600} history={[0.8, 0.2, 0.05, 0.004, 0]} />);
    expect(container.querySelector(".recharts-line-curve")).toBeInTheDocument();
    expect(screen.getByText("0,01")).toBeInTheDocument();
    expect(screen.getByText("0,1")).toBeInTheDocument();
  });
});
