"""Grille de référence de la base de résultats (données d'entraînement de l'IA de prédiction).

Grille : 7 ansatz du catalogue × distributions de référence × qubits 2 à 6 ×
couches 1 à 4 (Bars-and-Stripes n'existe qu'à 4 et 6 qubits). Pour chaque
configuration : entraînement exact (KL, Adam, 200 itérations, pas 0,1,
graine 0), puis évaluation des paramètres appris sous les trois profils de
bruit (topologie en ligne). Une configuration donne 4 lignes, écrites dans la
même transaction.

Reprise : les configurations déjà présentes (même ``config_key``) sont
sautées ; on peut interrompre et relancer.

Utilisation, depuis la racine du dépôt (PowerShell) :

    .venv\\Scripts\\python scripts\\build_results.py --measure       # 10 configurations, puis estimation
    .venv\\Scripts\\python scripts\\build_results.py --limit 50
    .venv\\Scripts\\python scripts\\build_results.py --workers 4
    .venv\\Scripts\\python scripts\\build_results.py --export resultats.csv   # ou .parquet

La base est celle de DATABASE_URL (ou de ``--database-url``).
"""

import argparse
import random
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

import stochastiq
from sqlalchemy import select
from stochastiq import circuit_features, list_ansatz, list_distributions, reference_distribution

from stochastiq_api.config import Settings
from stochastiq_api.db import make_engine, make_sessionmaker, upgrade_database
from stochastiq_api.ml.results import _base, export_results, training_rows
from stochastiq_api.models import Result
from stochastiq_api.runner import _training, evaluate_under_noise, make_circuit, to_json

QUBITS = range(2, 7)
LAYERS = range(1, 5)
PROFILES = ("faible", "moyen", "fort")
TOPOLOGY = "line"
TRAINING = {"loss": "kl", "optimizer": "adam", "max_iter": 200, "learning_rate": 0.1, "shots": None, "seed": 0}
# Au-delà, l'auteur doit donner son accord avant le lancement complet.
LIMIT_SECONDS = 2 * 3600


def grid() -> list[tuple[str, str, int, int]]:
    """Configurations (ansatz, distribution, qubits, couches) de la grille."""
    configs = []
    for ansatz in list_ansatz():
        for distribution in list_distributions():
            for n_qubits in QUBITS:
                try:
                    reference_distribution(distribution, n_qubits, seed=0)
                except ValueError:
                    continue
                configs.extend((ansatz, distribution, n_qubits, layers) for layers in LAYERS)
    return configs


def config_key(config, row_type: str, profile: str | None = None) -> str:
    ansatz, distribution, n_qubits, layers = config
    return f"grid|{ansatz}|{distribution}|{n_qubits}|{layers}|{row_type}|{profile or '-'}"


def compute(config) -> tuple[tuple, list[dict], float]:
    """Entraînement puis évaluations sous bruit d'une configuration (exécuté dans un processus séparé)."""
    start = time.perf_counter()
    ansatz, distribution, n_qubits, layers = config
    target = reference_distribution(distribution, n_qubits, seed=0).tolist()
    params = {"ansatz": ansatz, "n_qubits": n_qubits, "layers": layers, "problem_family": distribution, "target": target, **TRAINING}
    result = _training(params)
    circuit = make_circuit(ansatz, n_qubits, layers)
    evaluations = [
        evaluate_under_noise(circuit, result["params"], target, {"profile": name, "topology": TOPOLOGY}, TRAINING["seed"])
        for name in PROFILES
    ]
    base = _base(ansatz, n_qubits, layers, circuit_features(circuit))
    rows = to_json(training_rows(base, circuit, params, result, evaluations))
    keys = [config_key(config, "training")] + [config_key(config, "training_noise", name) for name in PROFILES]
    for row, key in zip(rows, keys):
        row["config_key"] = key
    return config, rows, time.perf_counter() - start


def save(sessions, rows: list[dict]) -> None:
    with sessions() as db:
        for row in rows:
            db.add(Result(source="grid", library_version=stochastiq.__version__, **row))
        db.commit()


def missing(sessions, configs) -> list:
    with sessions() as db:
        done = set(db.scalars(select(Result.config_key).where(Result.source == "grid")))
    return [c for c in configs if config_key(c, "training") not in done]


def format_hours(seconds: float) -> str:
    return f"{seconds / 3600:.1f} h".replace(".", ",")


def main() -> int:
    parser = argparse.ArgumentParser(description="Grille de référence de la base de résultats.")
    parser.add_argument("--database-url", default=None, help="Base à remplir (par défaut : DATABASE_URL).")
    parser.add_argument("--limit", type=int, default=None, help="Nombre maximal de configurations à calculer.")
    parser.add_argument("--workers", type=int, default=1, help="Processus de calcul en parallèle.")
    parser.add_argument("--measure", action="store_true", help="Calcule 10 configurations tirées au hasard et estime la durée totale.")
    parser.add_argument("--export", default=None, help="Exporte les lignes éligibles à l'IA (.csv ou .parquet) et s'arrête.")
    args = parser.parse_args()

    database_url = args.database_url or Settings().database_url
    upgrade_database(database_url)
    sessions = make_sessionmaker(make_engine(database_url))

    if args.export:
        with sessions() as db:
            print(f"{export_results(db, args.export)} lignes exportées dans {args.export}.")
        return 0

    configs = grid()
    todo = missing(sessions, configs)
    print(f"Grille : {len(configs)} configurations ({4 * len(configs)} lignes) ; {len(todo)} restent à calculer.")

    if args.measure:
        sample = random.Random(0).sample(todo, min(10, len(todo)))
        durations = []
        for config in sample:
            _, rows, seconds = compute(config)
            save(sessions, rows)
            durations.append(seconds)
            print(f"  {config} : {seconds:.1f} s")
        if not durations:
            return 0
        mean = sum(durations) / len(durations)
        remaining = len(todo) - len(sample)
        estimate = mean * remaining / max(1, args.workers)
        print(
            f"Moyenne {mean:.1f} s par configuration (échantillon de {len(durations)}, enregistré). "
            f"Estimation pour les {remaining} restantes avec {args.workers} processus : {format_hours(estimate)}."
        )
        if estimate > LIMIT_SECONDS:
            print("Estimation supérieure à 2 heures : demander l'accord de l'auteur avant le lancement complet.")
        return 0

    if args.limit is not None:
        todo = todo[: args.limit]
    start = time.perf_counter()
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(compute, config) for config in todo]
        for done, future in enumerate(as_completed(futures), 1):
            config, rows, seconds = future.result()
            save(sessions, rows)
            print(f"[{done}/{len(todo)}] {config} : {seconds:.1f} s", flush=True)
    print(f"Terminé en {format_hours(time.perf_counter() - start)}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
