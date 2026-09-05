<script setup lang="ts">
import type { Definition } from "../api/books";

defineProps<{ definitions: Definition[] }>();
</script>

<template>
  <dl v-if="definitions.length" class="definition-list">
    <template v-for="def in definitions" :key="def.name">
      <dt>{{ def.name }}</dt>
      <dd>{{ def.content }}</dd>
    </template>
  </dl>
  <p v-else class="empty"><slot name="empty" /></p>
</template>

<style scoped>
.definition-list {
  margin: 0;
  display: grid;
  grid-template-columns: max-content 1fr;
  gap: 0.5em 0.75em;
}
.definition-list dt {
  font-weight: 600;
  color: var(--accent);
  white-space: nowrap;
}
.definition-list dd {
  margin: 0;
  opacity: 0.9;
}
.empty {
  margin: 0;
  opacity: 0.6;
  font-size: 0.9rem;
}
</style>
