import "@testing-library/jest-dom/vitest";
import { cleanup, configure } from "@testing-library/react";
import { afterEach } from "vitest";

// Délai des requêtes asynchrones (findBy…) : 1 s par défaut, trop court quand toute la
// suite tourne en parallèle sur une machine chargée.
configure({ asyncUtilTimeout: 4000 });

afterEach(() => {
  cleanup();
  sessionStorage.clear();
});
