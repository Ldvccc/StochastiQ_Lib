"""Ansatz fournis par le client : spec JSON paramétrable ou circuit OpenQASM.

Aucun code client n'est exécuté : une spec est un dictionnaire validé, et un
texte QASM est analysé par les parseurs de Qiskit, puis validé par
``validate_ansatz``.

Format « spec », paramétrable en nombre de qubits et de couches ::

    {"rotations": ["ry", "rz"], "entangler": "ring"}
    {"rotations": ["ry"], "entangler": "custom", "pairs": [[0, 1], [1, 2]]}

``entangler`` vaut l'un des motifs de ``stochastiq.ansatz.ENTANGLERS``
(ring, basic_ring, strongly, linear, all_pairs, brick, none) ou ``custom``.
``pairs`` (liste de CNOT [contrôle, cible]) n'est permis qu'avec ``custom``
et fixe alors le nombre de qubits (plus grand indice + 1). Ordre des
paramètres : celui de ``build_ansatz``, indice ((l·n) + j)·k + r.

Format OpenQASM, à nombre de qubits fixe : OpenQASM 3 avec des paramètres
déclarés par ``input float[64] nom;`` (option ``qasm3`` de la bibliothèque,
paquet ``qiskit_qasm3_import``). OpenQASM 2 n'a pas de paramètres libres :
un circuit OpenQASM 2 se charge, mais ``validate_ansatz`` le refuse. Les
paramètres d'un circuit QASM suivent l'ordre de ``qc.parameters`` (ordre
alphabétique de leur nom, celui de Qiskit).
"""

from collections import Counter
from collections.abc import Mapping

from qiskit import QuantumCircuit, qasm2
from qiskit.circuit import Parameter, ParameterVector

from .ansatz import ENTANGLERS, entangler_pairs

ROTATIONS = ("rx", "ry", "rz")
MAX_ROTATIONS = 3
MAX_PAIRS = 64
MIN_QUBITS = 2
MAX_QUBITS = 8
MAX_PARAMETERS = 300
MAX_DEPTH = 500
MAX_QASM_CHARS = 20_000

# Portes fixes acceptées (sans paramètre libre) dans un ansatz client.
FIXED_GATES = {
    "id", "x", "y", "z", "h", "s", "sdg", "t", "tdg", "sx", "sxdg",
    "rx", "ry", "rz", "p", "u", "cx", "cy", "cz", "swap", "ccx", "cp", "crx", "cry", "crz",
}


def validate_spec(spec: Mapping) -> dict:
    """Valide une spec et la retourne sous forme normalisée (clés connues seulement)."""
    if not isinstance(spec, Mapping):
        raise ValueError("Une spec doit être un objet JSON.")
    unknown = set(spec) - {"rotations", "entangler", "pairs"}
    if unknown:
        raise ValueError(f"Clé(s) inconnue(s) dans la spec : {', '.join(sorted(unknown))}.")
    rotations = spec.get("rotations")
    if not isinstance(rotations, (list, tuple)) or not 1 <= len(rotations) <= MAX_ROTATIONS:
        raise ValueError(f"« rotations » doit contenir de 1 à {MAX_ROTATIONS} rotations parmi rx, ry, rz.")
    for rotation in rotations:
        if rotation not in ROTATIONS:
            raise ValueError(f"Rotation inconnue : {rotation!r} (rx, ry ou rz attendu).")
    entangler = spec.get("entangler")
    if entangler not in (*ENTANGLERS, "custom"):
        raise ValueError(f"Motif d'intrication inconnu : {entangler!r}. Motifs valides : {', '.join((*ENTANGLERS, 'custom'))}.")
    normalized = {"rotations": list(rotations), "entangler": entangler}
    pairs = spec.get("pairs")
    if entangler == "custom":
        if not isinstance(pairs, (list, tuple)) or not 1 <= len(pairs) <= MAX_PAIRS:
            raise ValueError(f"Le motif « custom » demande « pairs » : de 1 à {MAX_PAIRS} CNOT [contrôle, cible].")
        clean = []
        for pair in pairs:
            if (
                not isinstance(pair, (list, tuple))
                or len(pair) != 2
                or not all(isinstance(q, int) and not isinstance(q, bool) for q in pair)
            ):
                raise ValueError(f"CNOT invalide : {pair!r} ([contrôle, cible] entiers attendu).")
            control, target = pair
            if control < 0 or target < 0 or control == target:
                raise ValueError(f"CNOT invalide : {pair!r} (indices positifs et distincts attendus).")
            clean.append([control, target])
        n_fixed = max(max(p) for p in clean) + 1
        if not MIN_QUBITS <= n_fixed <= MAX_QUBITS:
            raise ValueError(f"Les CNOT fixent {n_fixed} qubits : de {MIN_QUBITS} à {MAX_QUBITS} attendus.")
        normalized["pairs"] = clean
    elif pairs is not None:
        raise ValueError("« pairs » n'est permis qu'avec le motif « custom ».")
    return normalized


