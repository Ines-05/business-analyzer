/**
 * dashboard_template.jsx - Business Intelligence Dashboard (domain-agnostic)
 *
 * HOW TO USE:
 * 1. Run scripts/build_dashboard_json.py to generate /home/claude/dashboard_data.json
 * 2. Replace each placeholder constant below (-- DATA INJECTION --)
 *    with the actual values from dashboard_data.json
 * 3. Save the completed file as /mnt/user-data/outputs/dashboard.jsx
 *
 * What changed from the previous version:
 *   - TOP_PRODUCTS -> TOP_ITEMS       (domain-agnostic)
 *   - PRODUCT_SHARE -> ITEM_SHARE     (domain-agnostic)
 *   - by_region / by_rep / by_category -> DIMENSIONS array (dynamic, AI-driven)
 *   - ROLES added: real column names used as axis/card labels
 *   - DATA_QUALITY badge added to header
 *   - All hardcoded "Sales", "Revenue", "Product" labels replaced with ROLES values
 *
 * Design: Dark executive theme. Do NOT switch to a white/light theme.
 * Typography: DM Sans from Google Fonts.
 */

import {
  BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Area, AreaChart,
} from "recharts";

/*
    DATA INJECTION
   Replace these constants with real values from /home/claude/dashboard_data.json
 */

const KPI_DATA = {
  totalRevenue:  { label: "Total",        value: "$0",   raw: 0,   delta: "+0.0%", positive: true },
  totalOrders:   { label: "Records",      value: "0",    raw: 0,   delta: null },
  avgOrderValue: { label: "Avg / Record", value: "$0",   raw: 0,   delta: null },
  topItem:       { label: "Top Item",     value: "N/A",  share: "0% of total", delta: null },
  periodGrowth:  { label: "Growth",       value: "+0%",  raw: 0,   positive: true },
};

const TREND_DATA = [
  // { period: "Jan 24", revenue: 0 },
];

// Top items ranked by primary measure (was TOP_PRODUCTS)
const TOP_ITEMS = [
  // { name: "Item A", revenue: 0, share_pct: 0 },
];

// Donut share data (was PRODUCT_SHARE)
const ITEM_SHARE = [
  // { name: "Item A", value: 0 },
];

// Dynamic dimension breakdowns - one block per AI-assigned dimension
// Each: { key: "technicien", label: "Technicien", data: [{ label, revenue, share_pct }] }
const DIMENSIONS = [
  // { key: "region", label: "Region", data: [{ label: "North", revenue: 5000, share_pct: 42 }] },
];

const RECOMMENDATIONS = [
  // { priority: "High", icon: "", title: "...", insight: "...", action: "..." },
];

// Column roles from AI plan - used for axis labels
const ROLES = {
  primary_measure: "Revenue",
  primary_date:    "Date",
  dimensions:      [],
};

const META = {
  // source_file: "data.csv",
  // date_range: { min: "2024-01", max: "2024-12" },
  // row_count: 0,
  // plan_source: "llm",
};

const DATA_QUALITY = {
  // score: 87.3, grade: "A"
};

/* 
   THEME
 */
const T = {
  bg:      "#0a0e1a",
  surface: "#111827",
  border:  "#1f2937",
  accent:  "#3b82f6",
  emerald: "#10b981",
  amber:   "#f59e0b",
  danger:  "#ef4444",
  purple:  "#8b5cf6",
  text:    "#f9fafb",
  muted:   "#9ca3af",
  success: "#22c55e",
};

const PALETTE = [T.accent, T.emerald, T.amber, T.danger, T.purple, "#ec4899", "#06b6d4", "#84cc16"];
const PRIORITY_COLORS = { High: T.danger, Medium: T.amber, Low: T.accent };

/* 
   HELPERS
 */
function fmtValue(v) {
  if (v === null || v === undefined) return "-";
  const n = Number(v);
  if (!Number.isFinite(n)) return String(v);
  if (Math.abs(n) >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000)     return `${(n / 1_000).toFixed(0)}K`;
  return n.toLocaleString();
}

/* 
   SUB-COMPONENTS
 */

function GoogleFonts() {
  return (
    <style>{`
      @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap');
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body { background: ${T.bg}; }
      ::-webkit-scrollbar { width: 6px; }
      ::-webkit-scrollbar-track { background: ${T.surface}; }
      ::-webkit-scrollbar-thumb { background: ${T.border}; border-radius: 3px; }
    `}</style>
  );
}

