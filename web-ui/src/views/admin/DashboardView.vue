<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { fetchStats, type SystemStats } from "../../api/system";
import StatCard from "../../components/StatCard.vue";
import BarChart from "../../components/charts/BarChart.vue";

const { t } = useI18n();
const stats = ref<SystemStats | null>(null);
const loading = ref(true);

function toChartData(record: Record<string, number>) {
  return Object.entries(record).map(([label, value]) => ({
    label: t(`status.${label}`, label),
    value,
  }));
}

const booksByStatus = computed(() => (stats.value ? toChartData(stats.value.books_by_status) : []));
const tasksByStatus = computed(() => (stats.value ? toChartData(stats.value.tasks_by_status) : []));

async function load() {
  loading.value = true;
  try {
    stats.value = await fetchStats();
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <h1>{{ t("dashboard.title") }}</h1>

    <div v-if="loading">{{ t("common.loading") }}</div>
    <template v-else-if="stats">
      <div class="cards">
        <StatCard :label="t('dashboard.booksTotal')" :value="stats.books_total" />
        <StatCard :label="t('dashboard.chunksTotal')" :value="stats.chunks_total" />
        <StatCard :label="t('dashboard.sessionsTotal')" :value="stats.sessions_total" />
      </div>

      <div class="panels">
        <div class="panel">
          <h2>{{ t("dashboard.booksByStatus") }}</h2>
          <BarChart :data="booksByStatus" />
        </div>
        <div class="panel">
          <h2>{{ t("dashboard.tasksByStatus") }}</h2>
          <BarChart :data="tasksByStatus" />
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped>
.cards {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  margin: 1rem 0 1.5rem;
}
.panels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}
.panel {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.25rem;
}
.panel h2 {
  font-size: 1rem;
  margin: 0 0 0.75rem;
}
</style>
