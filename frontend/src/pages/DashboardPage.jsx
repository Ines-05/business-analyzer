import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";

import { getAnalysisResult, getRawRows } from "../api";
import {
  CategoryChart,
  ProductMixChart,
  ProductsChart,
  QuantityChart,
  RegionChart,
  RepChart,
  TrendChart,
} from "../components/Charts";

// 
// Helpers
// 
function dateRangeLabel(range) {
  if (range?.min && range?.max && range.min !== range.max) return `${range.min}  ${range.max}`;
  if (range?.min) return range.min;
  return null;
}

function formatCurrency(value) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: 0 }).format(Number(value || 0));
}

function formatPct(value) {
  const n = Number(value || 0);
  return `${n >= 0 ? "+" : ""}${n.toFixed(1)}%`;
}

// 
// Cross-filter helpers
// 
function applyFilters(rows, { region, category, rep }, exclude = null) {
  return rows.filter((r) => {
    if (exclude !== "region"   && region   && r.region    !== region)   return false;
    if (exclude !== "category" && category && r.category  !== category) return false;
    if (exclude !== "rep"      && rep      && r.sales_rep !== rep)      return false;
    return true;
  });
}

function aggTrend(rows) {
  const map = {};
  for (const r of rows) map[r.order_date] = (map[r.order_date] || 0) + r.revenue;
  return Object.entries(map)
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([period, revenue]) => ({ period, revenue }));
}

function aggProducts(rows) {
  const map = {};
  for (const r of rows) map[r.product] = (map[r.product] || 0) + r.revenue;
  return Object.entries(map)
    .sort(([, a], [, b]) => b - a)
    .map(([product, revenue]) => ({ product, revenue }));
}

function aggShare(rows) {
  const map = {};
  let total = 0;
  for (const r of rows) { map[r.product] = (map[r.product] || 0) + r.revenue; total += r.revenue; }
  if (!total) return [];
  return Object.entries(map)
    .sort(([, a], [, b]) => b - a)
    .map(([name, rev]) => ({ name, value: (rev / total) * 100 }));
}

function aggDim(rows, field, valueKey = "revenue") {
  const map = {};
  for (const r of rows) {
    const key = r[field];
    if (!key) continue;
    map[key] = (map[key] || 0) + (valueKey === "quantity" ? Number(r.quantity || 0) : r.revenue);
  }
  return Object.entries(map)
    .sort(([, a], [, b]) => b - a)
    .map(([k, v]) => ({ [field]: k, [valueKey]: v }));
}

// 
// ChartPanel wrapper
// 
function ChartPanel({ title, subtitle, height = 280, children, interactive = false, active = false }) {
  const cls = [
    "db-panel",
    interactive ? "db-panel--interactive" : "",
    active      ? "db-panel--active"      : "",
  ].filter(Boolean).join(" ");

  return (
    <div className={cls}>
      <div className="db-panel-header">
        <p className="db-panel-title">{title}</p>
        {subtitle && <p className="db-panel-sub">{subtitle}</p>}
      </div>
      <div className="db-chart-area" style={{ height }}>
        {children}
      </div>
    </div>
  );
}

