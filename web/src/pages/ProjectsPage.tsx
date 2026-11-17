import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { api } from "../api/client";
import type { Project } from "../api/types";
import { Empty, ErrorState, Loading } from "../components/common";
import { ROLE_LABELS } from "../lib/roles";
import { useAsync } from "../lib/useAsync";

export function ProjectsPage() {
  const projects = useAsync(() => api.get<Project[]>("/projects"), []);
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const project = await api.post<Project>("/projects", { name, description });
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError((err as Error).message);
      setBusy(false);
    }
  }

  return (
    <>
      <h1>Projets</h1>
      <section className="card" aria-labelledby="nouveau-projet">
        <h2 id="nouveau-projet">Nouveau projet</h2>
        <form onSubmit={create} className="row">
          <label style={{ flex: "1 1 220px" }}>
            Nom
            <input required maxLength={100} value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label style={{ flex: "2 1 320px" }}>
            Description
            <input maxLength={2000} value={description} onChange={(e) => setDescription(e.target.value)} />
          </label>
          <button type="submit" disabled={busy || !name.trim()}>
            Créer le projet
          </button>
        </form>
        {error && <ErrorState message={error} />}
      </section>
      <section className="card" aria-labelledby="mes-projets">
        <h2 id="mes-projets">Mes projets</h2>
        {projects.loading ? (
          <Loading />
        ) : projects.error ? (
          <ErrorState message={projects.error} onRetry={projects.reload} />
        ) : projects.data!.length === 0 ? (
          <Empty>Vous n'êtes membre d'aucun projet. Créez-en un ou acceptez une invitation.</Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Projet</th>
                  <th scope="col">Description</th>
                  <th scope="col">Votre rôle</th>
                </tr>
              </thead>
              <tbody>
                {projects.data!.map((project) => (
                  <tr key={project.id}>
                    <td>
                      <Link to={`/projects/${project.id}`}>{project.name}</Link>
                    </td>
                    <td className="muted">{project.description || "Sans description"}</td>
                    <td>{ROLE_LABELS[project.role]}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  );
}
