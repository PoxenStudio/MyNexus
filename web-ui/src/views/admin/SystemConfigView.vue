<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { fetchSettings, saveSettings, type SystemSettings } from "../../api/system";
import { useAuthStore } from "../../stores/auth";

const { t } = useI18n();
const router = useRouter();
const auth = useAuthStore();

const settings = ref<SystemSettings | null>(null);
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref("");

async function load() {
  loading.value = true;
  try {
    settings.value = await fetchSettings();
  } finally {
    loading.value = false;
  }
}

async function onSave() {
  if (!settings.value) return;
  error.value = "";
  saving.value = true;
  try {
    await saveSettings(settings.value);
    saved.value = true;
    // core-api restarts after this call (see api/system.ts) — its in-memory
    // session table is gone with it, so the current session cookie stops
    // being valid. Send the admin back to /login instead of waiting for the
    // next request to fail with a confusing 401.
    setTimeout(() => {
      auth.username = null;
      router.push({ name: "login" });
    }, 2500);
  } catch (e: any) {
    error.value = e?.response?.data?.error || t("settings.error");
  } finally {
    saving.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <h1>{{ t("settings.systemConfig") }}</h1>

    <div v-if="loading">{{ t("common.loading") }}</div>
    <form v-else-if="settings" class="config-form" @submit.prevent="onSave">
      <p class="hint">{{ t("settings.restartHint") }}</p>

      <fieldset>
        <legend>{{ t("settings.storage") }}</legend>
        <label>
          {{ t("settings.storageDatabase") }}
          <select v-model="settings.storage.database">
            <option value="sqlite">sqlite</option>
            <option value="postgres">postgres</option>
          </select>
        </label>
        <label>
          {{ t("settings.sqlitePath") }}
          <input v-model="settings.storage.sqlite.path" />
        </label>
        <label>
          {{ t("settings.postgresDsn") }}
          <input v-model="settings.storage.postgres.dsn" placeholder="postgres://user:pass@host:5432/db" />
        </label>
        <label>
          {{ t("settings.vectorStore") }}
          <select v-model="settings.storage.vector_store">
            <option value="chroma">chroma</option>
            <option value="local">local</option>
          </select>
        </label>
        <label>
          {{ t("settings.vectorStorePath") }}
          <input v-model="settings.storage.vector_store_path" />
        </label>
        <label>
          {{ t("settings.uploadDir") }}
          <input v-model="settings.storage.upload_dir" />
        </label>
      </fieldset>

      <fieldset>
        <legend>{{ t("settings.worker") }}</legend>
        <label>
          {{ t("settings.workerUrl") }}
          <input v-model="settings.worker.url" placeholder="host:port" />
        </label>
        <label>
          {{ t("settings.maxConcurrentTasks") }}
          <input v-model.number="settings.worker.max_concurrent_tasks" type="number" min="1" />
        </label>
        <label>
          {{ t("settings.taskTimeoutSeconds") }}
          <input v-model.number="settings.worker.task_timeout_seconds" type="number" min="1" />
        </label>
      </fieldset>

      <fieldset>
        <legend>{{ t("settings.embedding") }}</legend>
        <label>
          {{ t("settings.provider") }}
          <select v-model="settings.embedding.provider">
            <option value="openai">openai</option>
            <option value="ollama">ollama</option>
          </select>
        </label>
        <template v-if="settings.embedding.provider === 'openai'">
          <label>
            {{ t("settings.apiKey") }}
            <input v-model="settings.embedding.openai.api_key" type="password" autocomplete="off" />
          </label>
          <label>
            {{ t("settings.baseUrl") }}
            <input v-model="settings.embedding.openai.base_url" />
          </label>
          <label>
            {{ t("settings.model") }}
            <input v-model="settings.embedding.openai.model" />
          </label>
        </template>
        <template v-else>
          <label>
            {{ t("settings.baseUrl") }}
            <input v-model="settings.embedding.ollama.base_url" />
          </label>
          <label>
            {{ t("settings.model") }}
            <input v-model="settings.embedding.ollama.model" />
          </label>
        </template>
      </fieldset>

      <fieldset>
        <legend>{{ t("settings.llm") }}</legend>
        <label>
          {{ t("settings.provider") }}
          <select v-model="settings.llm.provider">
            <option value="openai">openai</option>
            <option value="ollama">ollama</option>
          </select>
        </label>
        <template v-if="settings.llm.provider === 'openai'">
          <label>
            {{ t("settings.apiKey") }}
            <input v-model="settings.llm.openai.api_key" type="password" autocomplete="off" />
          </label>
          <label>
            {{ t("settings.baseUrl") }}
            <input v-model="settings.llm.openai.base_url" />
          </label>
          <label>
            {{ t("settings.model") }}
            <input v-model="settings.llm.openai.model" />
          </label>
        </template>
        <template v-else>
          <label>
            {{ t("settings.baseUrl") }}
            <input v-model="settings.llm.ollama.base_url" />
          </label>
          <label>
            {{ t("settings.model") }}
            <input v-model="settings.llm.ollama.model" />
          </label>
        </template>
      </fieldset>

      <fieldset>
        <legend>{{ t("settings.splitter") }}</legend>
        <label>
          {{ t("settings.chunkSize") }}
          <input v-model.number="settings.splitter.chunk_size" type="number" min="1" />
        </label>
        <label>
          {{ t("settings.chunkOverlap") }}
          <input v-model.number="settings.splitter.chunk_overlap" type="number" min="0" />
        </label>
        <label>
          {{ t("settings.strategy") }}
          <input v-model="settings.splitter.strategy" />
        </label>
      </fieldset>

      <fieldset>
        <legend>{{ t("settings.basic") }}</legend>
        <label>
          {{ t("settings.defaultLocale") }}
          <select v-model="settings.i18n.default_locale">
            <option value="zh-CN">zh-CN</option>
            <option value="zh-TW">zh-TW</option>
            <option value="en-US">en-US</option>
          </select>
        </label>
        <label class="checkbox-row">
          <input v-model="settings.chat.enabled" type="checkbox" />
          {{ t("settings.chatEnabled") }}
        </label>
        <label class="checkbox-row">
          <input v-model="settings.debug.llm_logging" type="checkbox" />
          {{ t("settings.debugLogging") }}
        </label>
        <p v-if="settings.debug.llm_logging" class="hint">{{ t("settings.debugLoggingHint") }}</p>
      </fieldset>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="saved" class="success">{{ t("settings.saveRestarting") }}</p>
      <button type="submit" class="primary" :disabled="saving || saved">
        {{ saving ? t("common.loading") : t("common.save") }}
      </button>
    </form>
  </section>
</template>

<style scoped>
.hint {
  font-size: 0.85rem;
  opacity: 0.75;
  margin: 0 0 1rem;
}
.config-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  max-width: 560px;
}
fieldset {
  display: flex;
  flex-direction: column;
  gap: 0.85rem;
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.25rem 1.25rem;
}
legend {
  padding: 0 0.4rem;
  font-weight: 600;
  font-size: 0.9rem;
}
label {
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
}
.checkbox-row {
  flex-direction: row;
  align-items: center;
  gap: 0.5rem;
}
input,
select {
  padding: 0.5rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
}
button.primary {
  align-self: flex-start;
  padding: 0.5rem 1.25rem;
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