function KpiCard({ label, value, delta, positive, mono = false }) {
  const deltaColor = positive === undefined ? T.muted : positive ? T.success : T.danger;
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12,
      padding: "1.4rem 1.6rem", flex: 1, minWidth: 160,
    }}>
      <div style={{ fontSize: 11, color: T.muted, textTransform: "uppercase", letterSpacing: "0.08em", marginBottom: 8 }}>
        {label}
      </div>
      <div style={{
        fontSize: 28, fontWeight: 700, color: T.text,
        fontFamily: mono ? "'JetBrains Mono', monospace" : "inherit",
        marginBottom: delta ? 6 : 0,
      }}>
        {value}
      </div>
      {delta && (
        <div style={{ fontSize: 13, color: deltaColor, fontWeight: 600 }}>{delta}</div>
      )}
    </div>
  );
}

function SectionHeader({ title, subtitle }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "1.25rem" }}>
      <div style={{ width: 4, height: 22, background: T.accent, borderRadius: 2 }} />
      <div>
        <h2 style={{ fontSize: 16, fontWeight: 600, color: T.text, letterSpacing: "-0.01em" }}>{title}</h2>
        {subtitle && <div style={{ fontSize: 11, color: T.muted, marginTop: 2 }}>{subtitle}</div>}
      </div>
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "10px 14px" }}>
      <div style={{ color: T.muted, fontSize: 12, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color || T.accent, fontWeight: 600, fontSize: 14 }}>
          {fmtValue(p.value)}
        </div>
      ))}
    </div>
  );
};

