<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { fetchStats, type SystemStats } from "../../api/system";
import { fetchTokenStats, formatTokens, type TokenStats } from "../../api/token";
import LineChart from "../../components/charts/LineChart.vue";
import PieChart from "../../components/charts/PieChart.vue";
import BarChart from "../../components/charts/BarChart.vue";
import StatCard from "../../components/StatCard.vue";

const { t } = useI18n();
const stats = ref<SystemStats | null>(null);
const tokenStats = ref<TokenStats | null>(null);
const loading = ref(true);

function toChartData(record: Record<string, number>) {
  return Object.entries(record).map(([label, value]) => ({
    label: t(`status.${label}`, label),
    value,
  }));
}

const booksByStatus = computed(() => (stats.value ? toChartData(stats.value.books_by_status) : []));
const tasksByStatus = computed(() => (stats.value ? toChartData(stats.value.tasks_by_status) : []));

const totalTokenRange = computed(() => {
  if (!tokenStats.value) return { total: 0, prompt: 0, completion: 0 };
  let total = 0, prompt = 0, completion = 0;
  for (const r of tokenStats.value.daily) {
    total += r.total_tokens;
    prompt += r.prompt_tokens;
    completion += r.completion_tokens;
  }
  return { total, prompt, completion };
});

const rangeOptions = computed(() => [
  { value: 1, label: t("dashboard.range1") },
  { value: 7, label: t("dashboard.range7") },
  { value: 30, label: t("dashboard.range30") },
]);

const currentRange = ref(7);

async function load() {
  loading.value = true;
  try {
    [stats.value, tokenStats.value] = await Promise.all([fetchStats(), fetchTokenStats(currentRange.value)]);
  } finally {
    loading.value = false;
  }
}

async function loadTokenRange(range: number) {
  currentRange.value = range;
  tokenStats.value = await fetchTokenStats(range);
}

onMounted(load);
</script>

<template>
  <section>
    <div class="core-stage">
      <div class="orb" :class="{ 'orb--settled': !loading }">
        <span class="orb-ring orb-ring--1" aria-hidden="true"></span>
        <span class="orb-ring orb-ring--2" aria-hidden="true"></span>
        <span class="orb-core" aria-hidden="true">
          <span class="orb-nucleus" aria-hidden="true"></span>
        </span>
      </div>
    </div>

    <div v-if="loading" class="status-line">{{ t("common.loading") }}</div>
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

      <div class="token-section">
        <div class="token-header">
          <h2>{{ t("dashboard.tokenUsageTitle") }}</h2>
          <div class="range-switch">
            <button
              v-for="opt in rangeOptions"
              :key="opt.value"
              :class="{ active: currentRange === opt.value }"
              @click="loadTokenRange(opt.value)"
            >
              {{ opt.label }}
            </button>
          </div>
        </div>

        <div v-if="tokenStats" class="token-content">
          <div class="token-summary">
            <StatCard :label="t('dashboard.totalTokens')" :value="formatTokens(totalTokenRange.total)" />
            <StatCard :label="t('dashboard.promptTokens')" :value="formatTokens(totalTokenRange.prompt)" />
            <StatCard :label="t('dashboard.completionTokens')" :value="formatTokens(totalTokenRange.completion)" />
          </div>

          <div class="token-charts">
            <div class="token-panel">
              <h3>{{ t("dashboard.tokenDailyTitle") }}</h3>
              <LineChart :data="tokenStats.daily" />
            </div>
            <div class="token-panel">
              <h3>{{ t("dashboard.tokenTodayTitle") }}</h3>
              <PieChart :data="tokenStats.today_by_provider" />
            </div>
          </div>
        </div>
        <p v-else class="status-line">{{ t("dashboard.noTokenData") }}</p>
      </div>
    </template>
  </section>
</template>

<style scoped>
.status-line {
  text-align: center;
  opacity: 0.7;
  margin: 0 0 1.5rem;
}

