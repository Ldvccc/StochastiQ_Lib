// Schéma d'un ansatz en SVG, à partir de GET /ansatz/{name}/structure.
// Rotations : boîtes violettes au texte blanc ; CNOT : point de contrôle et
// cible (disque encre avec un « + » blanc) reliés par un trait ; fils horizontaux.

export interface Gate {
  type: "RX" | "RY" | "RZ" | "CNOT";
  qubits: number[];
  param_index: number | null;
}

export interface Structure {
  n_qubits: number;
  layers: number;
  columns: { gates: Gate[] }[];
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
  const rotations = structure.columns.flatMap((c) => c.gates).filter((g) => g.type !== "CNOT").length;
  const cnots = structure.columns.flatMap((c) => c.gates).filter((g) => g.type === "CNOT").length;
  return (
    <div className="table-wrap">
      <svg
        role="img"
        aria-label={`${label} : ${structure.n_qubits} qubits, ${structure.layers} couches, ${rotations} rotations et ${cnots} CNOT`}
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
            const q = gate.qubits[0];
            return (
              <g key={`${c}-${g}`} data-gate={gate.type}>
                <rect x={x(c) - 20} y={y(q) - 14} width={40} height={28} rx={6} fill={VIOLET} />
                <text x={x(c)} y={y(q) + 5} textAnchor="middle" fontSize={12} fontWeight={600} fill="#ffffff">
                  {gate.type}
                </text>
              </g>
            );
          }),
        )}
      </svg>
    </div>
  );
}
