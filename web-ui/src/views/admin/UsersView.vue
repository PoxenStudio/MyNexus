<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useAuthStore } from "../../stores/auth";
import AppDialog from "../../components/AppDialog.vue";
import ConfirmDialog from "../../components/ConfirmDialog.vue";
import {
  createUser,
  listUsers,
  resetUserPassword,
  setUserRole,
  setUserStatus,
  type AppUser,
} from "../../api/users";

const { t } = useI18n();
const auth = useAuthStore();

const users = ref<AppUser[]>([]);
const loading = ref(true);

async function load() {
  loading.value = true;
  try {
    users.value = await listUsers();
  } finally {
    loading.value = false;
  }
}
onMounted(load);

// --- create ---
const createDialogOpen = ref(false);
const newUsername = ref("");
const newNickname = ref("");
const newPassword = ref("");
const newRole = ref<"admin" | "user">("user");
const createError = ref("");
const creating = ref(false);

function openCreateDialog() {
  newUsername.value = "";
  newNickname.value = "";
  newPassword.value = "";
  newRole.value = "user";
  createError.value = "";
  createDialogOpen.value = true;
}

async function onCreate() {
  createError.value = "";
  creating.value = true;
  try {
    await createUser(newUsername.value, newNickname.value, newPassword.value, newRole.value);
    createDialogOpen.value = false;
    await load();
  } catch (e: any) {
    createError.value = e?.response?.data?.error || t("users.createError");
  } finally {
    creating.value = false;
  }
}

// --- role ---
async function onRoleChange(u: AppUser, role: string) {
  try {
    await setUserRole(u.id, role);
    await load();
  } catch (e: any) {
    alert(e?.response?.data?.error || t("users.updateError"));
    await load(); // revert the <select> to the server's actual value
  }
}

// --- status (enable/disable) ---
const statusDialogOpen = ref(false);
const statusTarget = ref<AppUser | null>(null);

function askToggleStatus(u: AppUser) {
  statusTarget.value = u;
  statusDialogOpen.value = true;
}

async function onConfirmToggleStatus() {
  if (!statusTarget.value) return;
  const nextStatus = statusTarget.value.status === "active" ? "disabled" : "active";
  try {
    await setUserStatus(statusTarget.value.id, nextStatus);
    await load();
  } catch (e: any) {
    alert(e?.response?.data?.error || t("users.updateError"));
  }
}

// --- reset password ---
const resetDialogOpen = ref(false);
const resetTarget = ref<AppUser | null>(null);
const resetPasswordValue = ref("");
const resetError = ref("");
const resetting = ref(false);

function openResetDialog(u: AppUser) {
  resetTarget.value = u;
  resetPasswordValue.value = "";
  resetError.value = "";
  resetDialogOpen.value = true;
}

async function onResetPassword() {
  if (!resetTarget.value) return;
  resetError.value = "";
  if (resetPasswordValue.value.length < 4) {
    resetError.value = t("settings.tooShort");
    return;
  }
  resetting.value = true;
  try {
    await resetUserPassword(resetTarget.value.id, resetPasswordValue.value);
    resetDialogOpen.value = false;
  } catch (e: any) {
    resetError.value = e?.response?.data?.error || t("users.updateError");
  } finally {
    resetting.value = false;
  }
}
</script>

