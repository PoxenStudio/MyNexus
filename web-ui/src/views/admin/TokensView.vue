<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { createToken, listTokens, revokeToken, type ApiToken } from "../../api/tokens";

const { t } = useI18n();
const tokens = ref<ApiToken[]>([]);
const loading = ref(true);
const alias = ref("");
const creating = ref(false);
const justCreated = ref<{ token: string; alias: string } | null>(null);

async function load() {
  loading.value = true;
  try {
    tokens.value = await listTokens();
  } finally {
    loading.value = false;
  }
}

async function onCreate() {
  creating.value = true;
  try {
    const result = await createToken(alias.value);
    justCreated.value = { token: result.token, alias: result.alias };
    alias.value = "";
    await load();
  } finally {
    creating.value = false;
  }
}

async function onRevoke(id: string) {
  if (!confirm(t("common.confirmRevoke"))) return;
  await revokeToken(id);
  await load();
}

onMounted(load);
</script>

<template>
  <section>
    <h1>{{ t("tokens.title") }}</h1>

    <div class="create-box">
      <h2>{{ t("tokens.createNew") }}</h2>
      <div class="row">
        <input v-model="alias" :placeholder="t('tokens.aliasPlaceholder')" />
        <button :disabled="creating" @click="onCreate">{{ t("common.create") }}</button>
      </div>
      <div v-if="justCreated" class="reveal">
        <p>{{ t("tokens.createdOnce") }} <strong>{{ justCreated.alias }}</strong></p>
        <code>{{ justCreated.token }}</code>
        <button class="ghost" @click="justCreated = null">{{ t("common.close") }}</button>
      </div>
    </div>

    <div v-if="loading">{{ t("common.loading") }}</div>
    <table v-else-if="tokens.length">
      <thead>
        <tr>
          <th>{{ t("tokens.table.alias") }}</th>
          <th>{{ t("tokens.table.token") }}</th>
          <th>{{ t("tokens.table.lastUsed") }}</th>
          <th>{{ t("tokens.table.createdAt") }}</th>
          <th>{{ t("tokens.table.status") }}</th>
          <th>{{ t("tokens.table.actions") }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="tk in tokens" :key="tk.id">
          <td>{{ tk.alias || "—" }}</td>
          <td class="mono">{{ tk.masked_token }}</td>
          <td>{{ tk.last_used_at ? new Date(tk.last_used_at).toLocaleString() : t("tokens.neverUsed") }}</td>
          <td>{{ new Date(tk.created_at).toLocaleString() }}</td>
          <td>{{ tk.is_revoked ? t("tokens.revoked") : t("tokens.active") }}</td>
          <td>
            <button v-if="!tk.is_revoked" class="ghost" @click="onRevoke(tk.id)">{{ t("common.revoke") }}</button>
          </td>
        </tr>
      </tbody>
    </table>
    <p v-else>{{ t("common.empty") }}</p>
  </section>
</template>

<style scoped>
.create-box {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.25rem;
  margin: 1rem 0 1.5rem;
}
.create-box h2 {
  font-size: 1rem;
  margin: 0 0 0.75rem;
}
.row {
  display: flex;
  gap: 0.5rem;
}
.row input {
  flex: 1;
  padding: 0.4rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: inherit;
}
.reveal {
  margin-top: 1rem;
  padding: 0.75rem;
  background: var(--accent-bg);
  border-radius: 8px;
}
.reveal code {
  display: block;
  margin: 0.5rem 0;
  word-break: break-all;
  background: var(--code-bg);
  padding: 0.5rem;
  border-radius: 6px;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.9rem;
}
.mono {
  font-family: var(--mono);
}
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
}
</style>
