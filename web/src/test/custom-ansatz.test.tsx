import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CircuitSvg } from "../components/CircuitSvg";
import { csvParams, toCsv } from "../lib/csv";
import { refLabel } from "../lib/reading";
import { parsePairs } from "../pages/CustomAnsatzPage";

describe("ansatz du client", () => {
  it("lecture des CNOT contrôle-cible", () => {
    expect(parsePairs("0-1; 1-2")).toEqual({ pairs: [[0, 1], [1, 2]] });
    expect(parsePairs("")).toEqual({ error: "Indiquez au moins un CNOT « contrôle-cible »." });
    expect(parsePairs("1-1")).toEqual({ error: "CNOT invalide : « 1-1 » (contrôle et cible distincts)." });
    expect(parsePairs("0,1")).toEqual({ error: "CNOT invalide : « 0,1 » (forme « 0-1 » attendue)." });
  });

  it("libellé d'une référence d'ansatz", () => {
    expect(refLabel("hardware_efficient")).toBe("HardwareEfficient");
    expect(refLabel({ custom: { id: 3, name: "Mon circuit", format: "qasm", content: "...", n_qubits: 3 } })).toBe("Mon circuit (personnalisé)");
    expect(refLabel({ custom_id: 4 })).toBe("Ansatz personnalisé n° 4");
  });

  it("le commentaire CSV remplace l'ansatz complet par son libellé et tient sur une ligne", () => {
    const params = csvParams({ ansatz: { custom: { name: "QASM", content: "OPENQASM 3.0;\nqubit[2] q;" } }, n_qubits: 2 });
    expect(params.ansatz).toBe("QASM (personnalisé)");
    const csv = toCsv([{ a: 1 }], { note: "ligne 1\nligne 2", ...params });
    expect(csv.split("\n")[0]).toBe("# note=ligne 1 ligne 2; ansatz=QASM (personnalisé); n_qubits=2; version=0.3.0");
    expect(csvParams({ ansatz: ["brick_wall", { custom: { name: "B" } }] }).ansatz).toBe("BrickWall + B (personnalisé)");
  });

  it("schéma SVG d'un circuit quelconque : portes fixes et portes à plusieurs qubits", () => {
    const { container } = render(
      <CircuitSvg
        label="QASM"
        structure={{
          n_qubits: 3,
          columns: [
            { gates: [{ type: "RY", qubits: [0], param_index: 0 }, { type: "H", qubits: [1], param_index: null }] },
            { gates: [{ type: "CZ", qubits: [0, 2], param_index: null }] },
          ],
        }}
      />,
    );
    expect(screen.getByRole("img")).toHaveAccessibleName("QASM : 3 qubits, 1 rotation, 0 CNOT et 2 autres portes");
    expect(container.querySelectorAll('[data-gate="CZ"] rect')).toHaveLength(2);
    expect(container.querySelector('[data-gate="H"] rect')).toHaveAttribute("fill", "#14163f");
  });
});
