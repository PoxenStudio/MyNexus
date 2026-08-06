<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import AppIcon from "../components/AppIcon.vue";

const { t } = useI18n();
const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

const username = ref("");
const password = ref("");
const error = ref("");
const submitting = ref(false);
const passwordVisible = ref(false);

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
      <span class="brand-name">My Nexus</span>
    </div>
    <form class="login-card" @submit.prevent="onSubmit">
      <h1>{{ t("login.title") }}</h1>
      <label>
        {{ t("login.username") }}
        <input v-model="username" autocomplete="username" required />
      </label>
      <label>
        {{ t("login.password") }}
        <div class="password-field">
          <input
            v-model="password"
            :type="passwordVisible ? 'text' : 'password'"
            autocomplete="current-password"
            required
          />
          <button
            type="button"
            class="password-toggle"
            :title="t(passwordVisible ? 'login.hidePassword' : 'login.showPassword')"
            :aria-label="t(passwordVisible ? 'login.hidePassword' : 'login.showPassword')"
            @click="passwordVisible = !passwordVisible"
          >
            <AppIcon :name="passwordVisible ? 'eyeOff' : 'eye'" :size="18" />
          </button>
        </div>
      </label>
      <p v-if="error" class="error">{{ error }}</p>
      <button type="submit" :disabled="submitting">{{ t("login.submit") }}</button>
    </form>
    <div class="brand">
      <span style="color:grey">PoxenStudio, 2026</span>
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
  width: 100%;
}
.password-field {
  position: relative;
  display: flex;
}
.password-field input {
  padding-right: 2.25rem;
}
.password-toggle {
  position: absolute;
  top: 0;
  right: 0;
  height: 100%;
  width: 2.25rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--text);
  opacity: 0.65;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
}
.password-toggle:hover {
  opacity: 1;
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