<template>
  <section>
    <h1>{{ t("users.title") }}</h1>

    <button class="primary create-trigger" type="button" @click="openCreateDialog">{{ t("users.createNew") }}</button>

    <div v-if="loading">{{ t("common.loading") }}</div>
    <table v-else-if="users.length">
      <thead>
        <tr>
          <th>{{ t("users.table.user") }}</th>
          <th>{{ t("users.table.role") }}</th>
          <th>{{ t("users.table.status") }}</th>
          <th>{{ t("users.table.lastLogin") }}</th>
          <th>{{ t("users.table.actions") }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="u in users" :key="u.id">
          <td>
            <div class="user-cell">
              <strong>{{ u.nickname || u.username }}</strong>
              <span class="username-sub">{{ u.username }}</span>
            </div>
          </td>
          <td>
            <select
              :value="u.role"
              :disabled="u.username === auth.username"
              @change="onRoleChange(u, ($event.target as HTMLSelectElement).value)"
            >
              <option value="admin">{{ t("users.roleAdmin") }}</option>
              <option value="user">{{ t("users.roleUser") }}</option>
            </select>
          </td>
          <td>{{ u.status === "active" ? t("users.statusActive") : t("users.statusDisabled") }}</td>
          <td>{{ u.last_login_at ? new Date(u.last_login_at).toLocaleString() : t("users.neverLoggedIn") }}</td>
          <td>
            <div class="actions">
              <button class="ghost" type="button" @click="openResetDialog(u)">{{ t("users.resetPassword") }}</button>
              <button
                v-if="u.username !== auth.username"
                class="ghost"
                type="button"
                @click="askToggleStatus(u)"
              >
                {{ u.status === "active" ? t("users.disable") : t("users.enable") }}
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else>{{ t("common.empty") }}</p>

    <AppDialog v-model="createDialogOpen" :title="t('users.createNew')">
      <form class="user-form" @submit.prevent="onCreate">
        <label>
          {{ t("users.username") }}
          <input v-model="newUsername" required />
        </label>
        <label>
          {{ t("users.nickname") }}
          <input v-model="newNickname" />
        </label>
        <label>
          {{ t("users.password") }}
          <input v-model="newPassword" type="password" autocomplete="new-password" required />
        </label>
        <label>
          {{ t("users.role") }}
          <select v-model="newRole">
            <option value="user">{{ t("users.roleUser") }}</option>
            <option value="admin">{{ t("users.roleAdmin") }}</option>
          </select>
        </label>
        <p v-if="createError" class="error">{{ createError }}</p>
        <div class="dialog-actions">
          <button type="button" class="ghost" @click="createDialogOpen = false">{{ t("common.cancel") }}</button>
          <button type="submit" class="primary" :disabled="creating">{{ t("common.create") }}</button>
        </div>
      </form>
    </AppDialog>

    <AppDialog v-model="resetDialogOpen" :title="t('users.resetPasswordTitle')">
      <form class="user-form" @submit.prevent="onResetPassword">
        <p v-if="resetTarget">{{ resetTarget.nickname || resetTarget.username }}</p>
        <label>
          {{ t("users.newPassword") }}
          <input v-model="resetPasswordValue" type="password" autocomplete="new-password" required />
        </label>
        <p v-if="resetError" class="error">{{ resetError }}</p>
        <div class="dialog-actions">
          <button type="button" class="ghost" @click="resetDialogOpen = false">{{ t("common.cancel") }}</button>
          <button type="submit" class="primary" :disabled="resetting">{{ t("common.save") }}</button>
        </div>
      </form>
    </AppDialog>

    <ConfirmDialog
      v-model="statusDialogOpen"
      :title="statusTarget?.status === 'active' ? t('users.disable') : t('users.enable')"
      :message="statusTarget?.status === 'active' ? t('users.confirmDisable') : t('users.confirmEnable')"
      :danger="statusTarget?.status === 'active'"
      @confirm="onConfirmToggleStatus"
    />
  </section>
</template>

<style scoped>
button.primary {
  padding: 0.5rem 1rem;
  border-radius: 6px;
  border: none;
  background: var(--accent);
  color: white;
  cursor: pointer;
  font-weight: 600;
}
/* Spacing for the page-top trigger button only — kept off the shared
   .primary class so it doesn't stretch the dialog's Cancel/Create row
   (flex row default align-items: stretch matches the tallest item's outer
   box, margin included). */
.create-trigger {
  margin-bottom: 1rem;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th,
td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.9rem;
}
.user-cell {
  display: flex;
  flex-direction: column;
}
.username-sub {
  font-size: 0.8rem;
  opacity: 0.65;
}
.actions {
  display: flex;
  gap: 0.5rem;
}
select,
input {
  padding: 0.35rem 0.5rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: inherit;
}
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
}
.user-form {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}
.user-form label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.9rem;
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
