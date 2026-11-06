import { useState, type FormEvent } from "react";
import { Link, Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { ErrorState, Loading, Logo } from "../components/common";

export const MIN_PASSWORD_LENGTH = 10;

function useNext(): string {
  const [params] = useSearchParams();
  const next = params.get("next");
  // N'accepte qu'un chemin interne, pour éviter une redirection ouverte.
  return next && next.startsWith("/") && !next.startsWith("//") ? next : "/projects";
}

export function LoginPage() {
  const { login } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setBusy(true);
    try {
      await login(email, password);
      navigate(next, { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="auth-page">
      <div className="card">
        <Logo to="/login" />
        <h1>Connexion</h1>
        <form onSubmit={submit} noValidate>
          {error && <ErrorState message={error} />}
          <label>
            Adresse e-mail
            <input type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </label>
          <label>
            Mot de passe
            <input
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </label>
          <button type="submit" disabled={busy || !email || !password}>
            {busy ? "Connexion…" : "Se connecter"}
          </button>
          <p className="muted">
            Pas encore de compte ? <Link to={`/register?next=${encodeURIComponent(next)}`}>Créer un compte</Link>
          </p>
        </form>
      </div>
    </div>
  );
}

/** Erreurs de saisie du formulaire d'inscription (vide si tout est valide). */
export function registerErrors(name: string, email: string, password: string, confirmation: string): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!name.trim()) errors.name = "Indiquez votre nom.";
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = "Adresse e-mail invalide.";
  if (password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Le mot de passe doit compter au moins ${MIN_PASSWORD_LENGTH} caractères.`;
  }
  if (confirmation !== password) errors.confirmation = "Les deux mots de passe ne correspondent pas.";
  return errors;
}

export function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();
  const next = useNext();
  const [form, setForm] = useState({ name: "", email: "", password: "", confirmation: "" });
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const errors = registerErrors(form.name, form.email, form.password, form.confirmation);

  function field(key: keyof typeof form) {
    return { value: form[key], onChange: (e: { target: { value: string } }) => setForm({ ...form, [key]: e.target.value }) };
  }

  async function submit(event: FormEvent) {
    event.preventDefault();
    setSubmitted(true);
    if (Object.keys(errors).length > 0) return;
    setError(null);
    setBusy(true);
    try {
      await register(form.email, form.name, form.password);
      navigate(next, { replace: true });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  const show = (key: string) =>
    submitted && errors[key] ? (
      <span className="field-error" id={`erreur-${key}`}>
        {errors[key]}
      </span>
    ) : null;
  const describedBy = (key: string) => (submitted && errors[key] ? `erreur-${key}` : undefined);

  return (
    <div className="auth-page">
      <div className="card">
        <Logo to="/login" />
        <h1>Créer un compte</h1>
        <form onSubmit={submit} noValidate>
          {error && <ErrorState message={error} />}
          <label>
            Nom
            <input autoComplete="name" aria-describedby={describedBy("name")} {...field("name")} />
            {show("name")}
          </label>
          <label>
            Adresse e-mail
            <input type="email" autoComplete="email" aria-describedby={describedBy("email")} {...field("email")} />
            {show("email")}
          </label>
          <label>
            Mot de passe ({MIN_PASSWORD_LENGTH} caractères au moins)
            <input
              type="password"
              autoComplete="new-password"
              aria-describedby={describedBy("password")}
              {...field("password")}
            />
            {show("password")}
          </label>
          <label>
            Confirmation du mot de passe
            <input
              type="password"
              autoComplete="new-password"
              aria-describedby={describedBy("confirmation")}
              {...field("confirmation")}
            />
            {show("confirmation")}
          </label>
          <button type="submit" disabled={busy}>
            {busy ? "Création…" : "Créer le compte"}
          </button>
          <p className="muted">
            Déjà inscrit ? <Link to={`/login?next=${encodeURIComponent(next)}`}>Se connecter</Link>
          </p>
        </form>
      </div>
    </div>
  );
}

export function RequireAuth({ children }: { children: JSX.Element }) {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Vérification de la session" />;
  if (!user) {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    return <Navigate to={`/login?next=${next}`} replace />;
  }
  return children;
}
