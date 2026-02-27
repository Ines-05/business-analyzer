import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";

import { getAnalysisResult } from "../api";

export default function ReportPage({ onOpenDashboard, onGoUpload }) {
  const { analysisId } = useParams();
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!analysisId) {
      setData(null);
      setLoading(false);
      setError("No dashboard selected yet.");
      return;
    }

    let mounted = true;
    setLoading(true);
    setError("");

    getAnalysisResult(analysisId)
      .then((payload) => {
        if (!mounted) {
          return;
        }
        setData(payload);
        setLoading(false);
      })
      .catch((err) => {
        if (!mounted) {
          return;
        }
        setError(err.message || "Could not load analysis.");
        setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, [analysisId]);

  if (loading) {
    return (
      <main className="page-grid">
        <section className="glass loading-card">
          <p>Chargement du rapport...</p>
        </section>
      </main>
    );
  }

  if (error || !data) {
    return (
      <main className="page-grid">
        <section className="glass loading-card">
          <p>{error || "Rapport introuvable."}</p>
          <button type="button" className="primary-btn" onClick={onGoUpload}>
            Retour a l import
          </button>
        </section>
      </main>
    );
  }

  const charts = (data.charts || []).filter((row) => row.available);
  const reportUrl = `/api/analyses/${data.analysis_id}/report?download=true`;
  const recommendationCount = (data.recommendations || []).length;
  const visualCount = (data.visual_insights || []).length;

  return (
    <main className="report-page">
      <section className="dashboard-title">
        <div>
          <h2>Rapport IA</h2>
          <p>
            Exportez un document PDF avec vos KPIs, visuels et recommandations.
          </p>
        </div>
        <div className="dashboard-title-actions">
          <span className="pill">{data.analysis_id}</span>
          <a className="top-action-btn" href={reportUrl}>
            Telecharger le report IA
          </a>
          <button type="button" className="ghost-btn" onClick={() => onOpenDashboard(data.analysis_id)}>
            Voir dashboard
          </button>
          <button type="button" className="ghost-btn" onClick={onGoUpload}>
            Nouveau fichier
          </button>
        </div>
      </section>

      <section className="metrics-grid">
        <article className="metric-card">
          <p>Charts disponibles</p>
          <h3>{charts.length}</h3>
          <span>Images exportables</span>
        </article>
        <article className="metric-card">
          <p>Recommandations</p>
          <h3>{recommendationCount}</h3>
          <span>Actions prioritaires</span>
        </article>
        <article className="metric-card">
          <p>Insights visuels</p>
          <h3>{visualCount}</h3>
          <span>Lectures graphiques</span>
        </article>
      </section>

      {charts.length === 0 && (
        <section className="dashboard-panel">
          <h3>Exports graphiques</h3>
          <p className="empty-text">Aucun graphique n est disponible pour cette analyse.</p>
        </section>
      )}

      {charts.length > 0 && (
        <section className="dashboard-panel">
          <h3>Exports graphiques</h3>
          <div className="download-grid">
            {charts.map((chart) => (
              <div className="download-card" key={chart.id}>
                <img src={chart.url} alt={chart.label} />
                <a href={chart.download_url}>Telecharger {chart.label}</a>
              </div>
            ))}
          </div>
        </section>
      )}
    </main>
  );
}
