import { useEffect, useMemo, useState } from "react";
import { Navigate, Route, Routes, useLocation, useNavigate } from "react-router-dom";

import { getAnalyses } from "./api";
import DashboardPage from "./pages/DashboardPage";
import OnboardingPage from "./pages/OnboardingPage";
import ReportPage from "./pages/ReportPage";
import UploadPage from "./pages/UploadPage";

export default function App() {
  const [analyses, setAnalyses] = useState([]);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();
  const location = useLocation();

  async function refreshAnalyses() {
    setLoading(true);
    try {
      const payload = await getAnalyses(6);
      setAnalyses(payload.items || []);
    } catch {
      setAnalyses([]);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshAnalyses();
  }, []);

  const latestAnalysisId = analyses[0]?.analysis_id || null;
  const isHome = location.pathname === "/";
  const isDashboard = location.pathname.startsWith("/dashboard/");
  const isReport = location.pathname.startsWith("/report/");
  const activeAnalysisId = useMemo(() => {
    const parts = location.pathname.split("/");
    if (parts.length >= 3 && (parts[1] === "dashboard" || parts[1] === "report")) {
      return parts[2];
    }
    return latestAnalysisId;
  }, [location.pathname, latestAnalysisId]);

  function goBack() {
    if (window.history.length > 1) {
      navigate(-1);
      return;
    }
    navigate("/");
  }

  return (
    <div className="app-shell salesiq-shell">
      <header className="topbar salesiq-topbar">
        <div className="topbar-left">
          {!isHome && (
            <button type="button" className="back-btn" onClick={goBack} aria-label="Back">
              &larr;
            </button>
          )}
          <div className="brand-wrap">
            <div className="logo-dot" />
            <div className="brand-copy">
              <h1>SalesIQ</h1>
            </div>
          </div>
        </div>

        <div className="topbar-right">
          {isDashboard && activeAnalysisId && (
            <button type="button" className="top-action-btn" onClick={() => navigate(`/report/${activeAnalysisId}`)}>
              Telecharger le report IA
            </button>
          )}
          {isReport && activeAnalysisId && (
            <a className="top-action-btn" href={`/api/analyses/${activeAnalysisId}/report?download=true`}>
              Telecharger le report IA
            </a>
          )}
        </div>
      </header>

      {loading && (
        <section className="loading-shell">
          <p>Chargement des analyses...</p>
        </section>
      )}

      {!loading && (
        <div className="page-body">
          <Routes>
            <Route
              path="/"
              element={<OnboardingPage onStart={() => navigate("/upload")} />}
            />
            <Route
              path="/upload"
              element={
                <UploadPage
                  onRefresh={refreshAnalyses}
                  onOpenDashboard={(id) => navigate(`/dashboard/${id}`)}
                  onOpenReport={(id) => navigate(`/report/${id}`)}
                />
              }
            />
            <Route
              path="/dashboard/:analysisId"
              element={
                <DashboardPage
                  onOpenReport={(id) => navigate(`/report/${id}`)}
                  onGoUpload={() => navigate("/upload")}
                />
              }
            />
            <Route
              path="/report/:analysisId"
              element={
                <ReportPage
                  analyses={analyses}
                  onOpenDashboard={(id) => navigate(`/dashboard/${id}`)}
                  onGoUpload={() => navigate("/upload")}
                />
              }
            />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      )}
    </div>
  );
}
