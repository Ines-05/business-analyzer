/**
 * dashboard_template.jsx — Sales BI Dashboard React Template
 *
 * HOW TO USE:
 * 1. Run scripts/build_dashboard_json.py to generate /home/claude/dashboard_data.json
 * 2. Replace each placeholder block below (marked ── DATA INJECTION ──)
 *    with the actual values from dashboard_data.json
 * 3. Save the completed file as /mnt/user-data/outputs/sales-dashboard.jsx
 *
 * Dependencies (loaded via CDN by Claude.ai artifact runner):
 *   - recharts (LineChart, BarChart, PieChart, ...)
 *
 * Design: Dark executive theme. Do NOT switch to a white/light theme.
 * Typography: DM Sans from Google Fonts (imported via style tag below).
 */

import { useState } from "react";
import {
  LineChart, Line, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, Legend,
  ResponsiveContainer, Area, AreaChart,
} from "recharts";

/* ─────────────────────────────────────────────────────────────────────────────
   ── DATA INJECTION ──
   Replace these constants with real values from /home/claude/dashboard_data.json
   Copy the JSON value for each key directly.
───────────────────────────────────────────────────────────────────────────── */

const KPI_DATA = {
  totalRevenue:  { value: "$0",   raw: 0,   delta: "+0.0%", positive: true },
  totalOrders:   { value: "0",    raw: 0,   delta: null },
  avgOrderValue: { value: "$0",   raw: 0,   delta: null },
  topProduct:    { value: "N/A",  share: "0% of revenue", delta: null },
  periodGrowth:  { value: "+0%",  raw: 0,   positive: true },
};

const TREND_DATA = [
  // { period: "Jan 24", revenue: 0 },
];

const TOP_PRODUCTS = [
  // { product: "SKU-A", revenue: 0, share_pct: 0 },
];

const PRODUCT_SHARE = [
  // { name: "SKU-A", value: 0 },
];

const RECOMMENDATIONS = [
  // { priority: "High", icon: "🚨", title: "...", insight: "...", action: "..." },
];

const META = {
  // source_file: "sales.csv",
  // date_range: { min: "2024-01", max: "2024-12" },
  // row_count: 0,
};

/* ─────────────────────────────────────────────────────────────────────────────
   THEME — do not change these without updating generate_charts.py too
───────────────────────────────────────────────────────────────────────────── */
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

const PALETTE = [T.accent, T.emerald, T.amber, T.danger, T.purple, "#ec4899", "#06b6d4"];
const PRIORITY_COLORS = { High: T.danger, Medium: T.amber, Low: T.accent };

/* ─────────────────────────────────────────────────────────────────────────────
   SUB-COMPONENTS
───────────────────────────────────────────────────────────────────────────── */

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
        fontSize: 28, fontWeight: 700, color: T.text, fontFamily: mono ? "'JetBrains Mono', monospace" : "inherit",
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

function SectionHeader({ title }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: "1.25rem" }}>
      <div style={{ width: 4, height: 22, background: T.accent, borderRadius: 2 }} />
      <h2 style={{ fontSize: 16, fontWeight: 600, color: T.text, letterSpacing: "-0.01em" }}>{title}</h2>
    </div>
  );
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 8, padding: "10px 14px" }}>
      <div style={{ color: T.muted, fontSize: 12, marginBottom: 4 }}>{label}</div>
      {payload.map((p, i) => (
        <div key={i} style={{ color: p.color, fontWeight: 600, fontSize: 14 }}>
          ${p.value?.toLocaleString()}
        </div>
      ))}
    </div>
  );
};

