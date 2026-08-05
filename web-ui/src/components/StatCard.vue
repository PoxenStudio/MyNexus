<script setup lang="ts">
defineProps<{ label: string; value: number | string }>();
</script>

<template>
  <div class="stat-card">
    <div class="value">{{ value }}</div>
    <div class="label">{{ label }}</div>
  </div>
</template>

<style scoped>
.stat-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.25rem;
  min-width: 140px;
}
.value {
  font-size: 1.75rem;
  font-weight: 700;
}
.label {
  font-size: 0.85rem;
  opacity: 0.7;
  margin-top: 0.25rem;
}
</style>
