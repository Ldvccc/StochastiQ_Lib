// Session : jeton en mémoire et dans sessionStorage.
//
// Compromis : sessionStorage garde la session au rechargement de l'onglet et
// l'efface à sa fermeture, mais reste lisible par un script injecté (XSS).
// Un cookie HttpOnly serait plus sûr ; il demanderait une gestion CSRF, hors
// périmètre de ce prototype.

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { useLocation, useNavigate } from "react-router-dom";

import { api, setToken, setUnauthorizedHandler } from "../api/client";
import type { Token, User } from "../api/types";

const STORAGE_KEY = "stochastiq.token";

interface AuthState {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | null>(null);

function readStoredToken(): string | null {
  try {
    return sessionStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeToken(value: string | null): void {
  setToken(value);
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, value);
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // Stockage indisponible : la session reste en mémoire seulement.
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  const logout = useCallback(() => {
    storeToken(null);
    setUser(null);
  }, []);

  useEffect(() => {
    setUnauthorizedHandler(() => {
      logout();
      const next = encodeURIComponent(location.pathname + location.search);
      navigate(`/login?next=${next}`, { replace: true });
    });
  }, [logout, navigate, location.pathname, location.search]);

  useEffect(() => {
    const stored = readStoredToken();
    if (!stored) {
      setLoading(false);
      return;
    }
    setToken(stored);
    api
      .get<User>("/me")
      .then(setUser)
      .catch(() => storeToken(null))
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const token = await api.post<Token>("/auth/login", { email, password });
    storeToken(token.access_token);
    setUser(await api.get<User>("/me"));
  }, []);

  const register = useCallback(
    async (email: string, name: string, password: string) => {
      await api.post<User>("/auth/register", { email, name, password });
      await login(email, password);
    },
    [login],
  );

  const value = useMemo(() => ({ user, loading, login, register, logout }), [user, loading, login, register, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé dans AuthProvider");
  return context;
}
