/// <reference types="vitest" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173 },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    // Le parcours de bout en bout (e2e/) relève de Playwright, pas de Vitest.
    include: ["src/**/*.test.{ts,tsx}"],
    testTimeout: 15_000,
    css: false,
  },
});
