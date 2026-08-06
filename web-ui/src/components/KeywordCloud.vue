<script setup lang="ts">
import { computed } from "vue";
import type { Keyword } from "../api/books";

const props = defineProps<{ keywords: Keyword[] }>();

// Weighted tag cloud, not a pixel-packed word cloud: flex-wrap pills sized
// by weight bucket. Avoids the collision-detection/canvas layout a "real"
// word cloud needs, which doesn't play well with responsive reflow or
// arbitrary CJK/Latin mixed text.
const TIERS = 5;
const MIN_SCALE = 0.85;
const MAX_SCALE = 2.1;

const items = computed(() => {
  const kws = props.keywords;
  if (!kws.length) return [];
  const max = Math.max(...kws.map((k) => k.weight));
  const min = Math.min(...kws.map((k) => k.weight));
  const span = max - min;
  return kws.map((k) => {
    // min-max normalize to [0,1], then bucket into TIERS discrete steps so
    // near-equal weights don't produce visually-noisy near-equal font sizes.
    const ratio = span > 0 ? (k.weight - min) / span : 1;
    const tier = Math.round(ratio * (TIERS - 1));
    const scale = MIN_SCALE + (tier / (TIERS - 1)) * (MAX_SCALE - MIN_SCALE);
    return { term: k.term, tier, scale };
  });
});
</script>

<template>
  <div v-if="items.length" class="keyword-cloud">
    <span
      v-for="item in items"
      :key="item.term"
      class="keyword"
      :class="`tier-${item.tier}`"
      :style="{ fontSize: item.scale + 'em' }"
    >
      {{ item.term }}
    </span>
  </div>
  <p v-else class="empty"><slot name="empty" /></p>
</template>

<style scoped>
.keyword-cloud {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 0.4em 0.7em;
  line-height: 1.4;
}
.keyword {
  white-space: nowrap;
  color: var(--accent);
  font-weight: 500;
}
/* Lower tiers fade slightly so the cloud reads as one weighted mass rather
   than a flat list — the size difference alone can be subtle at small
   scale factors. */
.tier-0,
.tier-1 {
  opacity: 0.65;
  font-weight: 400;
}
.tier-2 {
  opacity: 0.8;
}
.empty {
  margin: 0;
  opacity: 0.6;
  font-size: 0.9rem;
}
</style>
