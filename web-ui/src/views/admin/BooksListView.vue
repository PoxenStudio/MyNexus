<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import {
  bulkDeleteBooks,
  bulkRebuildBooks,
  deleteBook,
  listBooks,
  rebuildBook,
  uploadBook,
  type Book,
} from "../../api/books";
import { apiClient } from "../../api/client";
import { fetchSettings } from "../../api/system";
import MyBooksImportDialog from "../../components/MyBooksImportDialog.vue";

const { t } = useI18n();
const books = ref<Book[]>([]);
const loading = ref(true);
const uploading = ref(false);
const mybooksConfigured = ref(false);
const mybooksDialogOpen = ref(false);
const uploadProgress = ref<{ current: number; total: number } | null>(null);
const uploadErrors = ref<string[]>([]);
const fileInput = ref<HTMLInputElement | null>(null);
const selected = ref<Set<string>>(new Set());
const bulkRunning = ref(false);
const bulkErrors = ref<string[]>([]);

type ViewMode = "card" | "list";
const viewMode = ref<ViewMode>("card");

const allSelected = computed(() => books.value.length > 0 && selected.value.size === books.value.length);
const someSelected = computed(() => selected.value.size > 0);
const dragOver = ref(false);

function coverUrl(b: Book) {
  if (!b.cover_url) return "";
  return apiClient.defaults.baseURL + b.cover_url;
}

function coverFallback(b: Book) {
  return (b.title || b.id || "?").charAt(0).toUpperCase();
}

async function load() {
  loading.value = true;
  try {
    const res = await listBooks({ size: 100 });
    books.value = res.items;
    selected.value = new Set([...selected.value].filter((id) => books.value.some((b) => b.id === id)));
    try {
      const s = await fetchSettings();
      mybooksConfigured.value = !!(s.mybooks?.base_url?.trim());
    } catch {
      /* ignore */
    }
  } finally {
    loading.value = false;
  }
}

async function onFileSelected(e: Event) {
  const files = (e.target as HTMLInputElement).files;
  if (files?.length) await doUploadMany([...files]);
  if (fileInput.value) fileInput.value.value = "";
}

async function doUploadMany(files: File[]) {
  uploading.value = true;
  uploadErrors.value = [];
  try {
    for (let i = 0; i < files.length; i++) {
      uploadProgress.value = { current: i + 1, total: files.length };
      try {
        await uploadBook(files[i]);
      } catch (e: any) {
        uploadErrors.value.push(`${files[i].name}: ${e?.response?.data?.error || e.message}`);
      }
    }
    await load();
  } finally {
    uploading.value = false;
    uploadProgress.value = null;
  }
}

function onDrop(e: DragEvent) {
  dragOver.value = false;
  const files = e.dataTransfer?.files;
  if (files?.length) doUploadMany([...files]);
}

async function onDelete(id: string) {
  if (!confirm(t("common.confirmDelete"))) return;
  await deleteBook(id);
  await load();
}

async function onRebuild(id: string) {
  await rebuildBook(id);
  await load();
}

function toggleAll() {
  selected.value = allSelected.value ? new Set() : new Set(books.value.map((b) => b.id));
}