def spec_qubits(spec: Mapping) -> int | None:
    """Nombre de qubits fixé par une spec (motif « custom »), sinon None."""
    spec = validate_spec(spec)
    if spec["entangler"] != "custom":
        return None
    return max(max(pair) for pair in spec["pairs"]) + 1


def build_from_spec(spec: Mapping, n_qubits: int, layers: int) -> QuantumCircuit:
    """Construit le circuit d'une spec, même structure que ``build_ansatz``.

    Lève ``ValueError`` si la spec est invalide, ou si ``n_qubits`` diffère du
    nombre de qubits fixé par un motif « custom ».
    """
    spec = validate_spec(spec)
    fixed = spec_qubits(spec)
    if fixed is not None and n_qubits != fixed:
        raise ValueError(f"Cet ansatz fixe {fixed} qubits : impossible de le construire sur {n_qubits}.")
    if not MIN_QUBITS <= n_qubits <= MAX_QUBITS or layers < 1:
        raise ValueError(f"Qubits de {MIN_QUBITS} à {MAX_QUBITS} et au moins une couche attendus.")
    rotations = spec["rotations"]
    k = len(rotations)
    theta = ParameterVector("θ", layers * n_qubits * k)
    qc = QuantumCircuit(n_qubits, name="spec")
    for layer in range(layers):
        for j in range(n_qubits):
            for r, rotation in enumerate(rotations):
                getattr(qc, rotation)(theta[(layer * n_qubits + j) * k + r], j)
        pairs = spec["pairs"] if spec["entangler"] == "custom" else entangler_pairs(spec["entangler"], n_qubits, layer)
        for control, target in pairs:
            qc.cx(control, target)
    return qc


def load_qasm(text: str) -> QuantumCircuit:
    """Analyse un texte OpenQASM 2 ou 3 (selon son en-tête) ; aucun code n'est exécuté.

    Lève ``ValueError`` (message en français) si le texte est trop long, si
    l'analyse échoue, ou si OpenQASM 3 est demandé sans l'option ``qasm3``.
    """
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Le texte OpenQASM est vide.")
    if len(text) > MAX_QASM_CHARS:
        raise ValueError(f"Le texte OpenQASM dépasse {MAX_QASM_CHARS} caractères.")
    header = text.lstrip().split(";", 1)[0].replace(" ", "")
    try:
        if header.upper().startswith("OPENQASM3"):
            from qiskit import qasm3

            return qasm3.loads(text)
        return qasm2.loads(text)
    except ImportError as error:
        raise ValueError("OpenQASM 3 demande l'option « qasm3 » (paquet qiskit_qasm3_import).") from error
    except Exception as error:  # erreurs de syntaxe des parseurs de Qiskit
        if type(error).__name__ == "MissingOptionalLibraryError":
            raise ValueError("OpenQASM 3 demande l'option « qasm3 » (paquet qiskit_qasm3_import).") from error
        raise ValueError(f"Texte OpenQASM invalide : {error}") from error


