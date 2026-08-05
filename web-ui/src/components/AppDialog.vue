<script setup lang="ts">
withDefaults(defineProps<{ modelValue: boolean; title?: string }>(), { title: "" });
const emit = defineEmits<{ (e: "update:modelValue", value: boolean): void }>();

function close() {
  emit("update:modelValue", false);
}
</script>

<template>
  <Teleport to="body">
    <div v-if="modelValue" class="overlay" @click.self="close">
      <div class="dialog" role="dialog" aria-modal="true">
        <div class="header">
          <h2>{{ title }}</h2>
          <button class="icon-btn" type="button" :aria-label="'close'" @click="close">✕</button>
        </div>
        <div class="body">
          <slot />
        </div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 100;
  padding: 1rem;
}
.dialog {
  width: 100%;
  max-width: 420px;
  max-height: calc(100vh - 2rem);
  overflow-y: auto;
  background: var(--surface, var(--bg));
  border-radius: 12px;
  box-shadow: var(--elevation-2, var(--shadow));
  border: 1px solid var(--border);
}
.header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 1rem 1.25rem;
  border-bottom: 1px solid var(--border);
}
.header h2 {
  margin: 0;
  font-size: 1.05rem;
}
.icon-btn {
  border: none;
  background: transparent;
  color: var(--text);
  cursor: pointer;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  font-size: 0.9rem;
}
.icon-btn:hover {
  background: var(--surface-hover, rgba(0, 0, 0, 0.06));
}
.body {
  padding: 1.25rem;
}
</style>
