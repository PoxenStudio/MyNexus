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

const { t } = useI18n();
const books = ref<Book[]>([]);
const loading = ref(true);
const uploading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);
const selected = ref<Set<string>>(new Set());
const bulkRunning = ref(false);
const bulkErrors = ref<string[]>([]);

const allSelected = computed(() => books.value.length > 0 && selected.value.size === books.value.length);
const someSelected = computed(() => selected.value.size > 0);

async function load() {
  loading.value = true;
  try {
    const res = await listBooks({ size: 100 });
    books.value = res.items;
    selected.value = new Set([...selected.value].filter((id) => books.value.some((b) => b.id === id)));
  } finally {
    loading.value = false;
  }
}

async function onFileSelected(e: Event) {
  const file = (e.target as HTMLInputElement).files?.[0];
  if (!file) return;
  uploading.value = true;
  try {
    await uploadBook(file);
    await load();
  } finally {
    uploading.value = false;
    if (fileInput.value) fileInput.value.value = "";
  }
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

    <div class="toolbar">
      <input ref="fileInput" type="file" accept=".epub,.txt" @change="onFileSelected" :disabled="uploading" />
      <span v-if="uploading">{{ t("common.loading") }}</span>
      <button class="ghost" @click="load">{{ t("common.refresh") }}</button>
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
    <table v-else-if="books.length">
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
    <p v-else>{{ t("common.empty") }}</p>
  </section>
</template>

<style scoped>
.toolbar {
  display: flex;
  align-items: center;
  gap: 1rem;
  margin: 1rem 0;
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
</style>
