# Image de l'API. Contexte de build : racine du dépôt (bibliothèque + API).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DATABASE_URL=sqlite:////data/stochastiq.db

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY api ./api
COPY scripts ./scripts
# Export de la grille de référence : sert à entraîner le modèle de prédiction au premier démarrage.
COPY data/results_grid.csv ./data/results_grid.csv
RUN pip install ./ ./api \
    && useradd --create-home --uid 1000 stochastiq \
    && mkdir -p /data && chown stochastiq /data

USER stochastiq
WORKDIR /app/api
EXPOSE 8000
# Le premier démarrage entraîne le modèle de prédiction (quelques minutes) avant de lancer l'API.
HEALTHCHECK --interval=15s --timeout=5s --start-period=600s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
# Modèle de prédiction entraîné dans MODELS_DIR s'il est absent, puis l'API.
CMD ["sh", "-c", "python -m stochastiq_api.ml.bootstrap && exec uvicorn stochastiq_api.main:app --host 0.0.0.0 --port 8000"]
