"""Distributions de probabilité cibles (le « problème » d'un client).

Une distribution sur n qubits est un vecteur de 2^n probabilités. Convention
d'ordre des bits : little-endian de Qiskit, comme dans le reste du code.
L'indice i correspond à l'état où le qubit q vaut le bit q de i ; sa chaîne
de bits s'écrit qubit n-1 à gauche et qubit 0 à droite (``format(i, "0nb")``).
Ainsi, ``from_probabilities({"01": 1.0})`` place toute la masse sur l'indice
1, où le qubit 0 vaut 1 et le qubit 1 vaut 0.
"""

from collections.abc import Callable, Mapping, Sequence

import numpy as np

MIN_QUBITS = 2
MAX_QUBITS = 8

# Tolérance sur la somme des probabilités fournies (aucune renormalisation silencieuse).
SUM_TOLERANCE = 1e-6


def _check_qubits(n_qubits: int) -> int:
    if not isinstance(n_qubits, (int, np.integer)) or not MIN_QUBITS <= n_qubits <= MAX_QUBITS:
        raise ValueError(f"Le nombre de qubits doit être un entier de {MIN_QUBITS} à {MAX_QUBITS}.")
    return int(n_qubits)


def _normalize(weights: np.ndarray) -> np.ndarray:
    total = weights.sum()
    if not np.isfinite(total) or total <= 0:
        raise ValueError("La distribution est nulle ou non définie.")
    return weights / total


def _grid(n_qubits: int) -> np.ndarray:
    """Valeurs entières 0..2^n-1 : l'indice lu comme un entier (une seule variable)."""
    return np.arange(2**n_qubits, dtype=float)


def gaussian(n_qubits: int, mean: float | None = None, std: float | None = None) -> np.ndarray:
    """Gaussienne discrétisée sur les entiers 0..2^n-1.

    Par défaut : moyenne au centre, (2^n - 1)/2, et écart-type 2^n/6.
    """
    n_qubits = _check_qubits(n_qubits)
    size = 2**n_qubits
    mean = (size - 1) / 2 if mean is None else mean
    std = size / 6 if std is None else std
    if std <= 0:
        raise ValueError("L'écart-type doit être strictement positif.")
    x = _grid(n_qubits)
    return _normalize(np.exp(-((x - mean) ** 2) / (2 * std**2)))


def bimodal(
    n_qubits: int,
    means: Sequence[float] | None = None,
    std: float | None = None,
    weights: Sequence[float] = (0.5, 0.5),
) -> np.ndarray:
    """Mélange de deux gaussiennes discrétisées.

    Par défaut : modes à 2^n/4 et 3·2^n/4, écart-type 2^n/10, poids égaux.
    """
    n_qubits = _check_qubits(n_qubits)
    size = 2**n_qubits
    means = (size / 4, 3 * size / 4) if means is None else tuple(means)
    std = size / 10 if std is None else std
    if len(means) != 2 or len(weights) != 2:
        raise ValueError("Un mélange bimodal demande deux moyennes et deux poids.")
    if std <= 0 or min(weights) < 0 or sum(weights) <= 0:
        raise ValueError("Écart-type strictement positif et poids positifs requis.")
    x = _grid(n_qubits)
    mixture = sum(w * np.exp(-((x - m) ** 2) / (2 * std**2)) for m, w in zip(means, weights))
    return _normalize(mixture)


def lognormal(n_qubits: int, mu: float = 0.0, sigma: float = 0.5) -> np.ndarray:
    """Log-normale (cas finance : prix d'un actif) discrétisée.

    L'intervalle ]0, exp(mu + 3 sigma)] est découpé en 2^n classes ; la
    densité est évaluée au centre de chaque classe, puis normalisée.
    """
    n_qubits = _check_qubits(n_qubits)
    if sigma <= 0:
        raise ValueError("sigma doit être strictement positif.")
    size = 2**n_qubits
    upper = np.exp(mu + 3 * sigma)
    centers = (np.arange(size) + 0.5) * upper / size
    density = np.exp(-((np.log(centers) - mu) ** 2) / (2 * sigma**2)) / centers
    return _normalize(density)


def uniform(n_qubits: int) -> np.ndarray:
    """Distribution uniforme sur les 2^n états."""
    n_qubits = _check_qubits(n_qubits)
    return np.full(2**n_qubits, 1 / 2**n_qubits)


BAS_GRIDS = {4: (2, 2), 6: (2, 3)}