// 
// Dashboard
// 
export default function DashboardPage({ onOpenReport, onGoUpload }) {
  const { analysisId } = useParams();
  const [data,    setData]    = useState(null);
  const [loading, setLoading] = useState(true);
  const [error,   setError]   = useState("");

  // Raw rows for cross-filtering
  const [rawRows, setRawRows] = useState([]);
  const [filters, setFilters] = useState({ region: null, category: null, rep: null });

  // Fetch analysis result
  useEffect(() => {
    if (!analysisId) return;
    let mounted = true;
    setLoading(true);
    setError("");
    getAnalysisResult(analysisId)
      .then((p) => { if (mounted) { setData(p); setLoading(false); } })
      .catch((e) => { if (mounted) { setError(e.message || "Erreur chargement."); setLoading(false); } });
    return () => { mounted = false; };
  }, [analysisId]);

  // Fetch raw rows (best-effort  older analyses may not have them)
  useEffect(() => {
    if (!analysisId) return;
    getRawRows(analysisId)
      .then((p) => setRawRows(p.rows || []))
      .catch(() => setRawRows([]));
  }, [analysisId]);

  //  Cross-filter derivations 
  const hasRaw = rawRows.length > 0;

  const filteredAll      = useMemo(() => applyFilters(rawRows, filters),            [rawRows, filters]);
  const filteredForRegion = useMemo(() => applyFilters(rawRows, filters, "region"), [rawRows, filters]);
  const filteredForCat   = useMemo(() => applyFilters(rawRows, filters, "category"),[rawRows, filters]);
  const filteredForRep   = useMemo(() => applyFilters(rawRows, filters, "rep"),     [rawRows, filters]);

  // Toggle a single filter value (click again to clear)
  function toggle(key, value) {
    setFilters((f) => ({ ...f, [key]: f[key] === value ? null : value }));
  }
  function clearFilters() { setFilters({ region: null, category: null, rep: null }); }

  //  Loading / error states 
  if (loading) return (
    <main className="page-grid">
      <section className="glass loading-card"><p>Chargement du dashboard</p></section>
    </main>
  );

  if (error || !data) return (
    <main className="page-grid">
      <section className="glass loading-card">
        <p>{error || "Dashboard introuvable."}</p>
        <button type="button" className="primary-btn" onClick={onGoUpload}>Retour à l&apos;import</button>
      </section>
    </main>
  );

  //  Pre-computed API data (fallback when no raw rows) 
  const kpis    = data.kpis    || {};
  const kpiDisp = data.kpi_display || {};
  const meta    = data.meta    || {};
  const trend0     = data.revenue_trend || [];
  const products0  = data.top_products  || [];
  const share0     = data.product_share || [];
  const regions0   = data.by_region     || [];
  const categories0= data.by_category   || [];
  const reps0      = data.by_rep        || [];
  const quantities0= data.by_quantity   || [];

  //  Live filtered chart data 
  const fTrend     = hasRaw ? aggTrend(filteredAll)    : trend0;
  const fProducts  = hasRaw ? aggProducts(filteredAll) : products0;
  const fShare     = hasRaw ? aggShare(filteredAll)    : share0;

  const fRegions   = hasRaw
    ? aggDim(filteredForRegion, "region").map((r) => ({ region: r.region, revenue: r.revenue }))
    : regions0;
  const fCategories= hasRaw
    ? aggDim(filteredForCat, "category").map((r) => ({ category: r.category, revenue: r.revenue }))
    : categories0;
  const fReps      = hasRaw
    ? aggDim(filteredForRep, "sales_rep").map((r) => ({ rep: r.sales_rep, revenue: r.revenue }))
    : reps0;
  const fQuantities= hasRaw
    ? aggDim(filteredAll, "product", "quantity").map((r) => ({ product: r.product, quantity: r.quantity }))
    : quantities0;

  //  KPI cards 
  const kpiCards = [
    { key:"revenue",  label:"Chiffre d'affaires", value: kpiDisp.totalRevenue?.value  || formatCurrency(kpis.total_revenue),  delta: kpiDisp.totalRevenue?.delta, positive: kpiDisp.totalRevenue?.positive ?? true },
    { key:"orders",   label:"Transactions",        value: kpiDisp.totalOrders?.value   || String(kpis.total_orders ?? ""),     delta: null },
    { key:"aov",      label:"Panier moyen",        value: kpiDisp.avgOrderValue?.value || formatCurrency(kpis.avg_order_value), delta: null },
    { key:"top",      label:"Top produit",         value: kpiDisp.topProduct?.value    || kpis.top_product?.product || "",     delta: kpiDisp.topProduct?.share || (kpis.top_product?.share_pct ? `${kpis.top_product.share_pct.toFixed(1)}% du CA` : null) },
    { key:"growth",   label:"Croissance",          value: kpiDisp.periodGrowth?.value  || (kpis.period_growth_pct !== undefined ? formatPct(kpis.period_growth_pct) : ""), delta: null, positive: Number(kpis.period_growth_pct || 0) >= 0 },
  ];

  //  Visibility flags 
  const hasTrend     = fTrend.length     >= 2;
  const hasShare     = fShare.length     >= 2;
  const hasProducts  = fProducts.length  >= 2;
  const hasCategory  = fCategories.length >= 2;
  const hasRegion    = fRegions.length   >= 2;
  const hasRep       = fReps.length      >= 2;
  const hasQuantity  = fQuantities.length >= 2;
  const hasFilters   = !!(filters.region || filters.category || filters.rep);

  const optionalPanels = [
    hasRegion   && { key:"region",   title:"Revenus par région",       subtitle:`${fRegions.length} régions`,      node:<RegionChart   regions={fRegions}     onSelect={hasRaw ? (v) => toggle("region",   v) : undefined} selected={filters.region}   />, height: Math.max(200, fRegions.length    * 36 + 40), interactive: hasRaw },
    hasRep      && { key:"rep",      title:"Revenus par commercial",   subtitle:`${fReps.length} commerciaux`,     node:<RepChart      reps={fReps}           onSelect={hasRaw ? (v) => toggle("rep",      v) : undefined} selected={filters.rep}      />, height: Math.max(200, fReps.length       * 36 + 40), interactive: hasRaw },
    hasQuantity && { key:"qty",      title:"Unités vendues",           subtitle:"par produit",                     node:<QuantityChart quantities={fQuantities}/>,                                                                                          height: Math.max(200, Math.min(fQuantities.length, 8) * 36 + 40) },
  ].filter(Boolean);

  const recommendations      = data.recommendations      || [];
  const recommendationsSource= data.recommendations_source || "unknown";

  return (
    <main className="db-page">

      {/*  Header  */}
      <header className="db-header">
        <div className="db-header-left">
          <h2 className="db-title">{data.company_name || "Dashboard"}</h2>
          <div className="db-meta-row">
            {meta.source_file && <span className="db-meta-pill">{meta.source_file}</span>}
            {meta.row_count   && <span className="db-meta-pill">{meta.row_count} lignes</span>}
            {dateRangeLabel(meta.date_range) && <span className="db-meta-pill">{dateRangeLabel(meta.date_range)}</span>}
            <span className="db-meta-pill muted">{data.analysis_id}</span>
          </div>
        </div>
        <div className="db-header-actions">
          <button type="button" className="ghost-btn" onClick={onGoUpload}>Nouveau fichier</button>
          <button type="button" className="primary-btn" onClick={() => onOpenReport(data.analysis_id)}>Rapport PDF</button>
        </div>
      </header>

      {/*  KPI row  */}
      <section className="db-kpi-row">
        {kpiCards.map((card) => (
          <div key={card.key} className="db-kpi-card">
            <p className="db-kpi-label">{card.label}</p>
            <p className="db-kpi-value">{card.value}</p>
            {card.delta && (
              <p className={`db-kpi-delta ${card.positive !== false ? "positive" : "negative"}`}>{card.delta}</p>
            )}
          </div>
        ))}
      </section>

      {/*  Active-filter bar  */}
      {hasFilters && (
        <div className="db-filter-bar">
          <span className="db-filter-label">Filtres actifs :</span>
          {filters.region && (
            <button className="db-filter-chip" onClick={() => toggle("region", filters.region)}>
              Région : {filters.region} &times;
            </button>
          )}
          {filters.category && (
            <button className="db-filter-chip" onClick={() => toggle("category", filters.category)}>
              Catégorie : {filters.category} &times;
            </button>
          )}
          {filters.rep && (
            <button className="db-filter-chip" onClick={() => toggle("rep", filters.rep)}>
              Commercial : {filters.rep} &times;
            </button>
          )}
          <button className="db-filter-clear" onClick={clearFilters}>Tout effacer</button>
        </div>
      )}

      {/*  Row 1 : Trend + Product Mix  */}
      <section className={`db-row ${hasTrend && hasShare ? "db-row--70-30" : ""}`}>
        <ChartPanel title="Tendance des revenus" subtitle={`${fTrend.length} période${fTrend.length > 1 ? "s" : ""}`} height={260}>
          <TrendChart trend={fTrend} />
        </ChartPanel>
        {hasShare && (
          <ChartPanel title="Répartition du CA" subtitle="par produit" height={260}>
            <ProductMixChart share={fShare} />
          </ChartPanel>
        )}
      </section>

      {/*  Row 2 : Top Products + Category  */}
      {(hasProducts || hasCategory) && (
        <section className={`db-row ${hasProducts && hasCategory ? "db-row--50-50" : ""}`}>
          {hasProducts && (
            <ChartPanel title="Top produits" subtitle={`${Math.min(fProducts.length, 8)} produits par CA`} height={Math.max(220, Math.min(fProducts.length, 8) * 38 + 40)}>
              <ProductsChart products={fProducts} />
            </ChartPanel>
          )}
          {hasCategory && (
            <ChartPanel
              title="Revenus par catégorie"
              subtitle={`${fCategories.length} catégories`}
              height={Math.max(220, fCategories.length * 38 + 40)}
              interactive={hasRaw}
              active={!!filters.category}
            >
              <CategoryChart
                categories={fCategories}
                onSelect={hasRaw ? (v) => toggle("category", v) : undefined}
                selected={filters.category}
              />
            </ChartPanel>
          )}
        </section>
      )}

      {/*  Row 3 : Region / Rep / Qty  */}
      {optionalPanels.length > 0 && (
        <section className={`db-row db-row--equal-${optionalPanels.length}`}>
          {optionalPanels.map((panel) => (
            <ChartPanel
              key={panel.key}
              title={panel.title}
              subtitle={panel.subtitle}
              height={panel.height}
              interactive={panel.interactive}
              active={panel.key === "region" ? !!filters.region : panel.key === "rep" ? !!filters.rep : false}
            >
              {panel.node}
            </ChartPanel>
          ))}
        </section>
      )}

      {/*  Row 4 : Recommendations + Insights  */}
      <section className="db-row db-row--50-50">
        <div className="db-panel">
          <div className="db-panel-header">
            <p className="db-panel-title">Recommandations IA</p>
            <span className={`llm-source-pill ${recommendationsSource === "llm" ? "ok" : "error"}`}>
              {recommendationsSource === "llm" ? `IA  ${data.model_used || ""}` : "Règles"}
            </span>
          </div>
          <div className="card-stack">
            {recommendations.length === 0 && <p className="empty-text">Aucune recommandation disponible.</p>}
            {recommendations.map((rec, i) => (
              <div className="info-card" key={`${rec.title}-${i}`}>
                <p className={`priority ${(rec.priority || "medium").toLowerCase()}`}>{rec.priority}</p>
                <h4>{rec.title}</h4>
                <p>{rec.insight}</p>
                <p><strong>Action :</strong> {rec.action}</p>
              </div>
            ))}
          </div>
        </div>

        <div className="db-panel">
          <div className="db-panel-header">
            <p className="db-panel-title">Explications visuelles</p>
          </div>
          <div className="card-stack">
            {(data.visual_insights || []).length === 0 && <p className="empty-text">Aucune explication disponible.</p>}
            {(data.visual_insights || []).map((ins, i) => (
              <div className="info-card" key={`${ins.title}-${i}`}>
                <h4>{ins.title}</h4>
                <p>{ins.explanation}</p>
                <p><strong>Takeaway :</strong> {ins.takeaway}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

    </main>
  );
}
