const IconUpload = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

const IconChart = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </svg>
);

const IconDoc = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
    <polyline points="14 2 14 8 20 8" />
    <line x1="16" y1="13" x2="8" y2="13" />
    <line x1="16" y1="17" x2="8" y2="17" />
  </svg>
);

const IconShield = () => (
  <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
  </svg>
);

const steps = [
  {
    icon: <IconUpload />,
    title: "Importez",
    text: "Chargez vos fichiers CSV ou XLSX en quelques secondes.",
  },
  {
    icon: <IconChart />,
    title: "Analysez",
    text: "Notre moteur détecte et analyse automatiquement vos données.",
  },
  {
    icon: <IconDoc />,
    title: "Décidez",
    text: "Recevez un rapport PDF avec des recommandations IA actionnables.",
  },
];

export default function OnboardingPage({ onStart }) {
  return (
    <main className="home-page">
      <section className="hero-section">
        <p className="hero-pill">
          <IconChart />
          Analyse intelligente des ventes
        </p>
        <h2>
          Transformez vos ventes en <span>décisions</span>
        </h2>
        <p>
          Importez vos données, obtenez un dashboard complet et des recommandations IA
          pour booster votre performance commerciale.
        </p>
        <button type="button" className="top-action-btn hero-cta" onClick={onStart}>
          Commencer votre analyse →
        </button>
      </section>

      <section className="preview-frame">
        <div className="mock-dashboard">
          <div className="mock-head">
            <div className="mock-dot" />
            <p>SalesIQ Dashboard</p>
            <div className="mock-head-nav">
              <span>Ventes</span>
              <span>Produits</span>
              <span>Budget</span>
            </div>
          </div>
          <div className="mock-grid">
            <article className="mock-card mock-chart">
              <p>Ventes du mois</p>
              <div className="mock-sparkline">
                <svg viewBox="0 0 200 60" preserveAspectRatio="none">
                  <polyline fill="none" stroke="#2f9f6b" strokeWidth="2.5"
                    points="0,50 20,38 40,42 60,28 80,30 100,18 120,22 140,12 160,8 180,6 200,4" />
                  <polyline fill="none" stroke="#cde9dc" strokeWidth="1.5"
                    points="0,55 20,50 40,52 60,44 80,46 100,40 120,42 140,36 160,32 180,28 200,24" />
                </svg>
              </div>
            </article>
            <div className="mock-side">
              <article className="mock-card mock-stat">
                <span className="mock-stat-label">Revenus</span>
                <span className="mock-stat-value">$48 230</span>
                <span className="mock-stat-delta">↑ 12%</span>
              </article>
              <article className="mock-card mock-stat light">
                <span className="mock-stat-label">Clients</span>
                <span className="mock-stat-value">1 284</span>
                <span className="mock-stat-delta">↑ 8%</span>
              </article>
              <article className="mock-card mock-stat light">
                <span className="mock-stat-label">Panier moyen</span>
                <span className="mock-stat-value">$37.6</span>
              </article>
              <article className="mock-card mock-stat">
                <span className="mock-stat-label">Taux conv.</span>
                <span className="mock-stat-value">3.4%</span>
              </article>
            </div>
          </div>
          <div className="mock-grid two">
            <article className="mock-card mock-chart short">
              <p>Ventes par région</p>
              <div className="mock-sparkline">
                <svg viewBox="0 0 200 50" preserveAspectRatio="none">
                  <polyline fill="none" stroke="#2f9f6b" strokeWidth="2.5"
                    points="0,40 30,30 60,28 90,20 120,18 150,12 180,8 200,4" />
                </svg>
              </div>
            </article>
            <article className="mock-card mock-chart short">
              <p>KPI Dashboard</p>
              <div className="mock-sparkline">
                <svg viewBox="0 0 200 50" preserveAspectRatio="none">
                  <polyline fill="none" stroke="#2f9f6b" strokeWidth="2.5"
                    points="0,45 30,38 60,40 90,28 120,26 150,16 180,10 200,6" />
                  <polyline fill="none" stroke="#cde9dc" strokeWidth="1.5"
                    points="0,50 30,46 60,48 90,40 120,38 150,30 180,22 200,18" />
                </svg>
              </div>
            </article>
          </div>
        </div>
      </section>

      <section className="how-section">
        <h3>Comment ça marche</h3>
        <p>Trois étapes simples vers des insights actionnables</p>
        <div className="steps-grid">
          {steps.map((step) => (
            <article className="step-card" key={step.title}>
              <div className="step-icon">{step.icon}</div>
              <h4>{step.title}</h4>
              <p>{step.text}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="privacy-card">
        <div className="privacy-icon"><IconShield /></div>
        <h4>Vos données restent privées</h4>
        <p>
          Tout le traitement se fait localement dans votre navigateur. Aucune donnée n&apos;est
          envoyée à un serveur.
        </p>
      </section>

      <footer className="home-footer">© 2026 SalesIQ. Analyse intelligente des ventes.</footer>
    </main>
  );
}
