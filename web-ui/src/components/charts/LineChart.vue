<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Title,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Line } from "vue-chartjs";

ChartJS.register(CategoryScale, LinearScale, PointElement, LineElement, Title, Tooltip, Legend, Filler);

const props = withDefaults(
  defineProps<{
    data: { date: string; llm_provider: string; total_tokens: number }[];
    // Number of calendar days the chart should always span (ending today),
    // regardless of how many days actually carry data. Missing days are
    // filled with zero so the x-axis stays consistent when providers go
    // silent and when the caller picks a "today-only" range for the
    // aggregate stat cards but still wants the chart to show context.
    expectedDays?: number;
  }>(),
  { expectedDays: 0 },
);

const COLORS = ["#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4"];

function isoDatesBetween(from: Date, to: Date): string[] {
  const out: string[] = [];
  const d = new Date(from);
  while (d <= to) {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, "0");
    const day = String(d.getDate()).padStart(2, "0");
    out.push(`${y}-${m}-${day}`);
    d.setDate(d.getDate() + 1);
  }
  return out;
}

function isoToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function isoNDaysAgo(n: number): string {
  const d = new Date();
  d.setDate(d.getDate() - n);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

// Resolve CSS variables at runtime — chart.js options are plain values, they
// can't reference CSS vars directly, so we re-read them every time the theme
// changes via a data-theme attribute observer.
function cssVar(name: string, fallback: string): string {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

const themeVersion = ref(0);
let observer: MutationObserver | null = null;

onMounted(() => {
  observer = new MutationObserver(() => themeVersion.value++);
  observer.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
});
onBeforeUnmount(() => observer?.disconnect());

const allDates = computed(() => {
  themeVersion.value;
  const N = props.expectedDays;
  if (N && N > 0) return isoDatesBetween(new Date(isoNDaysAgo(N - 1)), new Date(isoToday()));
  if (props.data.length === 0) return [];
  const sorted = props.data.map((r) => r.date).sort();
  return isoDatesBetween(new Date(sorted[0]), new Date(sorted[sorted.length - 1]));
});

const chartData = computed(() => {
  const byProvider = new Map<string, Map<string, number>>();
  for (const row of props.data) {
    if (!byProvider.has(row.llm_provider)) byProvider.set(row.llm_provider, new Map());
    byProvider.get(row.llm_provider)!.set(row.date, row.total_tokens);
  }
  const datasets = Array.from(byProvider.entries()).map(([provider, dayMap], i) => ({
    label: provider,
    data: allDates.value.map((date) => dayMap.get(date) ?? 0),
    borderColor: COLORS[i % COLORS.length],
    backgroundColor: COLORS[i % COLORS.length] + "22",
    borderWidth: 2,
    tension: 0.35,
    pointRadius: 2,
    pointHoverRadius: 5,
  }));
  return {
    labels: allDates.value.map((d) => d.slice(5)),
    datasets,
  };
});

const chartOptions = computed(() => {
  themeVersion.value; // re-read CSS vars when theme flips
  const text = cssVar("--text", "#2b2830");
  const textDim = cssVar("--text-h", "#555").replace(/^#(.)\1(.)\2(.)\3/, "#$1$2$3"); // darker dim fallback
  const border = cssVar("--border", "#e5e4e7");
  // Dim text is CSS var fallback if no dedicated dim var exists — fall back
  // to a translucent version of --text when --text-h resolves white on white.
  const gridLine = border;
  return {
    responsive: true,
    maintainAspectRatio: false,
    interaction: { mode: "index" as const, intersect: false },
    plugins: {
      legend: {
        position: "bottom" as const,
        labels: {
          boxWidth: 10,
          boxHeight: 10,
          usePointStyle: true,
          font: { size: 11, color: text },
          color: text,
        },
      },
      tooltip: {
        backgroundColor: "rgba(0,0,0,0.85)",
        borderColor: border,
        borderWidth: 1,
        titleFont: { size: 12, color: "#fff" },
        bodyFont: { size: 12, color: "#fff" },
        padding: 8,
        callbacks: {
          label: (ctx: any) => {
            const v = ctx.parsed.y;
            return `${ctx.dataset.label}: ${v >= 1000 ? (v / 1000).toFixed(1) + "K" : v}`;
          },
        },
      },
    },
    scales: {
      x: {
        grid: { display: false },
        ticks: { font: { size: 10 }, color: textDim || text },
      },
      y: {
        beginAtZero: true,
        grid: { color: gridLine },
        ticks: {
          font: { size: 10 },
          color: textDim || text,
          callback: (v: any) => (v >= 1000 ? (v / 1000).toFixed(0) + "K" : v),
        },
      },
    },
  };
});
</script>

<template>
  <div class="line-chart">
    <div v-if="chartData.datasets.length === 0" class="empty">—</div>
    <div v-else class="chart-wrap">
      <Line :data="chartData" :options="chartOptions" />
    </div>
  </div>
</template>

<style scoped>
.line-chart {
  color: var(--text);
}
.chart-wrap {
  height: 200px;
}
.empty {
  color: var(--text);
  opacity: 0.6;
  font-size: 0.85rem;
  text-align: center;
  padding: 2rem 0;
}
</style>
