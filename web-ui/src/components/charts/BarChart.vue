<script setup lang="ts">
import { computed } from "vue";

const props = defineProps<{
  data: { label: string; value: number }[];
}>();

const COLORS = ["#aa3bff", "#3b82f6", "#22c55e", "#f59e0b", "#ef4444", "#06b6d4"];

const max = computed(() => Math.max(1, ...props.data.map((d) => d.value)));
</script>

<template>
  <div class="bar-chart">
    <div v-if="data.length === 0" class="empty">—</div>
    <div v-for="(d, i) in data" :key="d.label" class="row">
      <span class="label">{{ d.label }}</span>
      <div class="track">
        <div class="fill" :style="{ width: (d.value / max) * 100 + '%', background: COLORS[i % COLORS.length] }" />
      </div>
      <span class="value">{{ d.value }}</span>
    </div>
  </div>
</template>

<style scoped>
.bar-chart {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.row {
  display: grid;
  grid-template-columns: 5rem 1fr 2.5rem;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.85rem;
}
.label {
  text-align: right;
  color: var(--text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.track {
  height: 0.85rem;
  background: var(--code-bg);
  border-radius: 4px;
  overflow: hidden;
}
.fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s ease;
}
.value {
  text-align: right;
  font-variant-numeric: tabular-nums;
}
.empty {
  color: var(--text);
  opacity: 0.6;
  font-size: 0.85rem;
}
</style>
