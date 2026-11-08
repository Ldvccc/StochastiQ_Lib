import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { bitstring, DistributionChart } from "../components/charts";
import { describeEvent } from "../lib/activity";
import { parseRanges } from "../pages/ProblemsPage";

describe("problèmes", () => {
  it("chaînes de bits little-endian, qubit n-1 à gauche", () => {
    expect(bitstring(1, 2)).toBe("01");
    expect(bitstring(6, 3)).toBe("110");
  });

  it("histogramme d'une distribution : une barre par état", () => {
    const { container } = render(<DistributionChart width={600} probabilities={[0.25, 0, 0, 0.75]} />);
    expect(container.querySelectorAll(".recharts-bar-rectangle")).toHaveLength(4);
    const ticks = [...container.querySelectorAll(".recharts-xAxis .recharts-cartesian-axis-tick-value")].map((t) => t.textContent);
    expect(ticks).toEqual(["00", "01", "10", "11"]);
  });

  it("au-delà de 4 qubits, les étiquettes d'états sont remplacées par le nombre d'états", () => {
    render(<DistributionChart width={600} probabilities={Array(32).fill(1 / 32)} />);
    expect(screen.getByText("32 états (qubit n-1 à gauche)")).toBeInTheDocument();
  });

  it("lecture des intervalles min:max", () => {
    expect(parseRanges("0:10; 0:4")).toEqual({ ranges: [[0, 10], [0, 4]] });
    expect(parseRanges("0,5:1,5")).toEqual({ ranges: [[0.5, 1.5]] });
    expect(parseRanges("")).toEqual({ error: "Indiquez au moins un intervalle « min:max »." });
    expect(parseRanges("1:1")).toEqual({ error: "Intervalle vide : « 1:1 » (max doit dépasser min)." });
    expect(parseRanges("a:b")).toEqual({ error: "Intervalle invalide : « a:b »." });
  });

  it("événement problem_added", () => {
    const text = describeEvent({
      id: 1,
      type: "problem_added",
      user: { id: 1, name: "Ada" },
      payload: { problem_id: 3, name: "Prix", n_qubits: 4, origin: "csv" },
      created_at: "2026-11-08T00:00:00",
    });
    expect(text).toBe("Ada a ajouté le problème « Prix » (4 qubits, fichier CSV).");
  });
});
