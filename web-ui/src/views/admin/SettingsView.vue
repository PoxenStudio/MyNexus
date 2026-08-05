<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { changePassword } from "../../api/auth";

const { t } = useI18n();

const oldPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const error = ref("");
const success = ref(false);
const submitting = ref(false);

async function onSubmit() {
  error.value = "";
  success.value = false;

  if (newPassword.value !== confirmPassword.value) {
    error.value = t("settings.mismatch");
    return;
  }
  if (newPassword.value.length < 4) {
    error.value = t("settings.tooShort");
    return;
  }

  submitting.value = true;
  try {
    await changePassword(oldPassword.value, newPassword.value);
    success.value = true;
    oldPassword.value = "";
    newPassword.value = "";
    confirmPassword.value = "";
  } catch (e: any) {
    error.value = e?.response?.data?.error || t("settings.error");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <section>
    <h1>{{ t("settings.title") }}</h1>

    <form class="password-form" @submit.prevent="onSubmit">
      <h2>{{ t("settings.changePassword") }}</h2>
      <label>
        {{ t("settings.oldPassword") }}
        <input v-model="oldPassword" type="password" autocomplete="current-password" required />
      </label>
      <label>
        {{ t("settings.newPassword") }}
        <input v-model="newPassword" type="password" autocomplete="new-password" required />
      </label>
      <label>
        {{ t("settings.confirmPassword") }}
        <input v-model="confirmPassword" type="password" autocomplete="new-password" required />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="success" class="success">{{ t("settings.success") }}</p>
      <button type="submit" :disabled="submitting">{{ t("common.save") }}</button>
    </form>
  </section>
</template>

<style scoped>
.password-form {
  max-width: 360px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin-top: 1rem;
  padding: 1.25rem;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.password-form h2 {
  font-size: 1rem;
  margin: 0;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
}
input {
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: inherit;
}
button {
  align-self: flex-start;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: none;
  background: var(--accent);
  color: white;
  cursor: pointer;
  font-weight: 600;
}
.error {
  color: #d33;
  font-size: 0.85rem;
  margin: 0;
}
.success {
  color: #2a9d5c;
  font-size: 0.85rem;
  margin: 0;
}
</style>
