import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";

import { api } from "../api/client";
import type { CustomAnsatz } from "../api/types";
import { CircuitSvg, type Structure } from "../components/CircuitSvg";
import { Empty, ErrorState, GuardedButton, Loading } from "../components/common";
import { useProject } from "../components/ProjectContext";
import { NumberField } from "../components/science";
import { formatDateTime } from "../lib/format";
import { useAsync } from "../lib/useAsync";

export const ENTANGLER_LABELS: Record<string, string> = {
  ring: "Anneau i → i+1",
  basic_ring: "Anneau (un seul CNOT pour 2 qubits)",
  strongly: "Portée variable selon la couche (StronglyEntangling)",
  linear: "Chaîne i → i+1",
  all_pairs: "Toutes les paires i < j",
  brick: "Briques (paires paires puis impaires)",
  none: "Aucune intrication",
  custom: "CNOT choisis (nombre de qubits fixé)",
};

const QASM_EXAMPLE = `OPENQASM 3.0;
include "stdgates.inc";
input float[64] a;
input float[64] b;
qubit[2] q;
ry(a) q[0];
ry(b) q[1];
cx q[0], q[1];
`;

/** Lit des CNOT « contrôle-cible » séparés par « ; » (par exemple « 0-1; 1-2 »). */
export function parsePairs(text: string): { pairs: [number, number][] } | { error: string } {
  const parts = text.split(";").map((p) => p.trim()).filter(Boolean);
  if (parts.length === 0) return { error: "Indiquez au moins un CNOT « contrôle-cible »." };
  const pairs: [number, number][] = [];
  for (const part of parts) {
    const match = /^(\d+)\s*-\s*(\d+)$/.exec(part);
    if (!match) return { error: `CNOT invalide : « ${part} » (forme « 0-1 » attendue).` };
    const [control, target] = [Number(match[1]), Number(match[2])];
    if (control === target) return { error: `CNOT invalide : « ${part} » (contrôle et cible distincts).` };
    pairs.push([control, target]);
  }
  return { pairs };
}

function SpecForm({ projectId, onCreated }: { projectId: number; onCreated: (id: number) => void }) {
  const { can, reason } = useProject();
  const [name, setName] = useState("");
  const [rotations, setRotations] = useState<string[]>(["ry", "rz", ""]);
  const [entangler, setEntangler] = useState("ring");
  const [pairsText, setPairsText] = useState("0-1; 1-2");
  const [error, setError] = useState<string | null>(null);
  const chosen = rotations.filter(Boolean);
  const parsed = parsePairs(pairsText);
  const invalid = !name.trim() || chosen.length === 0 || (entangler === "custom" && "error" in parsed);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    const spec: Record<string, unknown> = { rotations: chosen, entangler };
    if (entangler === "custom" && "pairs" in parsed) spec.pairs = parsed.pairs;
    try {
      const created = await api.post<CustomAnsatz>(`/projects/${projectId}/custom-ansatz`, { name, format: "spec", spec });
      setName("");
      onCreated(created.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} aria-label="Ansatz par spec">
      <div className="row">
        <label style={{ flex: "1 1 200px" }}>
          Nom
          <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
        </label>
        {rotations.map((rotation, i) => (
          <label key={i}>
            Rotation {i + 1}
            <select value={rotation} onChange={(e) => setRotations(rotations.map((r, j) => (j === i ? e.target.value : r)))}>
              <option value="">Aucune</option>
              <option value="rx">RX</option>
              <option value="ry">RY</option>
              <option value="rz">RZ</option>
            </select>
          </label>
        ))}
        <label>
          Intrication
          <select value={entangler} onChange={(e) => setEntangler(e.target.value)}>
            {Object.entries(ENTANGLER_LABELS).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        </label>
      </div>
      {entangler === "custom" && (
        <label style={{ marginTop: 12 }}>
          CNOT « contrôle-cible », séparés par « ; » (le plus grand indice fixe le nombre de qubits)
          <input value={pairsText} onChange={(e) => setPairsText(e.target.value)} aria-invalid={"error" in parsed} />
          {"error" in parsed && <span className="field-error">{parsed.error}</span>}
        </label>
      )}
      <p className="muted">
        Par couche : les rotations choisies sur chaque qubit, puis les CNOT du motif. Le nombre de qubits et de couches se choisit au lancement d'un run.
      </p>
      <GuardedButton type="submit" allowed={can("custom_ansatz")} reason={reason("custom_ansatz")} disabled={invalid}>
        Enregistrer l'ansatz
      </GuardedButton>
      {error && <ErrorState message={error} />}
    </form>
  );
}

function QasmForm({ projectId, onCreated }: { projectId: number; onCreated: (id: number) => void }) {
  const { can, reason } = useProject();
  const [name, setName] = useState("");
  const [qasm, setQasm] = useState(QASM_EXAMPLE);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const created = await api.post<CustomAnsatz>(`/projects/${projectId}/custom-ansatz`, { name, format: "qasm", qasm });
      setName("");
      onCreated(created.id);
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <form onSubmit={submit} aria-label="Ansatz OpenQASM" style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      <label>
        Nom
        <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
      </label>
      <label>
        Texte OpenQASM 3 (20 000 caractères au plus)
        <textarea className="num" rows={10} maxLength={20000} value={qasm} onChange={(e) => setQasm(e.target.value)} />
      </label>
      <p className="muted" style={{ margin: 0 }}>
        Paramètres déclarés par « input float[64] nom; » et utilisés chacun par une seule porte RX, RY ou RZ. OpenQASM 2 ne permet pas de
        paramètres libres. Le nombre de qubits est celui du texte.
      </p>
      <div>
        <GuardedButton type="submit" allowed={can("custom_ansatz")} reason={reason("custom_ansatz")} disabled={!name.trim() || !qasm.trim()}>
          Enregistrer l'ansatz
        </GuardedButton>
      </div>
      {error && <ErrorState message={error} />}
    </form>
  );
}

