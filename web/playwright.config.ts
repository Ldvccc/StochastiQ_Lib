// Test de bout en bout : démarre une vraie API (base SQLite temporaire) et le front.
// Lancement : npx playwright test (depuis web/, après npx playwright install chromium).
import { defineConfig } from "@playwright/test";
import os from "node:os";
import path from "node:path";

const API_PORT = 8010;
const WEB_PORT = 5180;
const database = path.join(os.tmpdir(), `stochastiq-e2e-${Date.now()}.db`).replace(/\\/g, "/");
// Commande uvicorn du venv du dépôt ; E2E_UVICORN permet d'en indiquer une autre.
const uvicorn =
  process.env.E2E_UVICORN ?? (process.platform === "win32" ? "..\\.venv\\Scripts\\uvicorn" : "../.venv/bin/uvicorn");

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
      command: `${uvicorn} stochastiq_api.main:app --port ${API_PORT}`,
      cwd: "../api",
      url: `http://127.0.0.1:${API_PORT}/health`,
      env: { DATABASE_URL: `sqlite:///${database}`, CORS_ORIGIN: `http://localhost:${WEB_PORT}`, ENV: "dev" },
      reuseExistingServer: false,
      timeout: 120_000,
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
