import {
  ArcElement,
  BarElement,
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Tooltip,
} from "chart.js";
import { Bar, Doughnut, Line } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Filler,
  Tooltip,
  Legend,
);

// 
// Theme  (light background, dark text, vivid palette)
// 
const BORDER_CLR = "#e2e8f0";
const MUTED      = "#64748b";
const TEXT       = "#0f172a";

const PALETTE = [
  "#3b82f6", "#10b981", "#f59e0b", "#ef4444",
  "#8b5cf6", "#ec4899", "#06b6d4", "#f97316",
  "#84cc16", "#a78bfa",
];

function fmtCurrency(value) {
  const n = Number(value || 0);
  if (n >= 1_000_000) return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)     return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

// Dark tooltip stays readable on white panels
const TOOLTIP = {
  backgroundColor: "#1e293b",
  borderColor:     "#334155",
  borderWidth:     1,
  titleColor:      "#f1f5f9",
  bodyColor:       "#94a3b8",
  padding:         10,
  cornerRadius:    8,
};

const GRID = { color: BORDER_CLR, lineWidth: 0.8 };

// 
// Shared base options
// 
function baseOpts(extraScales = {}) {
  return {
    responsive:          true,
    maintainAspectRatio: false,
    animation:           { duration: 500 },
    plugins: {
      legend:  { display: false },
      tooltip: { ...TOOLTIP },
    },
    scales: {
      x: {
        ticks:  { color: MUTED, font: { size: 11 } },
        grid:   GRID,
        border: { color: BORDER_CLR },
        ...extraScales.x,
      },
      y: {
        ticks:  { color: MUTED, font: { size: 11 } },
        grid:   GRID,
        border: { color: BORDER_CLR },
        ...extraScales.y,
      },
    },
  };
}

// 
// Revenue Trend  (Line)
// 
export function TrendChart({ trend = [] }) {
  if (trend.length < 2) return <EmptyChart label="Données de tendance insuffisantes" />;

  const labels = trend.map((d) => d.period);
  const values = trend.map((d) => Number(d.revenue));

  const data = {
    labels,
    datasets: [{
      label:              "Revenus",
      data:               values,
      borderColor:        "#3b82f6",
      backgroundColor:    "rgba(59,130,246,0.08)",
      fill:               true,
      tension:            0.4,
      pointRadius:        values.length <= 20 ? 4 : 2,
      pointBackgroundColor: "#3b82f6",
      borderWidth:        2.5,
    }],
  };

  const options = {
    ...baseOpts(),
    plugins: {
      ...baseOpts().plugins,
      tooltip: {
        ...TOOLTIP,
        callbacks: { label: (ctx) => ` ${fmtCurrency(ctx.parsed.y)}` },
      },
    },
    scales: {
      x: { ...baseOpts().scales.x, ticks: { color: MUTED, font: { size: 10 }, maxRotation: 45 } },
      y: { ...baseOpts().scales.y, ticks: { color: MUTED, font: { size: 10 }, callback: fmtCurrency } },
    },
  };

  return <Line data={data} options={options} />;
}

// 
// Horizontal Bar  (generic, interactive)
// 
function HBarChart({ labels, values, colors, formatValue, onSelect, selected }) {
  // Dim unselected bars when a selection is active
  const hasSelection = selected !== null && selected !== undefined;
  const bgColors = labels.map((lbl, i) => {
    const base = colors?.[i] ?? PALETTE[i % PALETTE.length];
    return hasSelection && lbl !== selected ? base + "55" : base;
  });

  const dataset = {
    data:            values,
    backgroundColor: bgColors,
    borderRadius:    4,
    borderSkipped:   false,
    barThickness:    Math.max(10, Math.min(28, 280 / labels.length)),
  };

  const data = { labels, datasets: [dataset] };

  const options = {
    ...baseOpts(),
    indexAxis: "y",
    plugins: {
      ...baseOpts().plugins,
      tooltip: {
        ...TOOLTIP,
        callbacks: {
          label: (ctx) => ` ${formatValue ? formatValue(ctx.parsed.x) : ctx.parsed.x}`,
        },
      },
    },
    scales: {
      x: {
        ...baseOpts().scales.x,
        ticks: { color: MUTED, font: { size: 10 }, callback: (v) => (formatValue ? formatValue(v) : v) },
      },
      y: { ...baseOpts().scales.y, grid: { display: false } },
    },
    ...(onSelect && { onHover: (_e, els, chart) => { chart.canvas.style.cursor = els.length ? "pointer" : "default"; } }),
  };

  function handleClick(_evt, elements) {
    if (!onSelect || elements.length === 0) return;
    const idx = elements[0].index;
    const lbl = labels[idx];
    onSelect(lbl === selected ? null : lbl); // toggle off
  }

  return <Bar data={data} options={options} onClick={handleClick} />;
}