interface Preview extends Structure {
  stats: { n_parameters: number; depth: number; n_two_qubit_gates: number; gate_counts: Record<string, number> };
}

function AnsatzDetail({ projectId, ansatz, onDeleted }: { projectId: number; ansatz: CustomAnsatz; onDeleted: () => void }) {
  const { can, reason } = useProject();
  const [nQubits, setNQubits] = useState(ansatz.n_qubits ?? 4);
  const [layers, setLayers] = useState(2);
  const [error, setError] = useState<string | null>(null);
  const fixed = ansatz.n_qubits !== null;
  const preview = useAsync(
    () => api.get<Preview>(`/projects/${projectId}/custom-ansatz/${ansatz.id}/structure?n_qubits=${nQubits}&layers=${layers}`),
    [projectId, ansatz.id, nQubits, layers],
  );

  async function remove() {
    try {
      await api.delete(`/projects/${projectId}/custom-ansatz/${ansatz.id}`);
      onDeleted();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  return (
    <section className="card" aria-labelledby="detail-ansatz">
      <h2 id="detail-ansatz">{ansatz.name}</h2>
      <p className="muted">
        {ansatz.format === "spec" && ansatz.spec
          ? `Spec : rotations ${ansatz.spec.rotations.map((r) => r.toUpperCase()).join(", ")}, intrication « ${ENTANGLER_LABELS[ansatz.spec.entangler]} ».`
          : "Circuit OpenQASM."}
        {fixed && ` Nombre de qubits fixé : ${ansatz.n_qubits}.`}
      </p>
      {ansatz.format === "spec" && (
        <div className="row" style={{ marginBottom: 16 }}>
          <NumberField label="Qubits" value={nQubits} min={2} max={8} onChange={setNQubits} disabled={fixed} note={fixed ? "Fixé par les CNOT choisis." : undefined} />
          <NumberField label="Couches" value={layers} min={1} max={8} onChange={setLayers} />
        </div>
      )}
      {ansatz.format === "qasm" && (
        <details style={{ marginBottom: 16 }}>
          <summary>Texte OpenQASM</summary>
          <pre className="num" style={{ whiteSpace: "pre-wrap", fontSize: "0.8rem" }}>{ansatz.content}</pre>
        </details>
      )}
      {preview.loading ? (
        <Loading label="Construction du schéma" />
      ) : preview.error ? (
        <ErrorState message={preview.error} onRetry={preview.reload} />
      ) : (
        <>
          <CircuitSvg structure={preview.data!} label={ansatz.name} />
          <div className="table-wrap" style={{ marginTop: 16 }}>
            <table>
              <tbody>
                <tr><th scope="row">Paramètres</th><td className="num">{preview.data!.stats.n_parameters}</td></tr>
                <tr><th scope="row">Profondeur</th><td className="num">{preview.data!.stats.depth}</td></tr>
                <tr><th scope="row">Portes à 2 qubits</th><td className="num">{preview.data!.stats.n_two_qubit_gates}</td></tr>
                {Object.entries(preview.data!.stats.gate_counts).map(([gate, count]) => (
                  <tr key={gate}><th scope="row">Portes {gate.toUpperCase()}</th><td className="num">{count}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
      <div style={{ marginTop: 16 }}>
        <GuardedButton className="secondary" allowed={can("custom_ansatz")} reason={reason("custom_ansatz")} onClick={remove}>
          Supprimer
        </GuardedButton>
      </div>
      {error && <ErrorState message={error} />}
    </section>
  );
}

export function CustomAnsatzPage() {
  const { project } = useProject();
  const list = useAsync(() => api.get<CustomAnsatz[]>(`/projects/${project.id}/custom-ansatz`), [project.id]);
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState<"spec" | "qasm">("spec");
  const selectedId = params.get("ansatz") ? Number(params.get("ansatz")) : null;
  const selected = list.data?.find((a) => a.id === selectedId) ?? null;
  const select = (id: number | null) => setParams(id === null ? {} : { ansatz: String(id) });

  return (
    <>
      <h1>Mes ansatz</h1>
      <p className="muted">
        Ansatz propres au projet, utilisables dans le Diagnostic, le Comparateur, le Plateau stérile et le Matériel. Aucun code n'est exécuté : une spec est validée,
        un texte OpenQASM est analysé puis vérifié.
      </p>
      <section className="card" aria-labelledby="nouvel-ansatz">
        <h2 id="nouvel-ansatz">Nouvel ansatz</h2>
        <div className="tabs" role="tablist" aria-label="Format de l'ansatz">
          <button type="button" role="tab" aria-selected={tab === "spec"} onClick={() => setTab("spec")}>
            Formulaire (spec)
          </button>
          <button type="button" role="tab" aria-selected={tab === "qasm"} onClick={() => setTab("qasm")}>
            OpenQASM 3
          </button>
        </div>
        <div role="tabpanel">
          {tab === "spec" ? (
            <SpecForm projectId={project.id} onCreated={(id) => { list.reload(); select(id); }} />
          ) : (
            <QasmForm projectId={project.id} onCreated={(id) => { list.reload(); select(id); }} />
          )}
        </div>
      </section>
      <section className="card" aria-labelledby="liste-ansatz">
        <h2 id="liste-ansatz">Ansatz du projet</h2>
        {list.loading ? (
          <Loading />
        ) : list.error ? (
          <ErrorState message={list.error} onRetry={list.reload} />
        ) : list.data!.length === 0 ? (
          <Empty>Aucun ansatz personnalisé. Créez-en un par le formulaire ou en collant un texte OpenQASM 3.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Nom</th>
                  <th scope="col">Format</th>
                  <th scope="col">Qubits</th>
                  <th scope="col">Créé le</th>
                </tr>
              </thead>
              <tbody>
                {list.data!.map((a) => (
                  <tr key={a.id}>
                    <td>
                      <button type="button" className={a.id === selectedId ? "" : "secondary"} onClick={() => select(a.id)}>
                        {a.name}
                      </button>
                    </td>
                    <td>{a.format === "spec" ? "Spec" : "OpenQASM"}</td>
                    <td className="num">{a.n_qubits ?? "au choix"}</td>
                    <td className="num">{formatDateTime(a.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
      {selected && (
        <AnsatzDetail
          key={selected.id}
          projectId={project.id}
          ansatz={selected}
          onDeleted={() => {
            select(null);
            list.reload();
          }}
        />
      )}
    </>
  );
}
