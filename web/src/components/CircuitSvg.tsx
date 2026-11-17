// Schéma d'un ansatz en SVG, à partir de GET /ansatz/{name}/structure.
// Rotations : boîtes violettes au texte blanc ; CNOT : point de contrôle et
// cible (disque encre avec un « + » blanc) reliés par un trait ; fils horizontaux.

export interface Gate {
  type: string; // "RX", "RY", "RZ", "CNOT" ou toute autre porte (H, CZ, SWAP...)
  qubits: number[];
  param_index: number | null;
}

export interface Structure {
  n_qubits: number;
  layers?: number | null;
  columns: { gates: Gate[] }[];
}

const ROTATIONS = new Set(["RX", "RY", "RZ"]);

/** « 1 couche », « 3 couches » (pluriel français à partir de 2). */
function count(n: number, word: string): string {
  return `${n} ${word}${n >= 2 ? "s" : ""}`;
}

const INK = "#14163f";
const VIOLET = "#5b4bff";
const WIRE_GAP = 48;
const COLUMN = 56;
const LEFT = 44;
const TOP = 28;

export function CircuitSvg({ structure, label }: { structure: Structure; label: string }) {
  const width = LEFT + structure.columns.length * COLUMN + 16;
  const height = TOP + (structure.n_qubits - 1) * WIRE_GAP + 28;
  const y = (qubit: number) => TOP + qubit * WIRE_GAP;
  const x = (column: number) => LEFT + column * COLUMN + COLUMN / 2;
  const gates = structure.columns.flatMap((c) => c.gates);
  const rotations = gates.filter((g) => ROTATIONS.has(g.type)).length;
  const cnots = gates.filter((g) => g.type === "CNOT").length;
  const others = gates.length - rotations - cnots;
  const layersText = structure.layers ? `, ${count(structure.layers, "couche")}` : "";
  const othersText = others === 0 ? "" : others === 1 ? " et 1 autre porte" : ` et ${others} autres portes`;
  return (
    <div className="table-wrap">
      <svg
        role="img"
        aria-label={`${label} : ${structure.n_qubits} qubits${layersText}, ${count(rotations, "rotation")}, ${cnots} CNOT${othersText}`}
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        style={{ display: "block", background: "#ffffff" }}
      >
        {Array.from({ length: structure.n_qubits }, (_, q) => (
          <g key={`fil-${q}`}>
            <text x={8} y={y(q) + 4} fontSize={13} fill={INK} fontFamily="JetBrains Mono, monospace">
              q{q}
            </text>
            <line x1={LEFT - 8} x2={width - 8} y1={y(q)} y2={y(q)} stroke={INK} strokeWidth={1.2} />
          </g>
        ))}
        {structure.columns.map((column, c) =>
          column.gates.map((gate, g) => {
            if (gate.type === "CNOT") {
              const [control, target] = gate.qubits;
              return (
                <g key={`${c}-${g}`} data-gate="CNOT">
                  <line x1={x(c)} x2={x(c)} y1={y(control)} y2={y(target)} stroke={INK} strokeWidth={1.5} />
                  <circle cx={x(c)} cy={y(control)} r={5} fill={INK} />
                  <circle cx={x(c)} cy={y(target)} r={11} fill={INK} />
                  <line x1={x(c) - 6} x2={x(c) + 6} y1={y(target)} y2={y(target)} stroke="#ffffff" strokeWidth={2} />
                  <line x1={x(c)} x2={x(c)} y1={y(target) - 6} y2={y(target) + 6} stroke="#ffffff" strokeWidth={2} />
                </g>
              );
            }
            // Rotation paramétrée : boîte violette ; autre porte : boîte encre. Les portes
            // à plusieurs qubits sont reliées par un trait vertical.
            const fill = ROTATIONS.has(gate.type) ? VIOLET : INK;
            const label = gate.type.length > 4 ? gate.type.slice(0, 4) : gate.type;
            return (
              <g key={`${c}-${g}`} data-gate={gate.type}>
                {gate.qubits.length > 1 && (
                  <line x1={x(c)} x2={x(c)} y1={y(Math.min(...gate.qubits))} y2={y(Math.max(...gate.qubits))} stroke={INK} strokeWidth={1.5} />
                )}
                {gate.qubits.map((q) => (
                  <g key={q}>
                    <rect x={x(c) - 20} y={y(q) - 14} width={40} height={28} rx={6} fill={fill} />
                    <text x={x(c)} y={y(q) + 5} textAnchor="middle" fontSize={12} fontWeight={600} fill="#ffffff">
                      {label}
                    </text>
                  </g>
                ))}
              </g>
            );
          }),
        )}
      </svg>
    </div>
  );
}