// 
// Top Products
// 
export function ProductsChart({ products = [] }) {
  const items = products.slice(0, 8);
  if (items.length < 2) return <EmptyChart label="Données produits insuffisantes" />;
  return (
    <HBarChart
      labels={items.map((d) => d.product)}
      values={items.map((d) => Number(d.revenue))}
      colors={items.map((_, i) => PALETTE[i % PALETTE.length])}
      formatValue={fmtCurrency}
    />
  );
}

// 
// Product Mix  (Doughnut)
// 
export function ProductMixChart({ share = [] }) {
  if (share.length < 2) return <EmptyChart label="Données de répartition insuffisantes" />;

  const labels = share.map((d) => d.name);
  const values = share.map((d) => Number(d.value));
  const colors = labels.map((_, i) => PALETTE[i % PALETTE.length]);

  const data = {
    labels,
    datasets: [{
      data:            values,
      backgroundColor: colors,
      borderColor:     "#e2e8f0",
      borderWidth:     3,
      hoverOffset:     6,
    }],
  };

  const options = {
    responsive:          true,
    maintainAspectRatio: false,
    cutout:              "58%",
    animation:           { duration: 500 },
    plugins: {
      legend: {
        display: true,
        position: "right",
        labels: { color: TEXT, font: { size: 11 }, padding: 12, boxWidth: 12, boxHeight: 12 },
      },
      tooltip: {
        ...TOOLTIP,
        callbacks: { label: (ctx) => ` ${ctx.label}: ${ctx.parsed.toFixed(1)}%` },
      },
    },
  };

  return <Doughnut data={data} options={options} />;
}

// 
// Region  (interactive  clicking filters the whole dashboard)
// 
export function RegionChart({ regions = [], onSelect, selected }) {
  if (regions.length < 2) return <EmptyChart label="Pas de données régionales" />;
  const sorted = [...regions].sort((a, b) => b.revenue - a.revenue);
  return (
    <HBarChart
      labels={sorted.map((d) => d.region)}
      values={sorted.map((d) => Number(d.revenue))}
      colors={sorted.map((_, i) => PALETTE[i % PALETTE.length])}
      formatValue={fmtCurrency}
      onSelect={onSelect}
      selected={selected}
    />
  );
}

// 
// Category  (interactive)
// 
export function CategoryChart({ categories = [], onSelect, selected }) {
  if (categories.length < 2) return <EmptyChart label="Pas de données de catégories" />;
  const sorted = [...categories].sort((a, b) => b.revenue - a.revenue);
  return (
    <HBarChart
      labels={sorted.map((d) => d.category)}
      values={sorted.map((d) => Number(d.revenue))}
      colors={sorted.map((_, i) => PALETTE[i % PALETTE.length])}
      formatValue={fmtCurrency}
      onSelect={onSelect}
      selected={selected}
    />
  );
}

// 
// Sales Rep  (interactive)
// 
export function RepChart({ reps = [], onSelect, selected }) {
  if (reps.length < 2) return <EmptyChart label="Pas de données par commercial" />;
  const sorted = [...reps].sort((a, b) => b.revenue - a.revenue);
  return (
    <HBarChart
      labels={sorted.map((d) => d.rep)}
      values={sorted.map((d) => Number(d.revenue))}
      colors={sorted.map((_, i) => PALETTE[i % PALETTE.length])}
      formatValue={fmtCurrency}
      onSelect={onSelect}
      selected={selected}
    />
  );
}

// 
// Quantities
// 
export function QuantityChart({ quantities = [] }) {
  if (quantities.length < 2) return <EmptyChart label="Pas de données de quantité" />;
  const sorted = [...quantities].sort((a, b) => b.quantity - a.quantity).slice(0, 8);
  return (
    <HBarChart
      labels={sorted.map((d) => d.product)}
      values={sorted.map((d) => Number(d.quantity))}
      colors={sorted.map((_, i) => PALETTE[i % PALETTE.length])}
    />
  );
}

// 
// Empty placeholder
// 
function EmptyChart({ label }) {
  return (
    <div className="chart-empty">
      <span>{label}</span>
    </div>
  );
}
