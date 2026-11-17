"""Schémas des runs, commentaires, activité, circuits épinglés et machines.

Les bornes de calcul (qubits 2 à 8, couches 1 à 8, échantillons 50 à 5000,
graines 1 à 10) sont validées ici, avant toute exécution.
"""

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, StringConstraints, field_validator, model_validator

from .catalog import ANSATZ_NAMES, TOPOLOGY_NAMES
from .schemas import Input

AnsatzName = Literal[ANSATZ_NAMES]
TopologyName = Literal[TOPOLOGY_NAMES]
Qubits = Annotated[int, Field(ge=2, le=8)]
Layers = Annotated[int, Field(ge=1, le=8)]
Samples = Annotated[int, Field(ge=50, le=5000)]
Seed = Annotated[int, Field(ge=0, le=1_000_000)]
Observable = Literal["Z0", "Zmean", "Zall"]

RunKind = Literal["diagnostic", "compare", "scaling", "hardware", "training", "noise", "recommendation"]
RunStatus = Literal["pending", "running", "done", "failed"]


class CustomRef(Input):
    """Référence à un ansatz personnalisé du projet (résolue par l'API avant l'enregistrement du run)."""

    custom_id: Annotated[int, Field(ge=1)]


# Nom du catalogue ou ansatz personnalisé du projet.
AnsatzRef = Union[AnsatzName, CustomRef]


def _unique(refs: list) -> list:
    keys = [ref if isinstance(ref, str) else ("custom", ref.custom_id) for ref in refs]
    if len(set(keys)) != len(keys):
        raise ValueError("Chaque ansatz ne doit figurer qu'une fois.")
    return refs


Rate = Annotated[float, Field(ge=0, le=0.5)]
# Topologies simulables en matrice densité (l'hexagone lourd, 19 qubits, ne l'est pas).
NoiseTopology = Literal["line", "ring", "full"]


class CustomNoiseProfile(Input):
    """Profil personnalisé : dépolarisation à 1 et 2 qubits, erreur de lecture."""

    p1: Rate
    p2: Rate
    readout: Rate


# Profil nommé (ordres de grandeur, pas des calibrations) ou personnalisé.
NoiseProfile = Union[Literal["faible", "moyen", "fort"], CustomNoiseProfile]


class NoiseEvaluation(Input):
    profile: NoiseProfile
    topology: NoiseTopology = "line"


class DiagnosticParams(Input):
    ansatz: AnsatzRef
    n_qubits: Qubits
    layers: Layers
    n_samples: Samples = 1000
    seed: Seed = 0
    observable: Observable = "Z0"
    # Facultatif : carte « Dégradation sous bruit » (TVD moyenne idéal / bruité, ligne, 20 tirages).
    noise_profile: NoiseProfile | None = None


class CompareParams(Input):
    ansatz: Annotated[list[AnsatzRef], Field(min_length=1, max_length=7)]
    n_qubits: Qubits
    layers: Layers
    n_samples: Samples = 1000
    n_seeds: Annotated[int, Field(ge=1, le=10)] = 1
    seed: Seed = 0

    _ansatz = field_validator("ansatz")(_unique)


class ScalingParams(Input):
    ansatz: Annotated[list[AnsatzRef], Field(min_length=1, max_length=4)]
    qubit_min: Qubits = 2
    qubit_max: Qubits = 6
    layers: Layers = 3
    layers_mode: Literal["fixed", "linear"] = "fixed"
    n_samples: Samples = 100
    observable: Observable = "Z0"
    # Si vrai, calcule les deux coûts Z0 (local) et Zall (global) ; ``observable`` est ignorée.
    compare_observables: bool = False
    seed: Seed = 0

    _ansatz = field_validator("ansatz")(_unique)

    @model_validator(mode="after")
    def _range(self) -> "ScalingParams":
        if self.qubit_min > self.qubit_max:
            raise ValueError("qubit_min doit être inférieur ou égal à qubit_max.")
        return self


class HardwareParams(Input):
    ansatz: AnsatzRef
    n_qubits: Qubits
    layers: Layers
    topology: TopologyName = "line"
    seed: Seed = 0


