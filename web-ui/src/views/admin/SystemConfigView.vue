<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  fetchSettings,
  saveSettings,
  testProvider,
  type SystemSettings,
} from "../../api/system";
import { testMyBooksConnection } from "../../api/mybooks";

const { t } = useI18n();

const settings = ref<SystemSettings | null>(null);
const loading = ref(true);
const saving = ref(false);
const saved = ref(false);
const error = ref("");

const tabs = [
  { key: "storage", label: "settings.tabs.storage" },
  { key: "worker", label: "settings.tabs.worker" },
  { key: "embedding", label: "settings.tabs.embedding" },
  { key: "llm", label: "settings.tabs.llm" },
  { key: "retrieval", label: "settings.tabs.retrieval" },
  { key: "splitter", label: "settings.tabs.splitter" },
  { key: "basic", label: "settings.tabs.basic" },
  { key: "connection", label: "settings.tabs.connection" },
] as const;
type TabKey = (typeof tabs)[number]["key"];
const activeTab = ref<TabKey>("storage");
const tabIndex = computed(() => Math.max(0, tabs.findIndex((tb) => tb.key === activeTab.value)));
const tabStripStyle = computed(() => ({
  "--tab-index": String(tabIndex.value),
  "--tab-count": String(tabs.length),
}));

const originalEmbedding = ref<{ provider: string; openai_model: string; ollama_model: string; local_model: string; local_model_path: string } | null>(null);
const embeddingChanged = computed(() => {
  if (!settings.value || !originalEmbedding.value) return false;
  const e = settings.value.embedding;
  return (
    e.provider !== originalEmbedding.value.provider ||
    e.openai.model !== originalEmbedding.value.openai_model ||
    e.ollama.model !== originalEmbedding.value.ollama_model ||
    e.local.model !== originalEmbedding.value.local_model ||
    e.local.model_path !== originalEmbedding.value.local_model_path
  );
});

const testing = ref<"embedding" | "llm" | "mybooks" | null>(null);
const testResult = ref<{ target: "embedding" | "llm" | "mybooks"; ok: boolean; message: string } | null>(null);

async function load() {
  loading.value = true;
  try {
    settings.value = await fetchSettings();
    const e = settings.value.embedding;
    originalEmbedding.value = {
      provider: e.provider,
      openai_model: e.openai.model,
      ollama_model: e.ollama.model,
      local_model: e.local.model,
      local_model_path: e.local.model_path,
    };
  } finally {
    loading.value = false;
  }
}

async function runTest(target: "embedding" | "llm") {
  if (!settings.value) return;
  const s = settings.value[target];
  testing.value = target;
  testResult.value = null;
  try {
    const r = await testProvider({
      provider: target,
      kind: s.provider as "openai" | "ollama",
      base_url: s[s.provider as "openai" | "ollama"].base_url,
      api_key: s[s.provider as "openai" | "ollama"].api_key,
      model: s[s.provider as "openai" | "ollama"].model,
    });
    testResult.value = { target, ok: r.ok, message: r.ok ? t("settings.testOk") : r.error || t("settings.testFail") };
  } catch (e: any) {
    testResult.value = { target, ok: false, message: e?.response?.data?.error || t("settings.testFail") };
  } finally {
    testing.value = null;
  }
}

async function runMyBooksTest() {
  if (!settings.value) return;
  const mb = settings.value.mybooks;
  testing.value = "mybooks";
  testResult.value = null;
  try {
    const r = await testMyBooksConnection(mb);
    testResult.value = { target: "mybooks", ok: r.ok, message: r.ok ? t("settings.testOk") : r.error || t("settings.testFail") };
  } catch (e: any) {
    testResult.value = { target: "mybooks", ok: false, message: e?.response?.data?.error || t("settings.testFail") };
  } finally {
    testing.value = null;
  }
}

