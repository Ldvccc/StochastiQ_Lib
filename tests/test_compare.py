from stochastiq import build_ansatz, compare

COLUMNS = [
    "n_qubits",
    "n_parameters",
    "depth",
    "n_two_qubit_gates",
    "expressibility",
    "entangling_capability",
    "gradient_variance",
]


def test_compare():
    circuits = {name: build_ansatz(name, 3, 2) for name in ("ry_linear", "ry_full", "ryrz_circular")}
    df = compare(circuits, n_samples=50, seed=0)
    assert list(df.columns) == COLUMNS
    assert len(df) == 3
    assert set(df.index) == set(circuits)
    assert df["expressibility"].is_monotonic_increasing
