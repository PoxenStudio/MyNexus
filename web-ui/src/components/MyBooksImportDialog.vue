<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import AppDialog from "./AppDialog.vue";
import { searchMyBooks, importFromMyBooks, type MyBooksSearchItem } from "../api/mybooks";

const props = withDefaults(defineProps<{ modelValue: boolean }>(), {});
const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "imported"): void;
}>();

const { t } = useI18n();
const query = ref("");
const books = ref<MyBooksSearchItem[]>([]);
const total = ref(0);
const start = ref(0);
const size = 20;
const loading = ref(false);
const err = ref("");
const importingId = ref<number | null>(null);
const importedOk = ref(false);

watch(() => props.modelValue, (v) => {
  if (v) {
    query.value = "";
    books.value = [];
    total.value = 0;
    start.value = 0;
    err.value = "";
    importedOk.value = false;
  }
});

async function doSearch() {
  const q = query.value.trim();
  if (!q) return;
  loading.value = true;
  err.value = "";
  try {
    const resp = await searchMyBooks(q, start.value, size);
    books.value = resp.books;
    total.value = resp.total;
  } catch (e: any) {
    err.value = e?.response?.data?.error || e.message;
    books.value = [];
    total.value = 0;
  } finally {
    loading.value = false;
  }
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Enter") {
    start.value = 0;
    doSearch();
  }
}

const pageCount = computed(() => Math.max(1, Math.ceil(total.value / size)));
const currentPage = computed(() => Math.floor(start.value / size) + 1);

function prevPage() {
  if (start.value >= size) {
    start.value -= size;
    doSearch();
  }
}
function nextPage() {
  if (start.value + size < total.value) {
    start.value += size;
    doSearch();
  }
}

function hasFormat(item: MyBooksSearchItem, fmt: string) {
  return item.files.some((f) => f.format.toLowerCase() === fmt.toLowerCase());
}

function pickFormat(item: MyBooksSearchItem) {
  if (hasFormat(item, "epub")) return "epub";
  if (hasFormat(item, "txt")) return "txt";
  return "";
}

function supportedFormats(item: MyBooksSearchItem) {
  return item.files.filter((f) => f.format.toLowerCase() === "epub" || f.format.toLowerCase() === "txt");
}

async function doImport(item: MyBooksSearchItem) {
  const fmt = pickFormat(item);
  if (!fmt) return;
  importingId.value = item.id;
  err.value = "";
  importedOk.value = false;
  try {
    await importFromMyBooks(item.id, fmt, item.thumb || undefined);
    importedOk.value = true;
    setTimeout(() => {
      emit("imported");
      emit("update:modelValue", false);
    }, 800);
  } catch (e: any) {
    err.value = e?.response?.data?.error || e.message;
  } finally {
    importingId.value = null;
  }
}

function close() {
  emit("update:modelValue", false);
}
</script>

<template>
  <AppDialog :model-value="modelValue" :title="t('books.mybooksDialogTitle')" class="mb-dialog" @update:model-value="close">
    <div class="mb-search">
      <input
        v-model="query"
        class="mb-search-input"
        :placeholder="t('books.mybooksSearchPlaceholder')"
        :disabled="loading"
        @keydown="onKeydown"
      />
      <button class="mb-search-btn" :disabled="loading || !query.trim()" @click="doSearch">
        {{ loading ? t("common.loading") : t("books.mybooksSearchButton") }}
      </button>
    </div>

    <div v-if="err" class="mb-err">{{ err }}</div>
    <div v-if="importedOk" class="mb-ok">{{ t("books.mybooksImportedOk") }}</div>

    <div v-if="loading" class="mb-loading">{{ t("common.loading") }}</div>

    <div v-else-if="books.length" class="mb-list">
      <div v-for="item in books" :key="item.id" class="mb-book">
        <div class="mb-cover-wrap">
          <img
            v-if="item.thumb"
            :src="item.thumb"
            :alt="item.title"
            referrerpolicy="no-referrer"
            class="mb-cover"
          />
          <div v-else class="mb-cover mb-cover-placeholder">{{ item.title?.[0] || "?" }}</div>
        </div>
        <div class="mb-meta">
          <div class="mb-title" :title="item.title">{{ item.title }}</div>
          <div class="mb-author">{{ (item.authors && item.authors.join(", ")) || item.author }}</div>
          <div v-if="item.publisher" class="mb-sub">{{ item.publisher }}</div>
          <div class="mb-formats">
            <span
              v-for="f in supportedFormats(item)"
              :key="f.format"
              class="mb-chip"
            >{{ f.format.toUpperCase() }}</span>
            <span v-if="!supportedFormats(item).length" class="mb-sub mb-nofmt">
              {{ t("books.mybooksNoSupportedFormat") }}
            </span>
          </div>
        </div>
        <div class="mb-actions">
          <button
            :disabled="!pickFormat(item) || importingId === item.id || importedOk"
            :class="{ 'mb-btn-loading': importingId === item.id }"
            @click="doImport(item)"
          >
            {{ importingId === item.id ? t("books.mybooksImporting") : t("books.mybooksImportButton", { format: pickFormat(item).toUpperCase() }) }}
          </button>
        </div>
      </div>
    </div>

    <div v-else-if="query.trim()" class="mb-empty">{{ t("books.mybooksNoResult") }}</div>

    <div v-if="books.length && total > size" class="mb-pager">
      <button :disabled="currentPage <= 1 || loading" @click="prevPage">‹</button>
      <span>{{ currentPage }} / {{ pageCount }}</span>
      <button :disabled="currentPage >= pageCount || loading" @click="nextPage">›</button>
      <span class="mb-total">共 {{ total }} 本</span>
    </div>
  </AppDialog>