def validate_ansatz(qc: QuantumCircuit) -> QuantumCircuit:
    """Vérifie qu'un circuit est utilisable comme ansatz et le retourne.

    Contraintes : de 2 à 8 qubits, de 1 à 300 paramètres, profondeur au plus
    500 ; portes paramétrées limitées à RX, RY ou RZ dont l'angle est un
    paramètre seul, chaque paramètre n'étant utilisé qu'une fois (contrainte
    de la règle du décalage de paramètre) ; portes fixes de ``FIXED_GATES``
    seulement (ni mesure, ni réinitialisation, ni condition classique).
    Lève ``ValueError`` avec un message qui nomme la porte fautive.
    """
    if not MIN_QUBITS <= qc.num_qubits <= MAX_QUBITS:
        raise ValueError(f"L'ansatz a {qc.num_qubits} qubits : de {MIN_QUBITS} à {MAX_QUBITS} attendus.")
    if qc.num_parameters == 0:
        raise ValueError(
            "L'ansatz n'a aucun paramètre libre. OpenQASM 2 ne permet pas de paramètres : "
            "utilisez OpenQASM 3 (input float[64] nom;) ou une spec."
        )
    if qc.num_parameters > MAX_PARAMETERS:
        raise ValueError(f"L'ansatz a {qc.num_parameters} paramètres : {MAX_PARAMETERS} au plus.")
    uses: Counter[Parameter] = Counter()
    for position, instruction in enumerate(qc.data, start=1):
        op = instruction.operation
        if op.name == "barrier":
            continue
        where = f"porte n° {position} « {op.name} »"
        if op.is_parameterized():
            angle = op.params[0] if op.name in ROTATIONS and len(op.params) == 1 else None
            if not isinstance(angle, Parameter):
                raise ValueError(
                    f"La {where} n'est pas acceptée : une porte paramétrée doit être RX, RY ou RZ "
                    "d'angle égal à un paramètre seul."
                )
            uses[angle] += 1
        elif op.name not in FIXED_GATES:
            raise ValueError(f"La {where} n'est pas acceptée dans un ansatz.")
    reused = sorted(p.name for p, count in uses.items() if count > 1)
    if reused:
        raise ValueError(f"Paramètre(s) utilisé(s) plusieurs fois : {', '.join(reused)} (une seule porte par paramètre).")
    depth = qc.depth()
    if depth > MAX_DEPTH:
        raise ValueError(f"La profondeur de l'ansatz vaut {depth} : {MAX_DEPTH} au plus.")
    return qc


_TYPE_NAMES = {"cx": "CNOT"}


def circuit_structure(qc: QuantumCircuit) -> dict:
    """Décrit un circuit quelconque en colonnes de portes, pour le dessin.

    Chaque porte est placée dans la première colonne libre sur toute la plage
    de qubits qu'elle couvre (du plus petit au plus grand indice), ce qui
    évite les chevauchements de traits verticaux. Format de ``ansatz_structure``,
    sans le nombre de couches : ``{"n_qubits", "columns": [{"gates": [...]}]}``,
    avec ``type`` (nom en majuscules, ``CNOT`` pour cx), ``qubits`` et
    ``param_index`` (rang du paramètre dans ``qc.parameters``, sinon None).
    """
    index = {p: i for i, p in enumerate(qc.parameters)}
    next_free = [0] * qc.num_qubits
    columns: list[list[dict]] = []
    for instruction in qc.data:
        op = instruction.operation
        if op.name == "barrier":
            continue
        qubits = [qc.find_bit(q).index for q in instruction.qubits]
        span = range(min(qubits), max(qubits) + 1)
        column = max(next_free[q] for q in span)
        while len(columns) <= column:
            columns.append([])
        param = op.params[0] if op.params and isinstance(op.params[0], Parameter) else None
        columns[column].append(
            {
                "type": _TYPE_NAMES.get(op.name, op.name.upper()),
                "qubits": qubits,
                "param_index": index[param] if param is not None else None,
            }
        )
        for q in span:
            next_free[q] = column + 1
    return {"n_qubits": qc.num_qubits, "columns": [{"gates": gates} for gates in columns]}
