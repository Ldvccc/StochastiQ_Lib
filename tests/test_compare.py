from stochastiq import build_ansatz, compare

COLUMNS = [
    "n_qubits",
    "n_parameters",
    "depth",
    "n_two_qubit_gates",
    "expressibility",
    "entangling_capability",
    "gradient_variance",
    "gradient_variance_active",
    "inactive_fraction",
]


def test_compare():
    circuits = {name: build_ansatz(name, 3, 2) for name in ("hardware_efficient", "all_to_all", "data_reuploading")}
    df = compare(circuits, n_samples=50, seed=0)
    assert list(df.columns) == COLUMNS
    assert len(df) == 3
    assert set(df.index) == set(circuits)
    assert df["expressibility"].is_monotonic_increasing


def test_compare_plusieurs_graines():
    circuits = {name: build_ansatz(name, 2, 1) for name in ("hardware_efficient", "basic_entangler")}
    df = compare(circuits, n_samples=30, seed=0, n_seeds=3)
    for metric in ("expressibility", "entangling_capability", "gradient_variance", "gradient_variance_active"):
        assert f"{metric}_std" in df.columns
        assert (df[f"{metric}_std"] >= 0).all()
    assert "inactive_fraction_std" not in df.columns
    assert df["inactive_fraction"].between(0, 1).all()
    assert df["expressibility"].is_monotonic_increasing


def test_compare_une_graine_sans_std():
    df = compare({"hardware_efficient": build_ansatz("hardware_efficient", 2, 1)}, n_samples=30, seed=0)
    assert list(df.columns) == COLUMNS


def test_compare_variance_active_au_moins_egale():
    circuits = {name: build_ansatz(name, 3, 2) for name in ("hardware_efficient", "strongly_entangling")}
    df = compare(circuits, n_samples=50, seed=0)
    assert (df["gradient_variance_active"] >= df["gradient_variance"]).all()
