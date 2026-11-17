// Test de bout en bout : démarre une vraie API (base SQLite et dossier de modèles
// temporaires) et le front. Avant l'API, un modèle de prédiction réduit (lignes à
// 1 couche de data/results_grid.csv) est entraîné dans le dossier temporaire :
// les parcours ne dépendent pas d'un modèle présent sur le poste.
// Lancement : npx playwright test (depuis web/, après npx playwright install chromium).
import { defineConfig } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const API_PORT = 8010;
const WEB_PORT = 5180;
const stamp = Date.now();
const database = path.join(os.tmpdir(), `stochastiq-e2e-${stamp}.db`).replace(/\\/g, "/");
const modelsDir = path.join(os.tmpdir(), `stochastiq-e2e-models-${stamp}`);
// Exécutables du venv du dépôt ; E2E_UVICORN et E2E_PYTHON permettent d'en indiquer d'autres.
const venv = process.platform === "win32" ? "..\\.venv\\Scripts\\" : "../.venv/bin/";
const uvicorn = process.env.E2E_UVICORN ?? `${venv}uvicorn`;
const python = process.env.E2E_PYTHON ?? `${venv}python`;
const train = `${python} ../scripts/train_predictor.py --csv ../data/results_grid.csv --layers 1 --models-dir "${modelsDir}"`;

export default defineConfig({
  testDir: "e2e",
  timeout: 240_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [["list"]],
  use: { baseURL: `http://localhost:${WEB_PORT}`, locale: "fr-FR" },
  webServer: [
    {
      command: `${train} && ${uvicorn} stochastiq_api.main:app --port ${API_PORT}`,
      cwd: "../api",
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: {
        DATABASE_URL: `sqlite:///${database}`,
        MODELS_DIR: modelsDir,
        CORS_ORIGIN: `http://localhost:${WEB_PORT}`,
        ENV: "dev",
        PYTHONIOENCODING: "utf-8",
      },
      reuseExistingServer: false,
      // Entraînement du modèle réduit (environ une minute) puis démarrage de l'API.
      timeout: 300_000,
    },
    {
      command: `npx vite --port ${WEB_PORT} --strictPort`,
      url: `http://localhost:${WEB_PORT}`,
      env: { VITE_API_URL: `http://localhost:${API_PORT}` },
      reuseExistingServer: false,
      timeout: 120_000,
    },
  ],
});