function RecommendationCard({ rec }) {
  const priColor = PRIORITY_COLORS[rec.priority] || T.accent;
  return (
    <div style={{
      background: T.surface, border: `1px solid ${T.border}`,
      borderLeft: `4px solid ${priColor}`,
      borderRadius: "0 10px 10px 0", padding: "1.25rem 1.5rem",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
        <span style={{ fontSize: 16 }}>{rec.icon}</span>
        <span style={{ fontSize: 11, fontWeight: 700, color: priColor, textTransform: "uppercase", letterSpacing: "0.07em" }}>
          {rec.priority}
        </span>
      </div>
      <div style={{ fontSize: 15, fontWeight: 600, color: T.text, marginBottom: 8 }}>{rec.title}</div>
      <div style={{ fontSize: 13, color: T.muted, lineHeight: 1.6, marginBottom: 10 }}>{rec.insight}</div>
      <div style={{
        background: priColor + "18", border: `1px solid ${priColor}44`,
        borderRadius: 6, padding: "8px 12px",
        fontSize: 12, color: T.text, lineHeight: 1.5,
      }}>
        <span style={{ color: priColor, fontWeight: 600 }}>Action: </span>{rec.action}
      </div>
    </div>
  );
}

function QualityBadge({ score, grade }) {
  if (score === null || score === undefined) return null;
  const color = score >= 85 ? T.emerald : score >= 70 ? T.amber : T.danger;
  return (
    <div style={{
      display: "inline-flex", alignItems: "center", gap: 6,
      background: color + "18", border: `1px solid ${color}44`,
      borderRadius: 20, padding: "4px 12px", fontSize: 11,
    }}>
      <div style={{ width: 6, height: 6, borderRadius: "50%", background: color }} />
      <span style={{ color, fontWeight: 600 }}>Data Quality {grade} ({score})</span>
    </div>
  );
}

/* Dimension breakdown block - renders one bar chart per dimension */
function DimensionBlock({ block, measureLabel }) {
  const data = (block.data || []).slice(0, 10).reverse();
  if (!data.length) return null;

  return (
    <div>
      <SectionHeader title={block.label} subtitle={`by ${measureLabel}`} />
      <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1.5rem" }}>
        <ResponsiveContainer width="100%" height={Math.max(200, data.length * 38)}>
          <BarChart data={data} layout="vertical" margin={{ top: 0, right: 60, left: 10, bottom: 0 }}>
            <CartesianGrid stroke={T.border} strokeDasharray="3 3" horizontal={false} />
            <XAxis type="number" stroke={T.muted} tick={{ fill: T.muted, fontSize: 10 }}
              axisLine={false} tickLine={false}
              tickFormatter={v => fmtValue(v)} />
            <YAxis type="category" dataKey="label" stroke={T.muted}
              tick={{ fill: T.muted, fontSize: 10 }}
              axisLine={false} tickLine={false} width={90} />
            <Tooltip content={<CustomTooltip />} />
            <Bar dataKey="revenue" radius={[0, 4, 4, 0]} label={{
              position: "right", formatter: v => fmtValue(v),
              fill: T.muted, fontSize: 9,
            }}>
              {data.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}

/* 
   MAIN DASHBOARD
 */
export default function Dashboard() {
  const measureLabel = ROLES.primary_measure || "Value";
  const dateLabel    = ROLES.primary_date    || "Date";
  const dr           = META.date_range || {};
  const dateRangeLabel = dr.min && dr.max ? `${dr.min} -> ${dr.max}` : "";

  // Split DIMENSIONS into pairs for 2-column layout
  const dimPairs = [];
  for (let i = 0; i < DIMENSIONS.length; i += 2) {
    dimPairs.push(DIMENSIONS.slice(i, i + 2));
  }

  return (
    <>
      <GoogleFonts />
      <div style={{
        fontFamily: "'DM Sans', sans-serif",
        background: T.bg, minHeight: "100vh", color: T.text,
        padding: "2rem 2.5rem",
      }}>

        {/*  HEADER  */}
        <div style={{
          display: "flex", alignItems: "flex-start", justifyContent: "space-between",
          marginBottom: "2.5rem", paddingBottom: "1.5rem",
          borderBottom: `1px solid ${T.border}`,
        }}>
          <div>
            <div style={{ fontSize: 11, color: T.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 6 }}>
              Business Intelligence
            </div>
            <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", marginBottom: 6 }}>
              {measureLabel} Analysis Dashboard
            </h1>
            <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
              {dateRangeLabel && (
                <div style={{ fontSize: 13, color: T.muted }}>{dateLabel}: {dateRangeLabel}</div>
              )}
              <QualityBadge score={DATA_QUALITY.score} grade={DATA_QUALITY.grade} />
              {META.plan_source === "llm" && (
                <div style={{
                  display: "inline-flex", alignItems: "center", gap: 5,
                  background: T.purple + "18", border: `1px solid ${T.purple}44`,
                  borderRadius: 20, padding: "4px 12px", fontSize: 11, color: T.purple,
                }}>
                  AI-powered analysis
                </div>
              )}
            </div>
          </div>
          {META.source_file && (
            <div style={{ textAlign: "right", fontSize: 11, color: T.muted }}>
              <div style={{ marginBottom: 2 }}>{META.source_file}</div>
              <div>{(META.row_count || 0).toLocaleString()} records</div>
            </div>
          )}
        </div>

        {/*  KPI CARDS  */}
        <div style={{ display: "flex", gap: "1rem", marginBottom: "2.5rem", flexWrap: "wrap" }}>
          <KpiCard label={KPI_DATA.totalRevenue.label  || measureLabel}
                   value={KPI_DATA.totalRevenue.value}
                   delta={KPI_DATA.totalRevenue.delta}
                   positive={KPI_DATA.totalRevenue.positive} mono />
          <KpiCard label={KPI_DATA.totalOrders.label   || "Records"}
                   value={KPI_DATA.totalOrders.value}
                   delta={null} />
          <KpiCard label={KPI_DATA.avgOrderValue.label || "Avg / Record"}
                   value={KPI_DATA.avgOrderValue.value}
                   delta={null} mono />
          <KpiCard label={KPI_DATA.periodGrowth.label  || "Growth"}
                   value={KPI_DATA.periodGrowth.value}
                   positive={KPI_DATA.periodGrowth.positive} />
          {KPI_DATA.topItem?.value && KPI_DATA.topItem.value !== "N/A" && (
            <KpiCard label={KPI_DATA.topItem.label || "Top Item"}
                     value={KPI_DATA.topItem.value}
                     delta={KPI_DATA.topItem.share} />
          )}
        </div>

        {/*  TREND  */}
        {TREND_DATA.length > 0 && (
          <div style={{ marginBottom: "2.5rem" }}>
            <SectionHeader title={`${measureLabel} Trend`} subtitle={dateLabel} />
            <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1.5rem" }}>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={TREND_DATA} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="measureGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={T.accent} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={T.accent} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={T.border} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="period" stroke={T.muted} tick={{ fill: T.muted, fontSize: 11 }}
                    axisLine={false} tickLine={false} />
                  <YAxis stroke={T.muted} tick={{ fill: T.muted, fontSize: 11 }}
                    axisLine={false} tickLine={false}
                    tickFormatter={v => fmtValue(v)} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="revenue" stroke={T.accent} strokeWidth={2.5}
                    fill="url(#measureGrad)"
                    dot={{ fill: T.accent, r: 4, strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: T.accent }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/*  TOP ITEMS + SHARE  */}
        {(TOP_ITEMS.length > 0 || ITEM_SHARE.length > 0) && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "2.5rem" }}>

            {/* Top items horizontal bar */}
            {TOP_ITEMS.length > 0 && (
              <div>
                <SectionHeader title={`Top ${ROLES.dimensions?.[0] || "Items"}`}
                               subtitle={`by ${measureLabel}`} />
                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1.5rem" }}>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart
                      data={TOP_ITEMS.slice(0, 8).map(d => ({ ...d, label: d.name })).reverse()}
                      layout="vertical"
                      margin={{ top: 0, right: 50, left: 10, bottom: 0 }}>
                      <CartesianGrid stroke={T.border} strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" stroke={T.muted} tick={{ fill: T.muted, fontSize: 10 }}
                        axisLine={false} tickLine={false}
                        tickFormatter={v => fmtValue(v)} />
                      <YAxis type="category" dataKey="label" stroke={T.muted}
                        tick={{ fill: T.muted, fontSize: 10 }}
                        axisLine={false} tickLine={false} width={80} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="revenue" radius={[0, 4, 4, 0]}>
                        {TOP_ITEMS.slice(0, 8).map((_, i) => (
                          <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Item share donut */}
            {ITEM_SHARE.length > 0 && (
              <div>
                <SectionHeader title={`${ROLES.dimensions?.[0] || "Item"} Mix`}
                               subtitle="share of total" />
                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1.5rem" }}>
                  <ResponsiveContainer width="100%" height={280}>
                    <PieChart>
                      <Pie data={ITEM_SHARE} cx="45%" cy="50%"
                        innerRadius="52%" outerRadius="75%"
                        dataKey="value" paddingAngle={3}>
                        {ITEM_SHARE.map((_, i) => (
                          <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                        ))}
                      </Pie>
                      <Tooltip
                        formatter={(val) => [`${Number(val || 0).toFixed(1)}%`, "Share"]}
                        contentStyle={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, color: T.text }} />
                      <Legend iconType="circle" iconSize={8}
                        formatter={(value) => <span style={{ color: T.muted, fontSize: 11 }}>{value}</span>} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}
          </div>
        )}

        {/*  DYNAMIC DIMENSIONS  */}
        {DIMENSIONS.length > 0 && (
          <div style={{ marginBottom: "2.5rem" }}>
            {dimPairs.map((pair, pi) => (
              <div key={pi} style={{
                display: "grid",
                gridTemplateColumns: pair.length === 2 ? "1fr 1fr" : "1fr",
                gap: "1.5rem",
                marginBottom: "1.5rem",
              }}>
                {pair.map((block) => (
                  <DimensionBlock key={block.key} block={block} measureLabel={measureLabel} />
                ))}
              </div>
            ))}
          </div>
        )}

        {/*  RECOMMENDATIONS  */}
        {RECOMMENDATIONS.length > 0 && (
          <div style={{ marginBottom: "2.5rem" }}>
            <SectionHeader title="Strategic Recommendations" />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              {RECOMMENDATIONS.map((rec, i) => (
                <RecommendationCard key={i} rec={rec} />
              ))}
            </div>
          </div>
        )}

        {/*  FOOTER  */}
        <div style={{
          marginTop: "2.5rem", paddingTop: "1.25rem",
          borderTop: `1px solid ${T.border}`,
          fontSize: 11, color: T.muted,
          display: "flex", justifyContent: "space-between", alignItems: "center",
        }}>
          <span>Business Intelligence Dashboard</span>
          <div style={{ display: "flex", gap: 16, alignItems: "center" }}>
            {META.plan_source && (
              <span>Analysis: {META.plan_source}</span>
            )}
            <span>Generated - {new Date().toLocaleDateString()}</span>
          </div>
        </div>

      </div>
    </>
  );
}


