// Mêmes cas que tests/test_dashboard.py pour les règles de lecture du dashboard Streamlit.
import { describe, expect, it } from "vitest";

import { toCsv } from "../lib/csv";
import {
  compareSentence,
  DILUTION_SENTENCE,
  layersLine,
  LOCAL_VS_GLOBAL_SENTENCE,
  logTickLabel,
  logTicks,
  observablesSentence,
  paretoSentence,
  scalingSentence,
  type CompareRow,
  type Fit,
} from "../lib/reading";

function rows(expr: number[], ent: number[], std?: number): CompareRow[] {
  return expr.map((e, i) => ({
    ansatz: `c${i}`,
    expressibility: e,
    entangling_capability: ent[i],
    gradient_variance: 0.03,
    gradient_variance_active: 0.05,
    inactive_fraction: 0.25,
    pareto: false,
    ...(std === undefined ? {} : { expressibility_std: std, entangling_capability_std: std }),
  }));
}

describe("phrase du Comparateur", () => {
  it("une graine, écart net", () => {
    const s = compareSentence(rows([0.01, 0.05, 0.2], [0.5, 0.9, 0.6]));
    expect(s).toContain("Le circuit le plus expressif est « c0 »");
    expect(s).toContain("La plus forte intrication est obtenue par « c1 »");
    expect(s).toContain("0,0100");
    expect(s).not.toContain("bruit");
    expect(s).not.toContain("graines");
  });

  it("une graine, écart flou", () => {
    const s = compareSentence(rows([0.1, 0.105, 0.3], [0.8, 0.78, 0.5]));
    expect(s).not.toContain("plus expressif");
    expect(s).not.toContain("plus forte intrication");
    expect(s.match(/du même ordre que le bruit d'échantillonnage/g)).toHaveLength(2);
    expect(s).toContain("relancez avec plusieurs graines");
  });

  it("plusieurs graines, gagnant net", () => {
    const s = compareSentence(rows([0.01, 0.05], [0.9, 0.6], 0.005));
    expect(s).toContain("Le circuit le plus expressif est « c0 »");
    expect(s).toContain("La plus forte intrication est obtenue par « c0 »");
    expect(s).toContain("Valeurs moyennes sur les graines.");
  });

  it("plusieurs graines, égalité", () => {
    const s = compareSentence(rows([0.01, 0.02], [0.8, 0.79], 0.01));
    expect(s).not.toContain("plus expressif");
    expect(s.match(/indistinguables sur cette métrique/g)).toHaveLength(2);
  });

  it("moins de deux circuits", () => {
    expect(compareSentence([])).toBe("");
    expect(compareSentence(rows([0.01], [0.5]))).toBe("");
  });
});

describe("phrase du front de Pareto", () => {
  it("un seul ansatz", () => {
    const data = rows([0.01, 0.03], [0.5, 0.5]).map((r, i) => ({ ...r, ansatz: ["all_to_all", "brick_wall"][i], pareto: i === 0 }));
    const s = paretoSentence(data);
    expect(s.startsWith("Le front de Pareto ne contient que « AllToAll ».")).toBe(true);
    expect(s).toContain("Un circuit du front n'est battu par aucun autre sur les deux critères");
  });

  it("plusieurs ansatz, sans aucune valeur chiffrée", () => {
    const names = ["all_to_all", "brick_wall", "rotation_only"];
    const s = paretoSentence(rows([0.01, 0.03, 0.7], [0.5, 0.5, 0.5]).map((r, i) => ({ ...r, ansatz: names[i], pareto: true })));
    expect(s).toContain("« AllToAll », « BrickWall » et « RotationOnly »");
    expect(/\d/.test(s)).toBe(false);
  });
});

const fit = (factor: number | null, r2: number | null): Fit => ({ factor_per_qubit: factor, r2, n_points: factor === null ? 2 : 5 });

describe("phrase du plateau stérile", () => {
  it("décroissance nette", () => {
    const s = scalingSentence("data_reuploading", fit(0.5, 0.99), fit(0.45, 0.99));
    expect(s).toContain("paramètres actifs : la variance est multipliée par 0,50 à chaque qubit ajouté");
    expect(s).toContain("R² = 0,990");
    expect(s).toContain("plateau stérile sur cette plage de qubits, avec cette observable");
    expect(s).not.toContain(DILUTION_SENTENCE);
  });

  it.each([
    [fit(0.9, 0.99), fit(0.85, 0.99)],
    [fit(0.5, 0.6), fit(0.5, 0.99)],
  ])("décroissance non nette", (active, all) => {
    const s = scalingSentence("data_reuploading", active, all);
    expect(s).toContain("pas de décroissance exponentielle nette sur cette plage");
    expect(s).not.toContain("plateau stérile");
  });

  it("dilution", () => {
    const s = scalingSentence("hardware_efficient", fit(0.95, 0.4), fit(0.72, 0.91));
    expect(s).toContain("Sur tous les paramètres, le facteur est 0,72.");
    expect(s.endsWith(DILUTION_SENTENCE)).toBe(true);
    expect(s).not.toContain("plateau stérile");
  });

  it("pas de dilution si la moyenne globale décroît moins vite", () => {
    expect(scalingSentence("data_reuploading", fit(0.4, 0.99), fit(0.6, 0.99))).not.toContain(DILUTION_SENTENCE);
  });

  it("données insuffisantes", () => {
    expect(scalingSentence("brick_wall", fit(null, null), fit(null, null))).toContain("données insuffisantes");
  });

  it("rappel du mode de couches", () => {
    expect(layersLine("fixed", 3)).toBe("Couches : 3 (fixe).");
    expect(layersLine("linear", 3)).toBe("Couches : égales au nombre de qubits.");
  });
});

describe("phrase local contre global", () => {
  it("hardware_efficient : plat en local, décroissant en global", () => {
    const s = observablesSentence("hardware_efficient", fit(0.904, 0.491), fit(0.531, 0.983));
    expect(s.startsWith("« HardwareEfficient », paramètres actifs : facteur par qubit 0,90 en local")).toBe(true);
    expect(s.endsWith(LOCAL_VS_GLOBAL_SENTENCE)).toBe(true);
  });

  it.each([
    [fit(0.6, 0.97), fit(0.5, 0.99), "nette avec les deux coûts"],
    [fit(0.6, 0.97), fit(0.9, 0.99), "avec le coût local seulement"],
    [fit(0.95, 0.5), fit(0.85, 0.99), "ni en local ni en global"],
  ])("autres cas", (local, global, expected) => {
    const s = observablesSentence("data_reuploading", local, global);
    expect(s).toContain(expected);
    expect(s).not.toContain(LOCAL_VS_GLOBAL_SENTENCE);
  });

  it("données insuffisantes", () => {
    expect(observablesSentence("brick_wall", fit(null, null), fit(0.5, 0.99))).toContain("données insuffisantes");
  });
});

describe("axe logarithmique", () => {
  it("plusieurs décades", () => {
    expect(logTicks(0.0004, 0.12)).toEqual([0.001, 0.01, 0.1]);
  });

  it.each([
    [0.02, 0.08],
    [0.03, 0.03],
    [0.005, 0.05],
    [1.5e-6, 4e-6],
  ])("au moins deux graduations consécutives (%s, %s)", (vmin, vmax) => {
    const ticks = logTicks(vmin, vmax);
    expect(ticks.length).toBeGreaterThanOrEqual(2);
    ticks.slice(1).forEach((t, i) => expect(t / ticks[i]).toBeCloseTo(10));
  });

  it("valeurs non positives refusées", () => {
    expect(() => logTicks(0, 0.1)).toThrow();
    expect(() => logTicks(-1, 0.1)).toThrow();
  });

  it("étiquettes françaises", () => {
    expect([1, 0.1, 0.01, 0.0001].map(logTickLabel)).toEqual(["1", "0,1", "0,01", "0,0001"]);
    expect(logTickLabel(1e-5)).toBe("1e-5");
    expect(logTickLabel(1.5e-5)).toBe("1,5e-5");
  });
});

describe("export CSV", () => {
  it("ligne de commentaire, virgule séparatrice, point décimal", () => {
    const csv = toCsv([{ ansatz: "brick_wall", value: 0.5 }, { ansatz: "a,b", value: 1.25 }], { qubits: 4, graine: 0 });
    expect(csv.split("\n")).toEqual(["# qubits=4; graine=0; version=0.3.0", "ansatz,value", "brick_wall,0.5", '"a,b",1.25', ""]);
  });
});
