<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const error = ref("");
const submitting = ref(false);

async function onSubmit() {
  error.value = "";
  submitting.value = true;
  try {
    await auth.login(username.value, password.value);
    const redirect = (route.query.redirect as string) || "/";
    router.push(redirect);
  } catch {
    error.value = t("login.error");
  } finally {
    submitting.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <div class="brand">
      <img src="/star.svg" class="brand-logo" alt="" aria-hidden="true" />
      <span class="brand-name">MyNexus</span>
    </div>
    <form class="login-card" @submit.prevent="onSubmit">
      <h1>{{ t("login.title") }}</h1>
      <label>
        {{ t("login.username") }}
        <input v-model="username" autocomplete="username" required />
      </label>
      <label>
        {{ t("login.password") }}
        <input v-model="password" type="password" autocomplete="current-password" required />
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="submitting">{{ t("login.submit") }}</button>
    </form>
    <div class="brand">
      <span class="brand-mark">PoxenStudio, 2026</span>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 1.5rem;
}
.login-card {
  width: 320px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 2rem;
  border: 1px solid var(--border);
  border-radius: 12px;
}
.brand {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
  text-align: center;
}
.brand-logo {
  width: 42px;
  height: 42px;
  display: block;
}
.brand-name {
  font-weight: 600;
  font-size: 2rem;
  color: var(--text-h);
}
h1 {
  font-size: 1.1rem;
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
  padding: 0.5rem 0.6rem;
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
</style>
