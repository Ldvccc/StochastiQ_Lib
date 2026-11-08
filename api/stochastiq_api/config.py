from pydantic_settings import BaseSettings, SettingsConfigDict

# Secret utilisable uniquement en développement : l'API refuse de démarrer
# avec cette valeur si ENV n'est pas « dev ».
DEFAULT_SECRET_KEY = "dev-secret-a-remplacer-hors-developpement"


class Settings(BaseSettings):
    """Configuration lue dans les variables d'environnement (ou un fichier ``.env``)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    env: str = "dev"
    secret_key: str = DEFAULT_SECRET_KEY
    database_url: str = "sqlite:///./stochastiq.db"
    cors_origin: str = "http://localhost:5173"
    jwt_expire_hours: int = 12
    # Durée maximale d'un run, en secondes (10 minutes).
    run_timeout_seconds: float = 600
    # Dossier du modèle de prédiction (scripts/train_predictor.py) ; /data/models sous Docker.
    models_dir: str = "./models"

    def check(self) -> None:
        """Lève ``RuntimeError`` si la configuration n'est pas sûre hors développement."""
        if self.env != "dev" and self.secret_key == DEFAULT_SECRET_KEY:
            raise RuntimeError(
                "SECRET_KEY doit être définie (valeur par défaut interdite quand ENV n'est pas « dev »)."
            )
        if self.env != "dev" and len(self.secret_key) < 32:
            raise RuntimeError("SECRET_KEY doit compter au moins 32 caractères hors développement.")
