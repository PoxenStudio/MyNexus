<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { useAuthStore } from "../../stores/auth";
import AppDialog from "../../components/AppDialog.vue";
import { changePassword } from "../../api/auth";

const { t } = useI18n();
const auth = useAuthStore();

const avatarInput = ref<HTMLInputElement | null>(null);
const avatarUploading = ref(false);
const avatarError = ref("");

async function onAvatarSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  avatarError.value = "";
  avatarUploading.value = true;
  try {
    await auth.uploadAvatar(file);
  } catch (err: any) {
    avatarError.value = err?.response?.data?.error || t("settings.avatarError");
  } finally {
    avatarUploading.value = false;
    if (avatarInput.value) avatarInput.value.value = "";
  }
}

const passwordDialogOpen = ref(false);
const oldPassword = ref("");
const newPassword = ref("");
const confirmPassword = ref("");
const passwordError = ref("");
const passwordSubmitting = ref(false);

function openPasswordDialog() {
  oldPassword.value = "";
  newPassword.value = "";
  confirmPassword.value = "";
  passwordError.value = "";
  passwordDialogOpen.value = true;
}

async function onSubmitPassword() {
  passwordError.value = "";

  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = t("settings.mismatch");
    return;
  }
  if (newPassword.value.length < 4) {
    passwordError.value = t("settings.tooShort");
    return;
  }

  passwordSubmitting.value = true;
  try {
    await changePassword(oldPassword.value, newPassword.value);
    passwordDialogOpen.value = false;
  } catch (e: any) {
    passwordError.value = e?.response?.data?.error || t("settings.error");
  } finally {
    passwordSubmitting.value = false;
  }
}
</script>

<template>
  <section>
    <h1>{{ t("settings.adminAccount") }}</h1>

    <div class="card">
      <h2>{{ t("settings.avatar") }}</h2>
      <div class="avatar-row">
        <div class="avatar-preview">
          <img v-if="auth.fullAvatarUrl" :src="auth.fullAvatarUrl" :alt="auth.username ?? ''" />
          <span v-else class="avatar-fallback">{{ (auth.username || "?").slice(0, 1).toUpperCase() }}</span>
        </div>
        <div class="avatar-actions">
          <label class="upload-btn">
            {{ avatarUploading ? t("common.loading") : t("settings.changeAvatar") }}
            <input
              ref="avatarInput"
              type="file"
              accept=".png,.jpg,.jpeg,.webp,.gif"
              class="hidden-input"
              :disabled="avatarUploading"
              @change="onAvatarSelected"
            />
          </label>
          <p v-if="avatarError" class="error">{{ avatarError }}</p>
        </div>
      </div>
    </div>

    <div class="card">
      <h2>{{ t("settings.account") }}</h2>
      <p class="username-line">{{ t("login.username") }}: <strong>{{ auth.username }}</strong></p>
      <button class="primary" type="button" @click="openPasswordDialog">{{ t("settings.changePassword") }}</button>
    </div>

    <AppDialog v-model="passwordDialogOpen" :title="t('settings.changePassword')">
      <form class="password-form" @submit.prevent="onSubmitPassword">
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
        <p v-if="passwordError" class="error">{{ passwordError }}</p>
        <div class="dialog-actions">
          <button type="button" class="ghost" @click="passwordDialogOpen = false">{{ t("common.cancel") }}</button>
          <button type="submit" class="primary" :disabled="passwordSubmitting">{{ t("common.save") }}</button>
        </div>
      </form>
    </AppDialog>
  </section>
</template>

<style scoped>
.card {
  max-width: 480px;
  display: flex;
  flex-direction: column;
  gap: 1rem;
  margin: 1rem 0;
  padding: 1.25rem;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.card h2 {
  font-size: 1rem;
  margin: 0;
}
.avatar-row {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}
.avatar-preview {
  width: 72px;
  height: 72px;
  border-radius: 50%;
  overflow: hidden;
  background: var(--accent-bg);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.avatar-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.avatar-fallback {
  font-size: 1.5rem;
  font-weight: 600;
  color: var(--accent);
}
.avatar-actions {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
}
.upload-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.5rem 1rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  width: fit-content;
}
.upload-btn:hover {
  background: var(--surface-hover, rgba(0, 0, 0, 0.05));
}
.hidden-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
}
.username-line {
  margin: 0;
  font-size: 0.9rem;
}
button.primary {
  align-self: flex-start;
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: none;
  background: var(--accent);
  color: white;
  cursor: pointer;
  font-weight: 600;
}
button.primary:disabled {
  opacity: 0.6;
  cursor: default;
}
button.ghost {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: inherit;
  cursor: pointer;
}
.password-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
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
.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
}
.error {
  color: #d33;
  font-size: 0.85rem;
  margin: 0;
}
</style>
