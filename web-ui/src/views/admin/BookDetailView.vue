<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { getBook, type BookDetail } from "../../api/books";

const { t } = useI18n();
const route = useRoute();
const book = ref<BookDetail | null>(null);
const loading = ref(true);

async function load() {
  loading.value = true;
  try {
    book.value = await getBook(route.params.id as string);
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <router-link to="/books">&larr; {{ t("books.title") }}</router-link>

    <div v-if="loading">{{ t("common.loading") }}</div>
    <template v-else-if="book">
      <h1>{{ book.title || book.id }}</h1>
      <dl class="meta">
        <dt>{{ t("books.table.author") }}</dt>
        <dd>{{ book.author || "—" }}</dd>
        <dt>{{ t("books.table.format") }}</dt>
        <dd>{{ book.source_format }}</dd>
        <dt>{{ t("books.table.status") }}</dt>
        <dd><span :class="['badge', book.status]">{{ t(`status.${book.status}`, book.status) }}</span></dd>
      </dl>

      <h2>{{ t("books.chapters") }}</h2>
      <ol v-if="book.chapters.length" class="chapters">
        <li v-for="ch in book.chapters" :key="ch.id">{{ ch.title }}</li>
      </ol>
      <p v-else>{{ t("books.noChapters") }}</p>
    </template>
  </section>
</template>

<style scoped>
.meta {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 1rem;
  margin: 1rem 0;
  font-size: 0.9rem;
}
.meta dt {
  opacity: 0.7;
}
.chapters {
  padding-left: 1.25rem;
}
.chapters li {
  padding: 0.25rem 0;
}
.badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: var(--code-bg);
}
</style>
