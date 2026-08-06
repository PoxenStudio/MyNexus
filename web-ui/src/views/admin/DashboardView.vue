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
    <!-- Living core: a breathing, self-animating sphere standing in for the
         "title" this page used to have — the product's autonomous, always-on
         feel rather than a static heading. Diameter tracks 30% of the
         section's own width via container query units, clamped so it never
         gets absurdly small or large. -->
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

/* ---- Living core -------------------------------------------------- */

.core-stage {
  container-type: inline-size;
  display: flex;
  justify-content: center;
  align-items: center;
  padding: clamp(1.5rem, 6cqw, 3.5rem) 1rem clamp(2rem, 7cqw, 4rem);
}

.orb {
  /* The orb is a light source, not text — it should glow the same vivid
     steel-blue in both themes. --accent goes near-black (#003153) in light
     mode for text readability, which would muddy the sphere; pin a bright
     blue locally and derive the glow/edge from it so the orb stays vivid
     on white backgrounds. */
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

/* Sonar rings: expand outward from the core and fade, one lagging the
   other, so the pulse reads as radiating rather than blinking. */
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

/* The sphere itself: a soft radial body that slowly breathes in scale and
   glow, echoing MyBooks' .avatar-round breathing animation but built up
   with extra depth (sheen sweep + nucleus) to read as "alive" rather than
   just a pulsing circle. Lighting is directional from the upper-left: a
   tinted highlight (not pure white) and a deeper lower-right shadow, plus
   a contact shadow below, so the orb reads as a 3D ball instead of a
   flat disc. */
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
    /* outer ambient glow */
    0 0 24px 4px var(--orb-glow),
    0 0 48px 12px var(--orb-glow),
    /* ground contact shadow — anchors the orb in space */
    0 16px 30px -12px rgba(0, 0, 0, 0.5),
    /* directional inner shading: deeper at lower-right, lifted at upper-left */
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

/* A brighter nucleus pulsing in lockstep with the outer breathe — same
   3.6s cadence and phase (both peak at 50%) so the highlight swells with
   the sphere instead of drifting against it. Kept small and tinted so it
   reads as a specular catch-light on the sphere rather than a flat white
   patch. */
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

/* Settling in once data has loaded: rings ease to a slightly calmer pace
   rather than an abrupt style change. */
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
