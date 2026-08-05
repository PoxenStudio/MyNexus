<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { getBook, summarizeBook, type BookDetail } from "../../api/books";
import { getTask, type Task } from "../../api/tasks";

const { t } = useI18n();
const route = useRoute();
const book = ref<BookDetail | null>(null);
const loading = ref(true);

const summarizing = ref(false);
const summarizeTask = ref<Task | null>(null);
const summarizeError = ref("");
let pollTimer: ReturnType<typeof setInterval> | null = null;

async function load() {
  loading.value = true;
  try {
    book.value = await getBook(route.params.id as string);
  } finally {
    loading.value = false;
  }
}

async function onSummarize() {
  if (!book.value) return;
  summarizeError.value = "";
  summarizing.value = true;
  try {
    const { task_id } = await summarizeBook(book.value.id);
    pollTimer = setInterval(() => pollSummarize(task_id), 2000);
    await pollSummarize(task_id);
  } catch (e: any) {
    summarizing.value = false;
    summarizeError.value = e?.response?.data?.error || t("books.summarizeError");
  }
}

async function pollSummarize(taskId: string) {
  const task = await getTask(taskId);
  summarizeTask.value = task;
  // Reload the book on every tick too — chapter summaries land one at a time
  // (the map step) well before the task itself completes (the reduce step),
  // so this is what makes each chapter's summary appear as it's ready.
  book.value = await getBook(route.params.id as string);

  if (task.status === "completed" || task.status === "failed") {
    stopPolling();
    summarizing.value = false;
    if (task.status === "failed") summarizeError.value = task.error_msg || t("books.summarizeError");
  }
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
}

onMounted(load);
onUnmounted(stopPolling);
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

      <div class="summary-section">
        <div class="summary-header">
          <h2>{{ t("books.bookSummary") }}</h2>
          <button
            class="ghost"
            :disabled="summarizing || !book.chapters.length"
            :title="!book.chapters.length ? t('books.noChaptersToSummarize') : undefined"
            @click="onSummarize"
          >
            {{ summarizing ? t("books.summarizing") : t("books.summarize") }}
          </button>
        </div>
        <p v-if="summarizing && summarizeTask" class="progress-line">
          {{ t("books.summarizeProgress", { progress: summarizeTask.progress }) }}
        </p>
        <p v-if="summarizeError" class="error">{{ summarizeError }}</p>
        <p v-if="book.summary" class="summary-text">{{ book.summary }}</p>
        <p v-else-if="!summarizing" class="empty">{{ t("books.noSummaryYet") }}</p>
      </div>

      <h2>{{ t("books.chapters") }}</h2>
      <ol v-if="book.chapters.length" class="chapters">
        <li v-for="ch in book.chapters" :key="ch.id">
          <div class="chapter-title">{{ ch.title }}</div>
          <p v-if="ch.summary" class="chapter-summary">{{ ch.summary }}</p>
        </li>
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
.summary-section {
  margin: 1.5rem 0;
  padding: 1rem 1.25rem;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.summary-header h2 {
  margin: 0;
  font-size: 1rem;
}
.progress-line {
  font-size: 0.85rem;
  opacity: 0.75;
  margin: 0.5rem 0 0;
}
.summary-text {
  margin: 0.75rem 0 0;
  line-height: 1.6;
  white-space: pre-wrap;
}
.empty {
  margin: 0.75rem 0 0;
  opacity: 0.6;
  font-size: 0.9rem;
}
.chapters {
  padding-left: 1.25rem;
}
.chapters li {
  padding: 0.4rem 0;
}
.chapter-title {
  font-weight: 500;
}
.chapter-summary {
  margin: 0.25rem 0 0;
  font-size: 0.85rem;
  opacity: 0.75;
  line-height: 1.5;
}
.badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: var(--code-bg);
}
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.35rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
  font-size: 0.85rem;
}
button.ghost:disabled {
  opacity: 0.5;
  cursor: default;
}
.error {
  color: #d33;
  font-size: 0.85rem;
  margin: 0.5rem 0 0;
}
</style>
