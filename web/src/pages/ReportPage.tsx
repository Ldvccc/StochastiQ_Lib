import { Link, useSearchParams } from "react-router-dom";

import { ErrorState, Loading } from "../components/common";
import { useProject } from "../components/ProjectContext";
import { CsvButton } from "../components/science";
import { formatDateTime, formatMetric, formatPercent } from "../lib/format";
import { NOISE_DISCLAIMER, NOISE_TOPOLOGY_LABELS, profileLabel, recommendationSentences, type RecommendationResult } from "../lib/reading";
import { useRunPolling } from "../lib/runs";
import { csvRows, RankingTable } from "./RecommendationPage";

/** Téléchargement d'un objet en JSON (rapport exportable). */
export function downloadJson(filename: string, value: unknown): void {
  const blob = new Blob([JSON.stringify(value, null, 2)], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

/** Rapport imprimable d'une recommandation (feuille de style d'impression dans theme.css). */
export function ReportPage() {
  const { project } = useProject();
  const [params] = useSearchParams();
  const runId = params.get("run") ? Number(params.get("run")) : null;
  const { run, error } = useRunPolling<RecommendationResult>(project.id, runId);
  if (runId === null) return <ErrorState message="Aucune recommandation choisie : ouvrez le rapport depuis l'écran Recommandation." />;
  if (error) return <ErrorState message={error} />;
  if (!run) return <Loading label="Chargement du rapport" />;
  if (run.kind !== "recommendation") return <ErrorState message={`Le run n° ${run.id} n'est pas une recommandation.`} />;
  if (run.status !== "done" || !run.result) return <ErrorState message={`La recommandation n° ${run.id} n'est pas terminée.`} />;
  const result = run.result;
  const p = run.params as Record<string, unknown>;
  const exportParams = { ...p, target: undefined, existing: undefined };
  const intervals = result.items.filter((item) => item.source !== "measured");
  const coverage = intervals.map((item) => item.prediction.final_tvd.coverage);
  return (
    <article className="report">
      <div className="no-print row" style={{ marginBottom: 16 }}>
        <Link to={`/projects/${project.id}/recommandation?run=${run.id}`}>Retour à la recommandation</Link>
        <button type="button" onClick={() => window.print()}>
          Imprimer
        </button>
        <CsvButton filename={`rapport-${run.id}.csv`} rows={csvRows(result)} params={exportParams} />
        <button type="button" className="secondary" onClick={() => downloadJson(`rapport-${run.id}.json`, { run_id: run.id, project: project.name, params: exportParams, result })}>
          Exporter en JSON
        </button>
      </div>
      <h1>Rapport de recommandation</h1>
      <p className="muted">
        Projet « {project.name} », run n° {run.id}, terminé le {run.finished_at ? formatDateTime(run.finished_at) : "n/a"}. StochastiQ, prototype universitaire.
      </p>
      <section className="card" aria-labelledby="rapport-cadre">
        <h2 id="rapport-cadre">Cadre</h2>
        <ul>
          <li>
            Problème « {String(p.problem_name)} » : {result.n_qubits} qubits.
          </li>
          <li>{result.layers} couche(s) par ansatz ; budget de {result.budget} itérations.</li>
          <li>
            {result.noise_profile
              ? `Bruit ${profileLabel(result.noise_profile)}, topologie ${NOISE_TOPOLOGY_LABELS[result.topology]}. ${NOISE_DISCLAIMER}`
              : "Sans bruit : TVD après entraînement exact."}
          </li>
        </ul>
      </section>
      <section className="card" aria-labelledby="rapport-verdict">
        <h2 id="rapport-verdict">Verdict</h2>
        {recommendationSentences(result).map((sentence) => (
          <p key={sentence}>{sentence}</p>
        ))}
      </section>
      <section className="card" aria-labelledby="rapport-classement">
        <h2 id="rapport-classement">Classement</h2>
        <RankingTable result={result} />
        <p className="muted">
          Meilleure référence classique : TVD {formatMetric(result.classical.best_tvd)}, calculée exactement sur la distribution du problème.
        </p>
      </section>
      <section className="card" aria-labelledby="rapport-methode">
        <h2 id="rapport-methode">Méthode et limites</h2>
        <p>
          Les TVD non mesurées sont prédites par l'IA de StochastiQ (gradient boosting) à partir des caractéristiques du circuit, du problème et du bruit. Un entraînement
          déjà fait dans le projet, sur le même problème et le même nombre de couches, prime sur la prédiction.
        </p>
        <p>
          Un intervalle 10-90 % n'est affiché que si sa couverture mesurée en validation, pour un cas comparable, est entre 70 % et 90 %
          {coverage.length > 0 ? ` (couvertures des cas de ce rapport : ${[...new Set(coverage.map(formatPercent))].join(", ")})` : ""}. Sans intervalle fiable, la
          prédiction est entourée d'une marge de deux fois son erreur moyenne de validation, et le verdict n'est que « probable ».
        </p>
        <p>
          Une TVD mesurée (une seule initialisation) n'a pas d'intervalle : elle n'est jugée meilleure ou moins bonne que la référence classique que si l'écart dépasse
          10 % ; sinon, elle lui est équivalente.
        </p>
        <p>
          Les colonnes Expressibilité, Intrication et Variance du gradient viennent d'un diagnostic léger ({String(p.n_samples ?? 200)} échantillons) : elles sont
          données à titre indicatif, l'expressibilité est surestimée sous 1000 échantillons, et elles n'entrent pas dans la prédiction, qui ne repose que sur la
          structure du circuit, le problème et le bruit.
        </p>
        <p>
          Budget de {result.budget} itérations, soit {result.decision.n_trainings} entraînement(s) de 200 itérations : seuls les ansatz les mieux classés parmi ceux
          qui restent à départager sont proposés à l'entraînement ; un ansatz déjà entraîné dans le projet n'est jamais proposé.
        </p>
        <p>Une seule initialisation par entraînement ; simulation, sans machine réelle. Le détail de la validation est décrit dans docs/PREDICTION.md.</p>
      </section>
    </article>
  );
}