</template>

<style scoped>
.mb-dialog {
  max-width: 640px !important;
}
.mb-search {
  display: flex;
  gap: 0.5rem;
  margin-bottom: 0.75rem;
}
.mb-search-input {
  flex: 1;
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
  color: var(--text);
  font-size: 0.9rem;
}
.mb-search-input:focus {
  outline: none;
  border-color: var(--primary, #3b82f6);
}
.mb-search-btn {
  padding: 0.5rem 1rem;
  border: none;
  border-radius: 6px;
  background: var(--primary, #3b82f6);
  color: #fff;
  cursor: pointer;
  font-size: 0.85rem;
}
.mb-search-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.mb-loading {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted, #888);
}
.mb-err {
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
  background: #fef2f2;
  border: 1px solid #fecaca;
  color: #b91c1c;
  border-radius: 6px;
  font-size: 0.8rem;
}
.mb-ok {
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.5rem;
  background: #f0fdf4;
  border: 1px solid #bbf7d0;
  color: #15803d;
  border-radius: 6px;
  font-size: 0.8rem;
}
.mb-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  max-height: 50vh;
  overflow-y: auto;
}
.mb-book {
  display: flex;
  gap: 0.75rem;
  padding: 0.6rem;
  border: 1px solid var(--border);
  border-radius: 8px;
  background: var(--surface, #fafafa);
}
.mb-cover-wrap {
  flex-shrink: 0;
}
.mb-cover {
  width: 56px;
  height: 76px;
  object-fit: cover;
  border-radius: 4px;
  background: #e5e7eb;
  display: block;
}
.mb-cover-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 1.5rem;
  font-weight: 600;
}
.mb-meta {
  flex: 1;
  min-width: 0;
}
.mb-title {
  font-weight: 600;
  font-size: 0.92rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.mb-author {
  font-size: 0.8rem;
  color: var(--text-muted, #6b7280);
  margin-top: 2px;
}
.mb-sub {
  font-size: 0.75rem;
  color: var(--text-muted, #9ca3af);
  margin-top: 2px;
}
.mb-nofmt {
  color: #b91c1c;
}
.mb-formats {
  display: flex;
  gap: 0.25rem;
  margin-top: 4px;
  flex-wrap: wrap;
}
.mb-chip {
  font-size: 0.7rem;
  padding: 1px 6px;
  border-radius: 10px;
  background: var(--primary, #3b82f6);
  color: #fff;
}
.mb-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
}
.mb-actions button {
  padding: 0.35rem 0.75rem;
  border: 1px solid var(--primary, #3b82f6);
  background: transparent;
  color: var(--primary, #3b82f6);
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.8rem;
}
.mb-actions button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.mb-btn-loading {
  opacity: 0.7;
}
.mb-empty {
  text-align: center;
  padding: 2rem;
  color: var(--text-muted, #888);
  font-size: 0.85rem;
}
.mb-pager {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding-top: 0.75rem;
  margin-top: 0.5rem;
  border-top: 1px solid var(--border);
  font-size: 0.85rem;
}
.mb-pager button {
  width: 28px;
  height: 28px;
  border: 1px solid var(--border);
  background: var(--bg);
  color: var(--text);
  border-radius: 4px;
  cursor: pointer;
  font-size: 1rem;
}
.mb-pager button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
.mb-total {
  color: var(--text-muted, #888);
  font-size: 0.8rem;
}
</style>
