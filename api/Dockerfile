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
RUN pip install ./ ./api \
    && useradd --create-home --uid 1000 stochastiq \
    && mkdir -p /data && chown stochastiq /data

USER stochastiq
WORKDIR /app/api
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=4)"
CMD ["uvicorn", "stochastiq_api.main:app", "--host", "0.0.0.0", "--port", "8000"]