class TrainingParams(Input):
    """Entraînement d'un ansatz sur un problème du projet (sa distribution cible)."""

    problem_id: Annotated[int, Field(ge=1)]
    ansatz: AnsatzRef
    layers: Layers
    loss: Literal["kl", "mmd", "tvd"] = "kl"
    optimizer: Literal["adam", "spsa", "cobyla"] = "adam"
    max_iter: Annotated[int, Field(ge=10, le=1000)] = 200
    learning_rate: Annotated[float, Field(gt=0, le=5)] = 0.1
    # None : probabilités exactes ; sinon, estimation par tirages pendant l'entraînement.
    shots: Annotated[int, Field(ge=100, le=100_000)] | None = None
    seed: Seed = 0
    # Facultatif : métriques finales recalculées sous bruit avec les paramètres appris.
    evaluate_noise: NoiseEvaluation | None = None

    @model_validator(mode="after")
    def _tvd_not_with_adam(self) -> "TrainingParams":
        if self.loss == "tvd" and self.optimizer == "adam":
            raise ValueError("La TVD n'est pas dérivable : avec la perte « tvd », choisissez SPSA ou COBYLA.")
        return self


class NoiseParams(Input):
    """TVD moyenne entre sortie idéale et sortie bruitée, sur des paramètres aléatoires."""

    ansatz: AnsatzRef
    n_qubits: Qubits
    layers: Layers
    profile: NoiseProfile
    topology: NoiseTopology = "line"
    n_samples: Annotated[int, Field(ge=1, le=200)] = 20
    seed: Seed = 0


class RecommendationParams(Input):
    """Classement de 2 à 7 ansatz sur un problème du projet, et verdict quantique / classique."""

    problem_id: Annotated[int, Field(ge=1)]
    ansatz: Annotated[list[AnsatzRef], Field(min_length=2, max_length=7)]
    layers: Layers
    noise_profile: NoiseProfile | None = None
    topology: NoiseTopology = "line"
    # Budget d'itérations : budget // 200 entraînements au plus sont conseillés pour trancher.
    budget: Annotated[int, Field(ge=200, le=7000)] = 400
    # Échantillons du diagnostic léger de chaque ansatz.
    n_samples: Samples = 200
    seed: Seed = 0

    _ansatz = field_validator("ansatz")(_unique)


class DiagnosticRunIn(Input):
    kind: Literal["diagnostic"]
    params: DiagnosticParams


class CompareRunIn(Input):
    kind: Literal["compare"]
    params: CompareParams


class ScalingRunIn(Input):
    kind: Literal["scaling"]
    params: ScalingParams


class HardwareRunIn(Input):
    kind: Literal["hardware"]
    params: HardwareParams


class TrainingRunIn(Input):
    kind: Literal["training"]
    params: TrainingParams


class NoiseRunIn(Input):
    kind: Literal["noise"]
    params: NoiseParams


class RecommendationRunIn(Input):
    kind: Literal["recommendation"]
    params: RecommendationParams


RunIn = Annotated[
    Union[DiagnosticRunIn, CompareRunIn, ScalingRunIn, HardwareRunIn, TrainingRunIn, NoiseRunIn, RecommendationRunIn],
    Field(discriminator="kind"),
]


class RunSummary(BaseModel):
    id: int
    project_id: int
    kind: RunKind
    params: dict[str, Any]
    status: RunStatus
    error: str | None
    created_by: int | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


class RunOut(RunSummary):
    result: dict[str, Any] | None


class RunPage(BaseModel):
    items: list[RunSummary]
    total: int


Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]


class CommentIn(Input):
    text: Text


class UserRef(BaseModel):
    id: int
    name: str


class CommentOut(BaseModel):
    id: int
    run_id: int
    user: UserRef | None
    text: str
    created_at: datetime


class ActivityOut(BaseModel):
    id: int
    type: str
    user: UserRef | None
    payload: dict[str, Any]
    created_at: datetime


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    total: int


class PinIn(Input):
    ansatz: AnsatzName
    n_qubits: Qubits
    layers: Layers


class PinOut(BaseModel):
    id: int
    ansatz: str
    n_qubits: int
    layers: int
    pinned_by: int | None
    created_at: datetime


SECRET_FIELDS = ("secret", "api_key", "token", "key", "password")


class MachineIn(Input):
    """Entrée fournisseur + libellé. Aucune clé n'est acceptée ni stockée."""

    provider: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    label: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]

    @model_validator(mode="before")
    @classmethod
    def _no_secret(cls, data: Any) -> Any:
        if isinstance(data, dict) and any(field in data for field in SECRET_FIELDS):
            raise ValueError(
                "Ce prototype ne stocke aucune clé ni aucun secret de machine : "
                "seuls le fournisseur et le libellé sont acceptés."
            )
        return data


class MachineOut(BaseModel):
    id: int
    provider: str
    label: str
    created_by: int | None
    created_at: datetime