def bars_and_stripes(n_qubits: int) -> np.ndarray:
    """Bars-and-Stripes : uniforme sur les images à lignes constantes ou à colonnes constantes.

    n = 4 : grille 2×2 (6 images) ; n = 6 : grille 2×3 (10 images). Le pixel
    (ligne r, colonne c) est porté par le qubit r × colonnes + c.
    """
    n_qubits = _check_qubits(n_qubits)
    if n_qubits not in BAS_GRIDS:
        raise ValueError("Bars-and-Stripes n'est défini que pour 4 qubits (grille 2×2) ou 6 qubits (grille 2×3).")
    rows, cols = BAS_GRIDS[n_qubits]
    patterns = set()
    for row_bits in range(2**rows):  # barres : chaque ligne est constante
        patterns.add(sum(((row_bits >> r) & 1) << (r * cols + c) for r in range(rows) for c in range(cols)))
    for col_bits in range(2**cols):  # rayures : chaque colonne est constante
        patterns.add(sum(((col_bits >> c) & 1) << (r * cols + c) for r in range(rows) for c in range(cols)))
    probs = np.zeros(2**n_qubits)
    probs[sorted(patterns)] = 1 / len(patterns)
    return probs


def ising_boltzmann(n_qubits: int, beta: float = 1.0, seed: int | None = None) -> np.ndarray:
    """Distribution de Boltzmann d'un modèle d'Ising à couplages aléatoires.

    Spins s_q = 1 - 2·bit_q ; énergie E(s) = -Σ_{i<j} J_ij s_i s_j, avec des
    couplages J_ij tirés selon N(0, 1) (``default_rng(seed)``) ; p(s) ∝ exp(-β E(s)).
    """
    n_qubits = _check_qubits(n_qubits)
    if beta < 0:
        raise ValueError("beta doit être positif ou nul.")
    rng = np.random.default_rng(seed)
    couplings = np.triu(rng.normal(size=(n_qubits, n_qubits)), k=1)
    indices = np.arange(2**n_qubits)
    spins = 1 - 2 * ((indices[:, None] >> np.arange(n_qubits)) & 1)
    energy = -np.einsum("si,ij,sj->s", spins, couplings, spins)
    weights = np.exp(-beta * (energy - energy.min()))
    return _normalize(weights)


# Nom -> (fonction, aléatoire ?). Les distributions aléatoires acceptent ``seed``.
REFERENCE_DISTRIBUTIONS: dict[str, tuple[Callable[..., np.ndarray], bool]] = {
    "gaussian": (gaussian, False),
    "bimodal": (bimodal, False),
    "lognormal": (lognormal, False),
    "uniform": (uniform, False),
    "bars_and_stripes": (bars_and_stripes, False),
    "ising_boltzmann": (ising_boltzmann, True),
}


def list_distributions() -> list[str]:
    """Noms des distributions de référence."""
    return list(REFERENCE_DISTRIBUTIONS)


def reference_distribution(name: str, n_qubits: int, seed: int | None = None) -> np.ndarray:
    """Distribution de référence ``name`` avec ses paramètres par défaut.

    ``seed`` n'est transmis qu'aux distributions aléatoires.
    """
    if name not in REFERENCE_DISTRIBUTIONS:
        raise ValueError(f"Distribution inconnue : {name!r}. Noms valides : {', '.join(list_distributions())}.")
    function, random = REFERENCE_DISTRIBUTIONS[name]
    return function(n_qubits, seed=seed) if random else function(n_qubits)


def _gray(value: np.ndarray) -> np.ndarray:
    return value ^ (value >> 1)


def from_samples(
    samples: Sequence[float] | Sequence[Sequence[float]] | np.ndarray,
    n_qubits: int,
    ranges: Sequence[tuple[float, float]],
    encoding: str = "binary",
) -> np.ndarray:
    """Distribution empirique d'échantillons continus d'une ou plusieurs variables.

    Chaque variable reçoit n/d qubits (d = nombre de variables) : son intervalle
    [min, max] est découpé en 2^(n/d) classes de même largeur (la borne max
    tombe dans la dernière classe). La variable v occupe les qubits
    v·k à (v+1)·k - 1, avec k = n/d. Encodage de la classe : ``"binary"``
    (rang de la classe) ou ``"gray"`` (code de Gray, deux classes voisines ne
    diffèrent que d'un bit).

    Lève ``ValueError`` si n n'est pas divisible par d, si un intervalle est
    vide, ou si un échantillon sort de son intervalle (pas d'écrêtage silencieux).
    """
    n_qubits = _check_qubits(n_qubits)
    data = np.asarray(samples, dtype=float)
    if data.ndim == 1:
        data = data[:, None]
    if data.ndim != 2 or data.shape[0] == 0:
        raise ValueError("Les échantillons doivent former un tableau non vide (une colonne par variable).")
    n_vars = data.shape[1]
    if len(ranges) != n_vars:
        raise ValueError(f"{n_vars} variable(s) mais {len(ranges)} intervalle(s) fourni(s).")
    if n_qubits % n_vars != 0:
        raise ValueError(f"{n_qubits} qubits ne se répartissent pas également entre {n_vars} variables.")
    if encoding not in ("binary", "gray"):
        raise ValueError("Encodage inconnu : 'binary' ou 'gray' attendu.")
    if not np.all(np.isfinite(data)):
        raise ValueError("Les échantillons contiennent des valeurs non numériques ou infinies.")

    bits = n_qubits // n_vars
    levels = 2**bits
    index = np.zeros(data.shape[0], dtype=np.int64)
    for v, (low, high) in enumerate(ranges):
        if not high > low:
            raise ValueError(f"Intervalle vide pour la variable {v + 1} : [{low}, {high}].")
        column = data[:, v]
        if column.min() < low or column.max() > high:
            raise ValueError(f"Des échantillons de la variable {v + 1} sortent de l'intervalle [{low}, {high}].")
        classes = np.minimum(((column - low) / (high - low) * levels).astype(np.int64), levels - 1)
        if encoding == "gray":
            classes = _gray(classes)
        index |= classes << (v * bits)
    counts = np.bincount(index, minlength=2**n_qubits).astype(float)
    return counts / counts.sum()