function toggleOne(id: string) {
  const next = new Set(selected.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  selected.value = next;
}

async function onBulkDelete() {
  if (!confirm(t("books.confirmBulkDelete", { count: selected.value.size }))) return;
  bulkRunning.value = true;
  bulkErrors.value = [];
  try {
    const results = await bulkDeleteBooks([...selected.value]);
    bulkErrors.value = results.filter((r) => !r.ok).map((r) => `${r.id}: ${r.error}`);
    selected.value = new Set();
    await load();
  } finally {
    bulkRunning.value = false;
  }
}

async function onBulkRebuild() {
  if (!confirm(t("books.confirmBulkRebuild", { count: selected.value.size }))) return;
  bulkRunning.value = true;
  bulkErrors.value = [];
  try {
    const results = await bulkRebuildBooks([...selected.value]);
    bulkErrors.value = results.filter((r) => !r.ok).map((r) => `${r.id}: ${r.error}`);
    selected.value = new Set();
    await load();
  } finally {
    bulkRunning.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <h1>{{ t("books.title") }}</h1>

    <div class="upload-cards">
      <label
        class="upload-card"
        :class="{ dragover: dragOver, uploading }"
        @dragover.prevent="dragOver = true"
        @dragleave.prevent="dragOver = false"
        @drop.prevent="onDrop"
      >
        <input
          ref="fileInput"
          type="file"
          accept=".epub,.pdf,.txt"
          multiple
          class="upload-input"
          :disabled="uploading"
          @change="onFileSelected"
        />
        <span class="upload-icon">📤</span>
        <span class="upload-title">{{ t("books.upload") }}</span>
        <span class="upload-hint">
          {{ uploadProgress ? t("books.uploadProgress", uploadProgress) : t("books.uploadHint") }}
        </span>
      </label>

      <button
        v-if="mybooksConfigured"
        type="button"
        class="upload-card mybooks-card"
        @click="mybooksDialogOpen = true"
      >
        <span class="upload-icon">📚</span>
        <span class="upload-title">{{ t("books.importFromMyBooks") }}</span>
        <span class="upload-hint">{{ t("books.importFromMyBooksHint") }}</span>
      </button>
    </div>
    <ul v-if="uploadErrors.length" class="bulk-errors">
      <li v-for="(err, i) in uploadErrors" :key="i">{{ err }}</li>
    </ul>

    <div class="toolbar">
      <button class="ghost" @click="load">{{ t("common.refresh") }}</button>
      <div class="view-toggle" role="tablist" aria-label="view mode">
        <button
          type="button"
          :class="['ghost', 'toggle-btn', { active: viewMode === 'card' }]"
          @click="viewMode = 'card'"
          :title="t('common.viewCard')"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <rect x="1" y="1" width="6" height="6" rx="1" />
            <rect x="9" y="1" width="6" height="6" rx="1" />
            <rect x="1" y="9" width="6" height="6" rx="1" />
            <rect x="9" y="9" width="6" height="6" rx="1" />
          </svg>
        </button>
        <button
          type="button"
          :class="['ghost', 'toggle-btn', { active: viewMode === 'list' }]"
          @click="viewMode = 'list'"
          :title="t('common.viewList')"
        >
          <svg width="16" height="16" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
            <rect x="1" y="2" width="14" height="2" rx="0.5" />
            <rect x="1" y="7" width="14" height="2" rx="0.5" />
            <rect x="1" y="12" width="14" height="2" rx="0.5" />
          </svg>
        </button>
      </div>
    </div>

    <div v-if="someSelected" class="bulk-bar">
      <span>{{ t("books.selectedCount", { count: selected.size }) }}</span>
      <button class="ghost" :disabled="bulkRunning" @click="onBulkRebuild">{{ t("books.bulkRebuild") }}</button>
      <button class="ghost danger" :disabled="bulkRunning" @click="onBulkDelete">{{ t("books.bulkDelete") }}</button>
    </div>
    <ul v-if="bulkErrors.length" class="bulk-errors">
      <li v-for="(err, i) in bulkErrors" :key="i">{{ err }}</li>
    </ul>

    <div v-if="loading">{{ t("common.loading") }}</div>

    <template v-else-if="books.length">
      <!-- CARD VIEW -->
      <div v-if="viewMode === 'card'" class="book-grid">
        <div
          v-for="b in books"
          :key="b.id"
          :class="['book-card', { selected: selected.has(b.id) }]"
        >
          <label class="card-checkbox">
            <input type="checkbox" :checked="selected.has(b.id)" @change="toggleOne(b.id)" />
          </label>
          <router-link :to="`/books/${b.id}`" class="card-cover-wrap">
            <img v-if="coverUrl(b)" :src="coverUrl(b)" :alt="b.title" class="card-cover" loading="lazy" />
            <div v-else class="card-cover card-cover-fallback">{{ coverFallback(b) }}</div>
            <span :class="['card-status', b.status]">{{ t(`status.${b.status}`, b.status) }}</span>
          </router-link>
          <div class="card-body">
            <router-link :to="`/books/${b.id}`" class="card-title" :title="b.title">
              {{ b.title || b.id }}
            </router-link>
            <div v-if="b.author" class="card-author" :title="b.author">{{ b.author }}</div>
          </div>
        </div>
      </div>

      <!-- LIST VIEW -->
      <table v-else>
        <thead>
          <tr>
            <th><input type="checkbox" :checked="allSelected" @change="toggleAll" /></th>
            <th>{{ t("books.table.title") }}</th>
            <th>{{ t("books.table.author") }}</th>
            <th>{{ t("books.table.format") }}</th>
            <th>{{ t("books.table.status") }}</th>
            <th>{{ t("books.table.updatedAt") }}</th>
            <th>{{ t("books.table.actions") }}</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="b in books" :key="b.id">
            <td><input type="checkbox" :checked="selected.has(b.id)" @change="toggleOne(b.id)" /></td>
            <td><router-link :to="`/books/${b.id}`">{{ b.title || b.id }}</router-link></td>
            <td>{{ b.author }}</td>
            <td>{{ b.source_format }}</td>
            <td><span :class="['badge', b.status]">{{ t(`status.${b.status}`, b.status) }}</span></td>
            <td>{{ new Date(b.updated_at).toLocaleString() }}</td>
            <td class="actions">
              <button class="ghost" @click="onRebuild(b.id)">{{ t("books.rebuild") }}</button>
              <button class="ghost" @click="onDelete(b.id)">{{ t("common.delete") }}</button>
            </td>
          </tr>
        </tbody>
      </table>
    </template>
    <p v-else>{{ t("common.empty") }}</p>

    <MyBooksImportDialog v-model="mybooksDialogOpen" @imported="load" />
  </section>
</template>

<style scoped>
.upload-cards {
  display: flex;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.upload-cards .upload-card {
  flex: 1 1 240px;
  margin: 1rem 0;
}
.mybooks-card {
  border-style: solid !important;
  border-color: var(--primary, #3b82f6) !important;
  border-width: 1.5px;
}
.mybooks-card:hover {
  background: var(--accent-bg);
  border-color: var(--primary, #3b82f6);
}
.upload-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.35rem;
  margin: 1rem 0;
  padding: 1.5rem;
  border: 1.5px dashed var(--border);
  border-radius: 12px;
  background: var(--surface, transparent);
  text-align: center;
  cursor: pointer;
  transition:
    border-color 0.15s ease,
    background-color 0.15s ease;
}
.upload-card:hover,
.upload-card.dragover {
  border-color: var(--accent-border);
  background: var(--accent-bg);
}
.upload-card.uploading {
  opacity: 0.7;
  cursor: default;
  pointer-events: none;
}
.upload-input {
  position: absolute;
  width: 1px;
  height: 1px;
  overflow: hidden;
  opacity: 0;
}
.upload-icon {
  font-size: 1.75rem;
  line-height: 1;
}
.upload-title {
  font-weight: 600;
  color: var(--text-h);
}
.upload-hint {
  font-size: 0.8rem;
  opacity: 0.7;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin: 0 0 0.75rem;
}
.view-toggle {
  display: inline-flex;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}
.toggle-btn {
  border: none !important;
  border-radius: 0 !important;
  border-right: 1px solid var(--border) !important;
  padding: 0.3rem 0.5rem !important;
  background: transparent;
  cursor: pointer;
  display: flex;
  align-items: center;
  color: inherit;
}
.toggle-btn:last-child {
  border-right: none !important;
}
.toggle-btn.active {
  background: var(--accent-bg);
  color: var(--primary, #3b82f6);
}
.bulk-bar {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.5rem 0.75rem;
  margin-bottom: 0.75rem;
  background: var(--accent-bg);
  border-radius: 8px;
  font-size: 0.9rem;
}
.bulk-errors {
  margin: 0 0 0.75rem;
  padding-left: 1.25rem;
  color: #dc2626;
  font-size: 0.85rem;
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
.badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: var(--code-bg);
}
.badge.ready, .badge.completed { color: #16a34a; }
.badge.failed { color: #dc2626; }
.badge.pending, .badge.processing { color: #d97706; }
.actions {
  display: flex;
  gap: 0.4rem;
}
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
}
button.ghost.danger {
  color: #dc2626;
  border-color: #dc2626;
}
button.ghost:disabled {
  opacity: 0.5;
  cursor: default;
}

/* CARD VIEW */
.book-grid {
  display: grid;
  gap: 1.25rem 1rem;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
}
.book-card {
  position: relative;
  border-radius: 10px;
  overflow: hidden;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.book-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 18px rgba(0, 0, 0, 0.12);
}
.book-card.selected {
  outline: 2px solid var(--primary, #3b82f6);
  outline-offset: -2px;
}
.card-checkbox {
  position: absolute;
  top: 6px;
  left: 6px;
  z-index: 2;
  background: rgba(255, 255, 255, 0.85);
  border-radius: 4px;
  padding: 2px 4px;
  display: flex;
  cursor: pointer;
}
.card-cover-wrap {
  display: block;
  aspect-ratio: 2 / 3;
  overflow: hidden;
  border-radius: 10px;
  background: #e5e7eb;
  position: relative;
}
.card-cover {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}
.card-cover-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 3rem;
  font-weight: 700;
  color: #fff;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.card-status {
  position: absolute;
  bottom: 6px;
  right: 6px;
  padding: 2px 8px;
  border-radius: 999px;
  font-size: 0.7rem;
  font-weight: 500;
  background: rgba(0, 0, 0, 0.55);
  color: #fff;
  backdrop-filter: blur(2px);
}
.card-status.ready, .card-status.completed { background: rgba(22, 163, 74, 0.85); }
.card-status.failed { background: rgba(220, 38, 38, 0.85); }
.card-status.pending, .card-status.processing { background: rgba(217, 119, 6, 0.85); }
.card-body {
  padding: 0.5rem 0.2rem 0.1rem;
}
.card-title {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-decoration: none;
  color: var(--text-h);
  font-weight: 500;
  font-size: 0.9rem;
  line-height: 1.35;
  min-height: 2.7em;
}
.card-title:hover {
  color: var(--primary, #3b82f6);
}
.card-author {
  margin-top: 0.15rem;
  font-size: 0.78rem;
  color: var(--text-h, inherit);
  opacity: 0.6;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
