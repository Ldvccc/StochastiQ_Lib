"""Lecture des CSV de problèmes, avec des bornes strictes (aucun code client exécuté).

Deux formats, avec ou sans ligne d'en-tête :

- ``probabilities`` : ``bitstring,probabilite`` par ligne (qubit n-1 à gauche) ;
- ``samples`` : échantillons bruts, une colonne numérique par variable.

Le séparateur est la virgule et le séparateur décimal le point (CSV standard).
"""

import csv
import io

MAX_CSV_BYTES = 1_000_000
MAX_CSV_ROWS = 100_000


def _rows(content: str) -> list[list[str]]:
    if len(content.encode("utf-8")) > MAX_CSV_BYTES:
        raise ValueError("Le fichier CSV dépasse 1 Mo.")
    rows = []
    for row in csv.reader(io.StringIO(content)):
        cells = [cell.strip() for cell in row]
        if not any(cells) or cells[0].startswith("#"):
            continue  # lignes vides et commentaires
        rows.append(cells)
        if len(rows) > MAX_CSV_ROWS + 1:  # + 1 : ligne d'en-tête éventuelle
            raise ValueError(f"Le fichier CSV dépasse {MAX_CSV_ROWS} lignes.")
    if not rows:
        raise ValueError("Le fichier CSV est vide.")
    return rows


def _is_number(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def parse_probabilities(content: str) -> dict[str, float]:
    """Lit ``bitstring,probabilite`` ; refuse les doublons et les lignes mal formées."""
    rows = _rows(content)
    if not (set(rows[0][0]) <= {"0", "1"} and len(rows[0]) >= 2 and _is_number(rows[0][1])):
        rows = rows[1:]  # ligne d'en-tête
    if not rows:
        raise ValueError("Aucune probabilité dans le fichier CSV : il est vide après la ligne d'en-tête.")
    if len(rows) > MAX_CSV_ROWS:
        raise ValueError(f"Le fichier CSV dépasse {MAX_CSV_ROWS} lignes.")
    mapping: dict[str, float] = {}
    for line, row in enumerate(rows, start=1):
        if len(row) != 2 or not row[0] or set(row[0]) - {"0", "1"} or not _is_number(row[1]):
            raise ValueError(f"Ligne {line} invalide : « bitstring,probabilite » attendu.")
        if row[0] in mapping:
            raise ValueError(f"La chaîne de bits {row[0]} apparaît plusieurs fois.")
        mapping[row[0]] = float(row[1])
    return mapping


def parse_samples(content: str) -> list[list[float]]:
    """Lit des échantillons numériques ; toutes les lignes ont le même nombre de colonnes."""
    rows = _rows(content)
    if not all(_is_number(cell) for cell in rows[0]):
        rows = rows[1:]  # ligne d'en-tête
    if not rows:
        raise ValueError("Aucun échantillon dans le fichier CSV.")
    if len(rows) > MAX_CSV_ROWS:
        raise ValueError(f"Le fichier CSV dépasse {MAX_CSV_ROWS} lignes.")
    width = len(rows[0])
    samples = []
    for line, row in enumerate(rows, start=1):
        if len(row) != width or not all(_is_number(cell) for cell in row):
            raise ValueError(f"Ligne {line} invalide : {width} valeur(s) numérique(s) attendue(s).")
        samples.append([float(cell) for cell in row])
    return samples