function RecommendationCard({ rec }) {
  const priColor = PRIORITY_COLORS[rec.priority] || T.accent;
  return (
    <div style={{
      background: T.surface,
      border: `1px solid ${T.border}`,
      borderLeft: `4px solid ${priColor}`,
      borderRadius: "0 10px 10px 0",
      padding: "1.25rem 1.5rem",
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
        background: priColor + "18",
        border: `1px solid ${priColor}44`,
        borderRadius: 6, padding: "8px 12px",
        fontSize: 12, color: T.text, lineHeight: 1.5,
      }}>
        <span style={{ color: priColor, fontWeight: 600 }}>→ Action: </span>
        {rec.action}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────────────────────
   MAIN DASHBOARD
───────────────────────────────────────────────────────────────────────────── */
export default function SalesDashboard() {
  const [activeTab, setActiveTab] = useState("dashboard");

  const dr = META.date_range || {};
  const dateRangeLabel = dr.min && dr.max ? `${dr.min} → ${dr.max}` : "";

  return (
    <>
      <GoogleFonts />
      <div style={{
        fontFamily: "'DM Sans', sans-serif",
        background: T.bg, minHeight: "100vh", color: T.text,
        padding: "2rem 2.5rem",
      }}>

        {/* ── HEADER ── */}
        <div style={{
          display: "flex", alignItems: "flex-start", justifyContent: "space-between",
          marginBottom: "2.5rem", paddingBottom: "1.5rem",
          borderBottom: `1px solid ${T.border}`,
        }}>
          <div>
            <div style={{ fontSize: 11, color: T.muted, textTransform: "uppercase", letterSpacing: "0.1em", marginBottom: 6 }}>
              Business Intelligence
            </div>
            <h1 style={{ fontSize: 26, fontWeight: 700, letterSpacing: "-0.02em", marginBottom: 4 }}>
              Sales Performance Report
            </h1>
            {dateRangeLabel && (
              <div style={{ fontSize: 13, color: T.muted }}>{dateRangeLabel}</div>
            )}
          </div>
          {META.source_file && (
            <div style={{ textAlign: "right", fontSize: 11, color: T.muted }}>
              <div>{META.source_file}</div>
              <div>{(META.row_count || 0).toLocaleString()} records</div>
            </div>
          )}
        </div>

        {/* ── KPI CARDS ── */}
        <div style={{ display: "flex", gap: "1rem", marginBottom: "2.5rem", flexWrap: "wrap" }}>
          <KpiCard label="Total Revenue"   value={KPI_DATA.totalRevenue.value}  delta={KPI_DATA.totalRevenue.delta}   positive={KPI_DATA.totalRevenue.positive}  mono />
          <KpiCard label="Total Orders"    value={KPI_DATA.totalOrders.value}   delta={null} />
          <KpiCard label="Avg Order Value" value={KPI_DATA.avgOrderValue.value} delta={null} mono />
          <KpiCard label="Period Growth"   value={KPI_DATA.periodGrowth.value}  positive={KPI_DATA.periodGrowth.positive} />
          {KPI_DATA.topProduct.value !== "N/A" && (
            <KpiCard label="Top Product" value={KPI_DATA.topProduct.value} delta={KPI_DATA.topProduct.share} />
          )}
        </div>

        {/* ── REVENUE TREND ── */}
        {TREND_DATA.length > 0 && (
          <div style={{ marginBottom: "2.5rem" }}>
            <SectionHeader title="Revenue Trend" />
            <div style={{
              background: T.surface, border: `1px solid ${T.border}`,
              borderRadius: 12, padding: "1.5rem",
            }}>
              <ResponsiveContainer width="100%" height={260}>
                <AreaChart data={TREND_DATA} margin={{ top: 10, right: 10, left: 10, bottom: 0 }}>
                  <defs>
                    <linearGradient id="revenueGrad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%"  stopColor={T.accent} stopOpacity={0.25} />
                      <stop offset="95%" stopColor={T.accent} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke={T.border} strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="period" stroke={T.muted} tick={{ fill: T.muted, fontSize: 11 }} axisLine={false} tickLine={false} />
                  <YAxis stroke={T.muted} tick={{ fill: T.muted, fontSize: 11 }} axisLine={false} tickLine={false}
                    tickFormatter={v => `$${v >= 1000 ? `${(v/1000).toFixed(0)}K` : v}`} />
                  <Tooltip content={<CustomTooltip />} />
                  <Area type="monotone" dataKey="revenue" stroke={T.accent} strokeWidth={2.5}
                    fill="url(#revenueGrad)" dot={{ fill: T.accent, r: 4, strokeWidth: 0 }}
                    activeDot={{ r: 6, fill: T.accent }} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {/* ── PRODUCTS + SHARE ── */}
        {(TOP_PRODUCTS.length > 0 || PRODUCT_SHARE.length > 0) && (
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", marginBottom: "2.5rem" }}>

            {/* Top Products Bar Chart */}
            {TOP_PRODUCTS.length > 0 && (
              <div>
                <SectionHeader title="Top Products" />
                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1.5rem" }}>
                  <ResponsiveContainer width="100%" height={280}>
                    <BarChart data={TOP_PRODUCTS.slice(0, 8).reverse()} layout="vertical"
                      margin={{ top: 0, right: 40, left: 10, bottom: 0 }}>
                      <CartesianGrid stroke={T.border} strokeDasharray="3 3" horizontal={false} />
                      <XAxis type="number" stroke={T.muted} tick={{ fill: T.muted, fontSize: 10 }} axisLine={false} tickLine={false}
                        tickFormatter={v => `$${v >= 1000 ? `${(v/1000).toFixed(0)}K` : v}`} />
                      <YAxis type="category" dataKey="product" stroke={T.muted} tick={{ fill: T.muted, fontSize: 10 }}
                        axisLine={false} tickLine={false} width={80} />
                      <Tooltip content={<CustomTooltip />} />
                      <Bar dataKey="revenue" radius={[0, 4, 4, 0]}>
                        {TOP_PRODUCTS.slice(0, 8).reverse().map((_, i) => (
                          <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                        ))}
                      </Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            )}

            {/* Product Share Donut */}
            {PRODUCT_SHARE.length > 0 && (
              <div>
                <SectionHeader title="Product Mix" />
                <div style={{ background: T.surface, border: `1px solid ${T.border}`, borderRadius: 12, padding: "1.5rem" }}>
                  <ResponsiveContainer width="100%" height={280}>
                    <PieChart>
                      <Pie data={PRODUCT_SHARE} cx="45%" cy="50%" innerRadius="52%" outerRadius="75%"
                        dataKey="value" paddingAngle={3}>
                        {PRODUCT_SHARE.map((_, i) => (
                          <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
                        ))}
                      </Pie>
                      <Tooltip formatter={(val) => [`${val.toFixed(1)}%`, "Share"]}
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

        {/* ── RECOMMENDATIONS ── */}
        {RECOMMENDATIONS.length > 0 && (
          <div>
            <SectionHeader title="Strategic Recommendations" />
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1rem" }}>
              {RECOMMENDATIONS.map((rec, i) => (
                <RecommendationCard key={i} rec={rec} />
              ))}
            </div>
          </div>
        )}

        {/* ── FOOTER ── */}
        <div style={{
          marginTop: "2.5rem", paddingTop: "1.25rem",
          borderTop: `1px solid ${T.border}`,
          fontSize: 11, color: T.muted, display: "flex", justifyContent: "space-between",
        }}>
          <span>Sales BI Dashboard</span>
          <span>Generated by Claude · {new Date().toLocaleDateString()}</span>
        </div>

      </div>
    </>
  );
}
