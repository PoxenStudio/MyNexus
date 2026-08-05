<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { deleteBook, listBooks, uploadBook, type Book } from "../../api/books";

const { t } = useI18n();
const books = ref<Book[]>([]);
const loading = ref(true);
const uploading = ref(false);
const fileInput = ref<HTMLInputElement | null>(null);

async function load() {
  loading.value = true;
  try {
    const res = await listBooks({ size: 100 });
    books.value = res.items;
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

    <div v-if="loading">{{ t("common.loading") }}</div>
    <table v-else-if="books.length">
      <thead>
        <tr>
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
          <td><router-link :to="`/books/${b.id}`">{{ b.title || b.id }}</router-link></td>
          <td>{{ b.author }}</td>
          <td>{{ b.source_format }}</td>
          <td><span :class="['badge', b.status]">{{ t(`status.${b.status}`, b.status) }}</span></td>
          <td>{{ new Date(b.updated_at).toLocaleString() }}</td>
          <td><button class="ghost" @click="onDelete(b.id)">{{ t("common.delete") }}</button></td>
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
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
}
</style>
