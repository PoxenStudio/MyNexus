<script setup lang="ts">
import { computed } from "vue";

// Pie slice per key (provider). data shape mirrors the dashboard's
// today_by_provider map so callers can pass it in directly.
const props = defineProps<{
  data: Record<string, number>;
}>();

const COLORS = ["#003153", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4"];

interface Slice {
  key: string;
  value: number;
  color: string;
  start: number; // radians
  end: number;   // radians
  percent: number;
}

const slices = computed<Slice[]>(() => {
  const entries = Object.entries(props.data).filter(([, v]) => v > 0);
  const total = entries.reduce((s, [, v]) => s + v, 0);
  if (total === 0) return [];
  let cursor = -Math.PI / 2; // start at top
  return entries.map(([key, value], i) => {
    const percent = value / total;
    const sweep = percent * Math.PI * 2;
    const start = cursor;
    const end = cursor + sweep;
    cursor = end;
    return { key, value, color: COLORS[i % COLORS.length], start, end, percent };
  });
});

const R = 55;
const CX = 80;
const CY = 80;
const SVG_SIZE = 160;

function arcPath(s: Slice): string {
  const x1 = CX + R * Math.cos(s.start);
  const y1 = CY + R * Math.sin(s.start);
  const x2 = CX + R * Math.cos(s.end);
  const y2 = CY + R * Math.sin(s.end);
  const large = s.end - s.start > Math.PI ? 1 : 0;
  return `M ${CX} ${CY} L ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2} Z`;
}

const singleFull = computed(() => slices.value.length === 1);
</script>

<template>
  <div class="pie-chart">
    <div v-if="slices.length === 0" class="empty">—</div>
    <svg v-else :viewBox="`0 0 ${SVG_SIZE} ${SVG_SIZE}`" class="svg">
      <circle
        v-if="singleFull"
        :cx="CX"
        :cy="CY"
        :r="R"
        :fill="slices[0].color"
      />
      <path
        v-else
        v-for="s in slices"
        :key="s.key"
        :d="arcPath(s)"
        :fill="s.color"
      />
    </svg>

    <div v-if="slices.length > 0" class="legend">
      <span v-for="s in slices" :key="s.key" class="legend-item">
        <span class="swatch" :style="{ background: s.color }"></span>
        <span class="label">{{ s.key }}</span>
        <span class="pct">{{ Math.round(s.percent * 100) }}%</span>
      </span>
    </div>
  </div>
</template>

<style scoped>
.pie-chart {
  color: var(--text);
  display: flex;
  gap: 1rem;
  align-items: center;
}
.svg {
  width: 120px;
  height: 120px;
  flex-shrink: 0;
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
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.8rem;
}
.legend-item {
  display: grid;
  grid-template-columns: 10px 1fr auto;
  gap: 0.4rem;
  align-items: center;
}
.swatch {
  width: 10px;
  height: 10px;
  border-radius: 2px;
  display: inline-block;
}
.label {
  opacity: 0.8;
}
.pct {
  font-variant-numeric: tabular-nums;
  opacity: 0.6;
}
</style>
