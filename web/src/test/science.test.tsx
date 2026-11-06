import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Project } from "../api/types";
import { FidelityHistogram, ParetoScatter, ScalingChart } from "../components/charts";
import { CircuitSvg, type Structure } from "../components/CircuitSvg";
import { ProjectContextProvider } from "../components/ProjectContext";
import { can, deniedReason, DEFAULT_PERMISSIONS } from "../lib/roles";
import type { CompareRow } from "../lib/reading";
import { DiagnosticPage, validateDiagnostic } from "../pages/DiagnosticPage";

afterEach(() => vi.unstubAllGlobals());

describe("graphiques sur données synthétiques", () => {
  it("histogramme des fidélités : barres du circuit et courbe de Haar", () => {
    const { container } = render(
      <FidelityHistogram width={600} histogram={{ edges: [0, 0.25, 0.5, 0.75, 1], circuit: [0.4, 0.3, 0.2, 0.1], haar: [0.5, 0.3, 0.15, 0.05] }} />,
    );
    expect(container.querySelectorAll(".recharts-bar-rectangle")).toHaveLength(4);
    expect(container.querySelector(".recharts-line-curve")).toHaveAttribute("stroke", "#d42a45");
    expect(screen.getByText("Référence de Haar")).toBeInTheDocument();
  });

  it("nuage de Pareto : un point par ansatz, étiquettes, deux séries", () => {
    const rows: CompareRow[] = [
      { ansatz: "all_to_all", expressibility: 0.01, entangling_capability: 0.8, gradient_variance: 0.02, gradient_variance_active: 0.05, inactive_fraction: 0.2, pareto: true },
      { ansatz: "brick_wall", expressibility: 0.03, entangling_capability: 0.6, gradient_variance: 0.03, gradient_variance_active: 0.04, inactive_fraction: 0.7, pareto: false },
    ];
    const { container } = render(<ParetoScatter width={600} rows={rows} />);
    expect(container.querySelectorAll(".recharts-scatter-symbol")).toHaveLength(2);
    expect(screen.getByText("AllToAll")).toBeInTheDocument();
    expect(screen.getByText("Front de Pareto")).toBeInTheDocument();
    expect(screen.getByText("Autres")).toBeInTheDocument();
  });

  it("courbes en échelle log : graduations françaises, trait plein et pointillé", () => {
    const data = (values: number[]) => values.map((value, i) => ({ n_qubits: i + 2, value }));
    const { container } = render(
      <ScalingChart
        width={700}
        lines={[
          { key: "a", name: "HardwareEfficient", color: "#5b4bff", marker: "circle", dash: "solid", data: data([0.11, 0.07, 0.065]) },
          { key: "b", name: "HardwareEfficient (tous)", color: "#5b4bff", marker: "circle", dash: "dashed", data: data([0.08, 0.04, 0.003]) },
        ]}
        legend={[
          { label: "Trait plein : paramètres actifs", dash: "solid" },
          { label: "Pointillé : tous les paramètres", dash: "dashed" },
        ]}
      />,
    );
    const curves = container.querySelectorAll(".recharts-line-curve");
    expect(curves).toHaveLength(2);
    expect(curves[1]).toHaveAttribute("stroke-dasharray", "6 4");
    expect(screen.getByText("0,01")).toBeInTheDocument();
    expect(screen.getByText("0,1")).toBeInTheDocument();
    expect(screen.getByText("Pointillé : tous les paramètres")).toBeInTheDocument();
  });

  it("schéma de circuit en SVG", () => {
    const structure: Structure = {
      n_qubits: 3,
      layers: 1,
      columns: [
        { gates: [0, 1, 2].map((q) => ({ type: "RY" as const, qubits: [q], param_index: q })) },
        { gates: [{ type: "CNOT", qubits: [0, 1], param_index: null }] },
        { gates: [{ type: "CNOT", qubits: [1, 2], param_index: null }] },
      ],
    };
    const { container } = render(<CircuitSvg structure={structure} label="HardwareEfficient" />);
    expect(screen.getByRole("img")).toHaveAccessibleName("HardwareEfficient : 3 qubits, 1 couches, 3 rotations et 2 CNOT");
    expect(container.querySelectorAll('[data-gate="RY"]')).toHaveLength(3);
    expect(container.querySelectorAll('[data-gate="CNOT"]')).toHaveLength(2);
  });
});

describe("formulaire de diagnostic", () => {
  const base = { ansatz: "hardware_efficient", n_qubits: 4, layers: 3, n_samples: 1000, seed: 0, observable: "Z0" as const };

  it("bornes de validation", () => {
    expect(validateDiagnostic(base)).toEqual({});
    expect(Object.keys(validateDiagnostic({ ...base, n_qubits: 1, layers: 9, n_samples: 49, seed: -1 })).sort()).toEqual([
      "layers",
      "n_qubits",
      "n_samples",
      "seed",
    ]);
    expect(validateDiagnostic({ ...base, n_qubits: 8, layers: 8, n_samples: 5000 })).toEqual({});
    expect(validateDiagnostic({ ...base, n_samples: 5001 }).n_samples).toBe("Échantillons : entier de 50 à 5 000.");
    expect(validateDiagnostic({ ...base, n_qubits: 3.5 }).n_qubits).toBeDefined();
  });

  function renderPage(role: Project["role"]) {
    vi.stubGlobal(
      "fetch",
      vi.fn(() =>
        Promise.resolve(
          new Response(JSON.stringify([{ name: "hardware_efficient", label: "HardwareEfficient", description: "", parameters: "2·L·n" }]), {
            status: 200,
          }),
        ),
      ),
    );
    const project: Project = { id: 1, name: "P", slug: "p", description: "", created_by: 1, created_at: "", role };
    render(
      <MemoryRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
        <ProjectContextProvider
          value={{ project, permissions: DEFAULT_PERMISSIONS, can: (a) => can(role, a), reason: (a) => deniedReason(a), reload: () => {} }}
        >
          <DiagnosticPage />
        </ProjectContextProvider>
      </MemoryRouter>,
    );
  }

  it("valeur hors bornes : message d'erreur et lancement désactivé", async () => {
    renderPage("editor");
    const button = await screen.findByRole("button", { name: "Diagnostiquer" });
    await screen.findByRole("option", { name: "HardwareEfficient" });
    expect(button).toBeEnabled();
    const qubits = screen.getByLabelText(/^Qubits/);
    await userEvent.clear(qubits);
    await userEvent.type(qubits, "9");
    expect(screen.getByText("Qubits : entier de 2 à 8.")).toBeInTheDocument();
    expect(qubits).toHaveAttribute("aria-invalid", "true");
    expect(button).toBeDisabled();
  });

  it("avertissement sous 1000 échantillons", async () => {
    renderPage("editor");
    const samples = await screen.findByLabelText(/^Échantillons/);
    await userEvent.clear(samples);
    await userEvent.type(samples, "500");
    expect(screen.getByText(/l'expressibilité est surestimée/)).toBeInTheDocument();
  });

  it("un lecteur voit le bouton désactivé avec la raison", async () => {
    renderPage("viewer");
    const button = await screen.findByRole("button", { name: "Diagnostiquer" });
    expect(button).toBeDisabled();
    expect(button).toHaveAccessibleDescription("Réservé au rôle « Éditeur » ou supérieur.");
    expect(within(screen.getByRole("form", { name: "Paramètres du diagnostic" })).getByLabelText("Observable")).toBeInTheDocument();
  });
});