def from_probabilities(mapping: Mapping[str, float]) -> np.ndarray:
    """Vecteur de probabilités à partir de chaînes de bits (qubit n-1 à gauche).

    Les états absents ont une probabilité nulle. Lève ``ValueError`` si les
    chaînes n'ont pas toutes la même longueur (2 à 8), si une probabilité est
    négative ou si la somme s'écarte de 1 de plus de 1e-6 (pas de
    renormalisation silencieuse).
    """
    if not mapping:
        raise ValueError("Aucune probabilité fournie.")
    lengths = {len(key) for key in mapping}
    if len(lengths) != 1:
        raise ValueError("Toutes les chaînes de bits doivent avoir la même longueur.")
    n_qubits = _check_qubits(lengths.pop())
    probs = np.zeros(2**n_qubits)
    for bitstring, value in mapping.items():
        if set(bitstring) - {"0", "1"}:
            raise ValueError(f"Chaîne de bits invalide : {bitstring!r}.")
        value = float(value)
        if not np.isfinite(value) or value < 0:
            raise ValueError(f"Probabilité négative ou non définie pour {bitstring!r}.")
        probs[int(bitstring, 2)] = value
    total = probs.sum()
    if abs(total - 1) > SUM_TOLERANCE:
        raise ValueError(f"La somme des probabilités vaut {total:.8g}, et non 1 (tolérance 1e-6).")
    return probs


def check_probabilities(probs: Sequence[float] | np.ndarray) -> np.ndarray:
    """Valide un vecteur de 2^n probabilités (n de 2 à 8), positif, de somme 1 à 1e-6 près."""
    vector = np.asarray(probs, dtype=float)
    if vector.ndim != 1:
        raise ValueError("Un vecteur de probabilités est attendu.")
    n_qubits = int(np.log2(vector.size)) if vector.size > 0 else 0
    if 2**n_qubits != vector.size:
        raise ValueError("La longueur du vecteur doit être une puissance de 2.")
    _check_qubits(n_qubits)
    if not np.all(np.isfinite(vector)) or vector.min() < 0:
        raise ValueError("Les probabilités doivent être positives ou nulles.")
    if abs(vector.sum() - 1) > SUM_TOLERANCE:
        raise ValueError(f"La somme des probabilités vaut {vector.sum():.8g}, et non 1 (tolérance 1e-6).")
    return vector


def _bit_marginals(probs: np.ndarray, n_qubits: int) -> np.ndarray:
    """Tableau de forme (2,)*n, l'axe n - 1 - q portant le qubit q."""
    return probs.reshape([2] * n_qubits)


def problem_features(probs: Sequence[float] | np.ndarray) -> dict:
    """Caractéristiques d'une distribution, utilisées par la prédiction.

    Retourne ``n_qubits``, ``entropy`` (entropie de Shannon normalisée par n,
    entre 0 et 1), ``support_fraction`` (part des états de probabilité non
    nulle), ``max_probability`` et ``mean_mutual_information`` (information
    mutuelle moyenne entre paires de bits, en bits).
    """
    vector = check_probabilities(probs)
    n_qubits = int(np.log2(vector.size))
    nonzero = vector[vector > 0]
    entropy = float(-(nonzero * np.log2(nonzero)).sum() / n_qubits)

    tensor = _bit_marginals(vector, n_qubits)
    informations = []
    for a in range(n_qubits):
        for b in range(a + 1, n_qubits):
            keep = (n_qubits - 1 - a, n_qubits - 1 - b)
            joint = tensor.sum(axis=tuple(i for i in range(n_qubits) if i not in keep))
            # ``joint`` est indexé dans l'ordre croissant des axes : (axe de b, axe de a).
            pa, pb = joint.sum(axis=0), joint.sum(axis=1)
            outer = np.outer(pb, pa)
            mask = joint > 0
            informations.append(float((joint[mask] * np.log2(joint[mask] / outer[mask])).sum()))
    return {
        "n_qubits": n_qubits,
        "entropy": entropy,
        "support_fraction": float(nonzero.size / vector.size),
        "max_probability": float(vector.max()),
        "mean_mutual_information": float(np.mean(informations)) if informations else 0.0,
    }


def bitstring(index: int, n_qubits: int) -> str:
    """Chaîne de bits de l'indice ``index`` (qubit n-1 à gauche, convention Qiskit)."""
    return format(index, f"0{n_qubits}b")