async function onSave() {
  if (!settings.value) return;
  error.value = "";
  saving.value = true;
  try {
    await saveSettings(settings.value);
    saved.value = true;
    // Worker restarts to pick up the new config (see backend handler) —
    // core-api stays up, so the current session keeps working. No logout
    // needed; the saved flag just shows a success chip.
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
    <template v-else-if="settings">
      <div class="tab-container" role="tablist" :style="tabStripStyle">
        <button
          v-for="tb in tabs"
          :key="tb.key"
          type="button"
          class="tab-label"
          :class="{ active: activeTab === tb.key }"
          role="tab"
          :aria-selected="activeTab === tb.key"
          @click="activeTab = tb.key"
        >
          {{ t(tb.label) }}
        </button>
        <span class="indicator" aria-hidden="true"></span>
      </div>

      <form class="config-form" @submit.prevent="onSave">
        <p class="hint">{{ t("settings.restartHint") }}</p>

      <fieldset v-show="activeTab === 'storage'">
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

      <fieldset v-show="activeTab === 'worker'">
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

      <fieldset v-show="activeTab === 'embedding'">
        <legend>{{ t("settings.embedding") }}</legend>
        <label>
          {{ t("settings.provider") }}
          <select v-model="settings.embedding.provider">
            <option value="local">local</option>
            <option value="openai">openai</option>
            <option value="ollama">ollama</option>
          </select>
        </label>
        <template v-if="settings.embedding.provider === 'local'">
          <label>
            {{ t("settings.localModel") }}
            <select v-model="settings.embedding.local.model">
              <option value="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2">multilingual-MiniLM-L12-v2 (~220MB)</option>
              <option value="BAAI/bge-small-zh-v1.5">bge-small-zh-v1.5 (~90MB)</option>
              <option value="sentence-transformers/all-MiniLM-L6-v2">all-MiniLM-L6-v2 (~90MB)</option>
            </select>
          </label>
          <p class="hint">{{ t("settings.localModelHint") }}</p>
          <label>
            {{ t("settings.localModelPath") }}
            <input v-model="settings.embedding.local.model_path" :placeholder="t('settings.localModelPathPlaceholder')" />
          </label>
          <p class="hint">{{ t("settings.localModelPathHint") }}</p>
        </template>
        <template v-else-if="settings.embedding.provider === 'openai'">
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
        <div v-if="settings.embedding.provider !== 'local'" class="test-row">
          <button type="button" :disabled="testing === 'embedding'" @click="runTest('embedding')">
            {{ testing === "embedding" ? t("common.loading") : t("settings.testConnection") }}
          </button>
          <span v-if="testResult?.target === 'embedding'" :class="testResult.ok ? 'success' : 'error'">
            {{ testResult.message }}
          </span>
        </div>
        <p v-else class="hint">{{ t("settings.localNoTest") }}</p>
        <p v-if="embeddingChanged" class="hint warn">{{ t("settings.embeddingChangedHint") }}</p>
      </fieldset>

      <fieldset v-show="activeTab === 'llm'">
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
          <label>
            {{ t("settings.chapterTokenBudget") }}
            <input
              v-model.number="settings.llm.openai.chapter_token_budget"
              type="number"
              min="2000"
              max="50000"
              step="1000"
            />
          </label>
          <p class="hint">{{ t("settings.chapterTokenBudgetHint") }}</p>
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
        <div class="test-row">
          <button type="button" :disabled="testing === 'llm'" @click="runTest('llm')">
            {{ testing === "llm" ? t("common.loading") : t("settings.testConnection") }}
          </button>
          <span v-if="testResult?.target === 'llm'" :class="testResult.ok ? 'success' : 'error'">
            {{ testResult.message }}
          </span>
        </div>
      </fieldset>

      <fieldset v-show="activeTab === 'retrieval'">
        <legend>{{ t("settings.retrieval") }}</legend>
        <label>
          {{ t("settings.retrievalFusion") }}
          <select v-model="settings.retrieval.fusion">
            <option value="weighted">{{ t("settings.fusionWeighted") }}</option>
            <option value="rrf">RRF</option>
          </select>
        </label>
        <p class="hint">{{ t("settings.retrievalFusionHint") }}</p>
        <label>
          {{ t("settings.vectorWeight") }}
          <input v-model.number="settings.retrieval.vector_weight" type="number" min="0" max="1" step="0.1" />
        </label>
        <label>
          {{ t("settings.keywordWeight") }}
          <input v-model.number="settings.retrieval.keyword_weight" type="number" min="0" max="1" step="0.1" />
        </label>
        <p class="hint">{{ t("settings.retrievalWeightsHint") }}</p>
      </fieldset>

      <fieldset v-show="activeTab === 'splitter'">
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

      <fieldset v-show="activeTab === 'basic'">
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
        <label>
          {{ t("settings.maxSessions") }}
          <input v-model.number="settings.chat.max_sessions" type="number" min="1" max="1000" />
        </label>
        <p class="hint">{{ t("settings.maxSessionsHint") }}</p>
        <label>
          {{ t("settings.slidingWindowSize") }}
          <input v-model.number="settings.chat.sliding_window_size" type="number" min="0" max="100" />
        </label>
        <p class="hint">{{ t("settings.slidingWindowSizeHint") }}</p>
        <label>
          {{ t("settings.maxKeywords") }}
          <input v-model.number="settings.keyword.max_keywords" type="number" min="1" max="500" />
        </label>
        <p class="hint">{{ t("settings.maxKeywordsHint") }}</p>
        <label class="checkbox-row">
          <input v-model="settings.summary.skip_backmatter_chapters" type="checkbox" />
          {{ t("settings.skipBackmatterChapters") }}
        </label>
        <label class="checkbox-row">
          <input v-model="settings.debug.llm_logging" type="checkbox" />
          {{ t("settings.debugLogging") }}
        </label>
        <p v-if="settings.debug.llm_logging" class="hint">{{ t("settings.debugLoggingHint") }}</p>
      </fieldset>

      <fieldset v-show="activeTab === 'connection'">
        <legend>{{ t("settings.mybooks") }}</legend>
        <label>
          {{ t("settings.mybooksBaseUrl") }}
          <input v-model="settings.mybooks.base_url" placeholder="http://your.mybooks:8081" />
        </label>
        <p class="hint">{{ t("settings.mybooksBaseUrlHint") }}</p>
        <label>
          {{ t("settings.mybooksUsername") }}
          <input v-model="settings.mybooks.username" />
        </label>
        <label>
          {{ t("settings.mybooksPassword") }}
          <input v-model="settings.mybooks.password" type="password" autocomplete="off" />
        </label>
        <div class="test-row">
          <button type="button" :disabled="testing === 'mybooks'" @click="runMyBooksTest">
            {{ testing === "mybooks" ? t("common.loading") : t("settings.testConnection") }}
          </button>
          <span v-if="testResult?.target === 'mybooks'" :class="testResult.ok ? 'success' : 'error'">
            {{ testResult.message }}
          </span>
        </div>
      </fieldset>

      <p v-if="error" class="error">{{ error }}</p>
      <p v-if="saved" class="success">{{ t("settings.saveRestarting") }}</p>
      <button type="submit" class="primary" :disabled="saving || saved">
        {{ saving ? t("common.loading") : t("common.save") }}
      </button>
      </form>
    </template>
  </section>
</template>

<style scoped>
.hint {
  font-size: 0.85rem;
  opacity: 0.75;
  margin: 0 0 1rem;
}
.tab-container {
  position: relative;
  display: flex;
  width: 700px;
  max-width: 100%;
  padding: 2px;
  border-radius: 9px;
  background-color: color-mix(in srgb, var(--text) 10%, transparent);
}
.tab-label {
  flex: 1 1 0;
  min-width: 0;
  position: relative;
  z-index: 2;
  height: 30px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 0.4rem;
  border: 0;
  background: transparent;
  color: inherit;
  font: inherit;
  font-size: 0.78rem;
  white-space: nowrap;
  opacity: 0.6;
  cursor: pointer;
  transition: opacity 0.18s ease;
}
.tab-label.active {
  opacity: 1;
}
.tab-label::after {
  content: "";
  position: absolute;
  left: 50%;
  bottom: 3px;
  transform: translateX(-50%);
  width: 56%;
  height: 3px;
  border-radius: 2px;
  background: #2563eb;
  opacity: 0.25;
  transition: opacity 0.18s ease;
}
.tab-label.active::after {
  opacity: 1;
}
.indicator {
  position: absolute;
  top: 2px;
  left: calc(2px + (100% - 4px) / var(--tab-count) * var(--tab-index));
  z-index: 1;
  width: calc((100% - 4px) / var(--tab-count));
  height: 30px;
  border: 0.5px solid rgba(0, 0, 0, 0.04);
  border-radius: 7px;
  background: var(--surface, #fff);
  box-shadow: 0 3px 8px rgba(0, 0, 0, 0.12), 0 3px 1px rgba(0, 0, 0, 0.04);
  transition: left 0.2s ease-out;
}
.config-form {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
  width: 700px;
  max-width: 100%;
  margin-top: 1.25rem;
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
.test-row {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}
.test-row button {
  padding: 0.35rem 0.9rem;
  border-radius: 6px;
  border: 1px solid var(--border);
  background: transparent;
  color: inherit;
  cursor: pointer;
  font: inherit;
  font-size: 0.85rem;
}
.test-row button:disabled {
  opacity: 0.6;
  cursor: default;
}
.test-row span {
  font-size: 0.85rem;
}
.hint.warn {
  color: #b8860b;
  opacity: 1;
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
