<script setup lang="ts">
import { useI18n } from "vue-i18n";
import AppDialog from "./AppDialog.vue";

// Reusable replacement for the browser's native confirm() — same title-bar +
// message + confirm/cancel-button shape as AppDialog's other consumers
// (e.g. AdminAccountView.vue's change-password dialog), just pre-wired for
// the "are you sure?" case: title, a message body, and Cancel/Confirm
// buttons that close the dialog and emit which one was picked. Callers stay
// in charge of the actual action (do it in the @confirm handler) — this
// component only owns the yes/no prompt, not what happens after.
withDefaults(
  defineProps<{
    modelValue: boolean;
    title: string;
    message: string;
    confirmText?: string;
    cancelText?: string;
    // Red confirm button for destructive/irreversible actions (delete-like);
    // the default accent color is for anything else that just warrants a
    // heads-up (e.g. "this will overwrite existing data").
    danger?: boolean;
  }>(),
  { confirmText: "", cancelText: "", danger: false },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "confirm"): void;
  (e: "cancel"): void;
}>();

const { t } = useI18n();

function onCancel() {
  emit("update:modelValue", false);
  emit("cancel");
}

function onConfirm() {
  emit("update:modelValue", false);
  emit("confirm");
}
</script>

<template>
  <AppDialog :model-value="modelValue" :title="title" @update:model-value="onCancel">
    <p class="message">{{ message }}</p>
    <div class="dialog-actions">
      <button type="button" class="ghost" @click="onCancel">{{ cancelText || t("common.cancel") }}</button>
      <button type="button" :class="danger ? 'danger' : 'primary'" @click="onConfirm">
        {{ confirmText || t("common.confirm") }}
      </button>
    </div>
  </AppDialog>
</template>

<style scoped>
.message {
  margin: 0 0 1.25rem;
  line-height: 1.6;
  white-space: pre-wrap;
}
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.4rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
  font-size: 0.85rem;
}
button.primary,
button.danger {
  border: none;
  padding: 0.4rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font-weight: 600;
  font-size: 0.85rem;
  color: white;
}
button.primary {
  background: var(--accent);
}
button.danger {
  background: #d33;
}
</style>
