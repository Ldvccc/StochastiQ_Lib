import { useState } from "react";

import { api } from "../api/client";
import { CircuitSvg, type Structure } from "../components/CircuitSvg";
import { ErrorState, Loading } from "../components/common";
import { NumberField, useAnsatzCatalog } from "../components/science";
import { boundErrors } from "../lib/runs";
import { useAsync } from "../lib/useAsync";

interface StructureWithStats extends Structure {
  stats: {
    n_qubits: number;
    n_parameters: number;
    depth: number;
    n_two_qubit_gates: number;
    gate_counts: Record<string, number>;
  };
}

export function AnsatzPage() {
  const catalog = useAnsatzCatalog();
  const [name, setName] = useState("hardware_efficient");
  const [nQubits, setNQubits] = useState(4);
  const [layers, setLayers] = useState(3);
  const errors = boundErrors({ n_qubits: nQubits, layers });
  const valid = Object.keys(errors).length === 0;
  const structure = useAsync(
    () => (valid ? api.get<StructureWithStats>(`/ansatz/${name}/structure?n_qubits=${nQubits}&layers=${layers}`) : Promise.reject(new Error("Paramètres invalides."))),
    [name, nQubits, layers],
  );
  const info = catalog.data?.find((a) => a.name === name);

  return (
    <>
      <h1>Ansatz</h1>
      <div className="card">
        {catalog.loading ? (
          <Loading />
        ) : catalog.error ? (
          <ErrorState message={catalog.error} onRetry={catalog.reload} />
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Ansatz</th>
                  <th scope="col">Description</th>
                  <th scope="col">Paramètres</th>
                </tr>
              </thead>
              <tbody>
                {catalog.data!.map((a) => (
                  <tr key={a.name} aria-selected={a.name === name}>
                    <td>
                      <button type="button" className={a.name === name ? "" : "secondary"} onClick={() => setName(a.name)}>
                        {a.label}
                      </button>
                    </td>
                    <td>{a.description}</td>
                    <td className="num">{a.parameters}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
      <section className="card" aria-labelledby="schema">
        <h2 id="schema">{info?.label ?? name}</h2>
        <div className="row" style={{ marginBottom: 16 }}>
          <NumberField label="Qubits" value={nQubits} min={2} max={8} onChange={setNQubits} error={errors.n_qubits} />
          <NumberField label="Couches" value={layers} min={1} max={8} onChange={setLayers} error={errors.layers} />
        </div>
        {!valid ? null : structure.loading ? (
          <Loading label="Construction du schéma" />
        ) : structure.error ? (
          <ErrorState message={structure.error} onRetry={structure.reload} />
        ) : (
          <>
            <CircuitSvg structure={structure.data!} label={info?.label ?? name} />
            <h3 style={{ marginTop: 20 }}>Caractéristiques</h3>
            <div className="table-wrap">
              <table>
                <tbody>
                  <tr>
                    <th scope="row">Paramètres</th>
                    <td className="num">{structure.data!.stats.n_parameters}</td>
                  </tr>
                  <tr>
                    <th scope="row">Profondeur</th>
                    <td className="num">{structure.data!.stats.depth}</td>
                  </tr>
                  <tr>
                    <th scope="row">Portes à 2 qubits</th>
                    <td className="num">{structure.data!.stats.n_two_qubit_gates}</td>
                  </tr>
                  {Object.entries(structure.data!.stats.gate_counts)
                    .sort(([, a], [, b]) => b - a)
                    .map(([gate, count]) => (
                      <tr key={gate}>
                        <th scope="row">Portes {gate.toUpperCase()}</th>
                        <td className="num">{count}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </section>
    </>
  );
}
