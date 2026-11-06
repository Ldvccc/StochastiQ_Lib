import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AuthProvider } from "../auth/AuthContext";
import { LoginPage, RegisterPage, registerErrors } from "../pages/AuthPages";

function json(status: number, body: unknown) {
  return Promise.resolve(new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } }));
}

function renderAt(path: string) {
  return render(
    <MemoryRouter initialEntries={[path]} future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <AuthProvider>
        <Routes>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
          <Route path="/projects" element={<p>Liste des projets</p>} />
          <Route path="/projects/7" element={<p>Projet 7</p>} />
        </Routes>
      </AuthProvider>
    </MemoryRouter>,
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("connexion", () => {
  it("connecte l'utilisateur et suit le paramètre next", async () => {
    const fetchMock = vi.fn((url: string, _init?: RequestInit) =>
      url.endsWith("/auth/login")
        ? json(200, { access_token: "jeton", token_type: "bearer", expires_in: 43200 })
        : json(200, { id: 1, email: "a@example.test", name: "Ada", created_at: "2026-01-01T00:00:00" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderAt("/login?next=%2Fprojects%2F7");
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), "a@example.test");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "motdepasse-solide");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByText("Projet 7")).toBeInTheDocument();
    const [, init] = fetchMock.mock.calls.find(([url]) => url.endsWith("/auth/login"))!;
    expect(JSON.parse(String(init?.body))).toEqual({ email: "a@example.test", password: "motdepasse-solide" });
    expect(sessionStorage.getItem("stochastiq.token")).toBe("jeton");
  });

  it("affiche l'erreur de l'API", async () => {
    vi.stubGlobal("fetch", vi.fn(() => json(401, { detail: "E-mail ou mot de passe incorrect." })));
    renderAt("/login");
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), "a@example.test");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "mauvais");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("E-mail ou mot de passe incorrect.");
  });

  it("refuse une redirection vers un autre site", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: string) =>
        url.endsWith("/auth/login")
          ? json(200, { access_token: "jeton", token_type: "bearer", expires_in: 1 })
          : json(200, { id: 1, email: "a@example.test", name: "Ada", created_at: "2026-01-01T00:00:00" }),
      ),
    );
    renderAt("/login?next=%2F%2Fmalveillant.test");
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), "a@example.test");
    await userEvent.type(screen.getByLabelText("Mot de passe"), "motdepasse-solide");
    await userEvent.click(screen.getByRole("button", { name: "Se connecter" }));
    expect(await screen.findByText("Liste des projets")).toBeInTheDocument();
  });
});

describe("inscription", () => {
  it("valide les champs avant tout appel à l'API", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderAt("/register");
    await userEvent.type(screen.getByLabelText("Nom"), "Ada");
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), "ada@example.test");
    await userEvent.type(screen.getByLabelText(/^Mot de passe/), "court");
    await userEvent.type(screen.getByLabelText("Confirmation du mot de passe"), "autre");
    await userEvent.click(screen.getByRole("button", { name: "Créer le compte" }));
    expect(screen.getByText("Le mot de passe doit compter au moins 10 caractères.")).toBeInTheDocument();
    expect(screen.getByText("Les deux mots de passe ne correspondent pas.")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("crée le compte puis connecte l'utilisateur", async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith("/auth/register")) return json(201, { id: 2, email: "b@example.test", name: "Bob", created_at: "" });
      if (url.endsWith("/auth/login")) return json(200, { access_token: "jeton", token_type: "bearer", expires_in: 1 });
      return json(200, { id: 2, email: "b@example.test", name: "Bob", created_at: "" });
    });
    vi.stubGlobal("fetch", fetchMock);
    renderAt("/register");
    await userEvent.type(screen.getByLabelText("Nom"), "Bob");
    await userEvent.type(screen.getByLabelText("Adresse e-mail"), "b@example.test");
    await userEvent.type(screen.getByLabelText(/^Mot de passe/), "motdepasse-solide");
    await userEvent.type(screen.getByLabelText("Confirmation du mot de passe"), "motdepasse-solide");
    await userEvent.click(screen.getByRole("button", { name: "Créer le compte" }));
    await waitFor(() => expect(screen.getByText("Liste des projets")).toBeInTheDocument());
  });

  it("règles de validation", () => {
    expect(registerErrors("Ada", "ada@example.test", "motdepasse-solide", "motdepasse-solide")).toEqual({});
    expect(Object.keys(registerErrors("", "pas-un-email", "123456789", "x")).sort()).toEqual([
      "confirmation",
      "email",
      "name",
      "password",
    ]);
  });
});
