<script setup lang="ts">
import { computed } from "vue";

// Per-provider stacked line over time. data[day][provider] = tokens — the
// daily API already groups by (date, provider); we just reshape into
// per-provider traces here so a provider with zero tokens on a particular
// day naturally lands on the x-axis instead of disappearing from the chart.
const props = defineProps<{
  data: { date: string; llm_provider: string; total_tokens: number }[];
}>();

const COLORS = ["#003153", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4"];

interface Trace {
  provider: string;
  color: string;
  points: { date: string; total: number }[];
}

const traces = computed<Trace[]>(() => {
  const byProvider = new Map<string, { date: string; total: number }[]>();
  for (const row of props.data) {
    if (!byProvider.has(row.llm_provider)) byProvider.set(row.llm_provider, []);
    byProvider.get(row.llm_provider)!.push({ date: row.date, total: row.total_tokens });
  }
  return Array.from(byProvider.entries()).map(([provider, rows], i) => {
    rows.sort((a, b) => a.date.localeCompare(b.date));
    return { provider, color: COLORS[i % COLORS.length], points: rows };
  });
});

const dates = computed(() => {
  const set = new Set<string>();
  for (const t of traces.value) for (const p of t.points) set.add(p.date);
  return Array.from(set).sort();
});

const WIDTH = 520;
const HEIGHT = 180;
const PAD = { top: 10, right: 16, bottom: 28, left: 44 };

const layout = computed(() => {
  const w = WIDTH - PAD.left - PAD.right;
  const h = HEIGHT - PAD.top - PAD.bottom;
  const maxY = Math.max(1, ...props.data.map((d) => d.total_tokens));
  const stepY = Math.pow(10, Math.floor(Math.log10(maxY)));
  const niceMax = Math.ceil(maxY / stepY) * stepY;
  const xStep = dates.value.length > 1 ? w / (dates.value.length - 1) : w / 2;

  const providerIndex = new Map<string, number>();
  traces.value.forEach((t, i) => providerIndex.set(t.provider, i));
  const positioned = traces.value.map((t) => ({
    ...t,
    points: t.points.map((p) => ({
      ...p,
      x: PAD.left + (dates.value.indexOf(p.date) * xStep) || PAD.left,
      y: PAD.top + h - (p.total / niceMax) * h,
    })),
  }));
  return { w, h, maxY: niceMax, xStep, positioned, ticksY: [0, 0.25, 0.5, 0.75, 1].map((r) => r * niceMax) };
});
</script>

<template>
  <div class="line-chart">
    <div v-if="traces.length === 0" class="empty">—</div>
    <svg v-else :viewBox="`0 0 ${WIDTH} ${HEIGHT}`" class="svg">
      <!-- Y-axis ticks -->
      <g>
        <line
          v-for="(tick, i) in layout.ticksY"
          :key="`y-${i}`"
          :x1="PAD.left"
          :x2="WIDTH - PAD.right"
          :y1="PAD.top + layout.h - (tick / layout.maxY) * layout.h"
          :y2="PAD.top + layout.h - (tick / layout.maxY) * layout.h"
          stroke="currentColor"
          stroke-opacity="0.12"
        />
        <text
          v-for="(tick, i) in layout.ticksY"
          :key="`yt-${i}`"
          :x="PAD.left - 6"
          :y="PAD.top + layout.h - (tick / layout.maxY) * layout.h + 3"
          text-anchor="end"
          font-size="10"
          fill="currentColor"
          fill-opacity="0.5"
        >
          {{ tick >= 1000 ? (tick / 1000).toFixed(0) + "K" : tick }}
        </text>
      </g>

      <!-- X-axis labels -->
      <g>
        <text
          v-for="(d, i) in dates"
          :key="`x-${i}`"
          :x="PAD.left + i * layout.xStep"
          :y="HEIGHT - 8"
          text-anchor="middle"
          font-size="10"
          fill="currentColor"
          fill-opacity="0.5"
        >
          {{ d.slice(5) }}
        </text>
      </g>

      <!-- One polyline per provider -->
      <path
        v-for="t in layout.positioned"
        :key="t.provider"
        :d="t.points.length > 1 ? t.points.map((p) => `${p.x},${p.y}`).join(' ') : ''"
        :stroke="t.color"
        stroke-width="2"
        fill="none"
        stroke-linejoin="round"
        stroke-linecap="round"
        vector-effect="non-scaling-stroke"
      />

      <!-- Dots -->
      <g v-for="t in layout.positioned" :key="`dot-${t.provider}`">
        <circle
          v-for="(p, i) in t.points"
          :key="i"
          :cx="p.x"
          :cy="p.y"
          :r="2.5"
          :fill="t.color"
        />
      </g>
    </svg>

    <!-- Legend -->
    <div class="legend">
      <span v-for="t in traces" :key="t.provider" class="legend-item">
        <span class="swatch" :style="{ background: t.color }"></span>
        {{ t.provider }}
      </span>
    </div>
  </div>
</template>

<style scoped>
.line-chart {
  color: var(--text);
}
.svg {
  width: 100%;
  height: auto;
  display: block;
}
.empty {
  color: var(--text);
  opacity: 0.6;
  font-size: 0.85rem;
  text-align: center;
  padding: 2rem 0;
}
.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem 1rem;
  font-size: 0.75rem;
  opacity: 0.75;
  margin-top: 0.5rem;
}
.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 0.35rem;
}
.swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}
</style>