.cards {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
  justify-content: center;
  margin: 0 0 1.5rem;
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

/* Token section ---------------------------------------------------- */
.token-section {
  margin-top: 2rem;
  padding-top: 1.5rem;
  border-top: 1px solid var(--border);
}
.token-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
  margin-bottom: 1rem;
}
.token-header h2 {
  font-size: 1rem;
  margin: 0;
}
.range-switch {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.range-switch button {
  border: none;
  background: transparent;
  padding: 0.3rem 0.8rem;
  font-size: 0.8rem;
  cursor: pointer;
  color: inherit;
  font: inherit;
}
.range-switch button.active {
  background: var(--accent);
  color: white;
}
.token-summary {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.75rem;
  margin-bottom: 1rem;
}
.token-charts {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(200px, 1fr);
  gap: 1.5rem;
}
.token-panel {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.25rem;
}
.token-panel h3 {
  font-size: 0.85rem;
  margin: 0 0 0.75rem;
  opacity: 0.7;
  font-weight: 500;
}
@media (max-width: 720px) {
  .token-charts {
    grid-template-columns: 1fr;
  }
}

/* ---- Living core -------------------------------------------------- */

.core-stage {
  container-type: inline-size;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: clamp(1.5rem, 6cqw, 3.5rem) 1rem clamp(2rem, 7cqw, 4rem);
}

.orb {
  --orb-accent: #5b9bd5;
  --orb-glow: rgba(91, 155, 213, 0.3);
  --orb-edge: rgba(91, 155, 213, 0.5);
  position: relative;
  width: 30cqw;
  height: 30cqw;
  min-width: 160px;
  min-height: 160px;
  max-width: 340px;
  max-height: 340px;
}

.orb-ring {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  border: 1px solid var(--orb-edge);
  animation: orb-sonar 3.6s cubic-bezier(0.25, 0.6, 0.4, 1) infinite;
}
.orb-ring--2 {
  animation-delay: 1.8s;
}

@keyframes orb-sonar {
  0% {
    transform: scale(0.82);
    opacity: 0.55;
  }
  100% {
    transform: scale(1.35);
    opacity: 0;
  }
}

.orb-core {
  position: absolute;
  inset: 6%;
  border-radius: 50%;
  overflow: hidden;
  background: radial-gradient(
    circle at 32% 28%,
    color-mix(in srgb, var(--orb-accent) 78%, white 22%) 0%,
    var(--orb-accent) 46%,
    color-mix(in srgb, var(--orb-accent) 45%, black 55%) 100%
  );
  box-shadow:
    0 0 24px 4px var(--orb-glow),
    0 0 48px 12px var(--orb-glow),
    0 16px 30px -12px rgba(0, 0, 0, 0.5),
    inset -10px -12px 24px rgba(0, 0, 0, 0.45),
    inset 8px 10px 20px rgba(255, 255, 255, 0.1);
  animation: orb-breathe 3.5s ease-in-out infinite;
  transform-origin: center;
}

@keyframes orb-breathe {
  0%,
  100% {
    transform: scale(0.8);
    box-shadow:
      0 0 18px 2px var(--orb-glow),
      0 0 36px 8px var(--orb-glow),
      0 16px 30px -12px rgba(0, 0, 0, 0.5),
      inset -10px -12px 24px rgba(0, 0, 0, 0.45),
      inset 8px 10px 20px rgba(255, 255, 255, 0.1);
  }
  50% {
    transform: scale(1.0);
    box-shadow:
      0 0 30px 8px var(--orb-glow),
      0 0 60px 18px var(--orb-glow),
      0 18px 34px -12px rgba(0, 0, 0, 0.45),
      inset -10px -12px 26px rgba(0, 0, 0, 0.4),
      inset 8px 10px 22px rgba(255, 255, 255, 0.12);
  }
}

.orb-nucleus {
  position: absolute;
  inset: 0%;
  border-radius: 50%;
  background: radial-gradient(
    circle at 38% 32%,
    rgba(255, 255, 255, 0.7),
    rgba(255, 255, 255, 0.2) 45%,
    transparent 75%
  );
  filter: blur(0.5px);
  animation: orb-nucleus-pulse 3.6s ease-in-out infinite;
}

@keyframes orb-nucleus-pulse {
  0%,
  100% {
    opacity: 0.55;
  }
  50% {
    opacity: 0.9;
  }
}

.orb--settled .orb-ring {
  animation-duration: 3.5s;
}

@media (prefers-reduced-motion: reduce) {
  .orb-ring,
  .orb-core,
  .orb-nucleus {
    animation: none;
  }
}
</style>
