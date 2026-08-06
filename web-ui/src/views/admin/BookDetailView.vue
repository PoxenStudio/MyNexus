<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { getBook, rebuildBook, summarizeBook, updateBook, type BookDetail } from "../../api/books";
import { getTask, listTasks, type Task } from "../../api/tasks";
import ConfirmDialog from "../../components/ConfirmDialog.vue";
import KeywordCloud from "../../components/KeywordCloud.vue";
import { languageName, languageOptions } from "../../utils/languageCodes";

const { t } = useI18n();
const route = useRoute();
const book = ref<BookDetail | null>(null);
const loading = ref(true);

const editingLanguage = ref(false);
const languageDraft = ref("");
const languageSaving = ref(false);
const languageError = ref("");

function startEditLanguage() {
  if (!book.value) return;
  languageDraft.value = book.value.language;
  languageError.value = "";
  editingLanguage.value = true;
}

function cancelEditLanguage() {
  editingLanguage.value = false;
}

async function saveLanguage() {
  if (!book.value) return;
  languageSaving.value = true;
  languageError.value = "";
  try {
    // PUT overwrites title/author/category/tags wholesale — carry the
    // book's current values through so only language actually changes.
    const updated = await updateBook(book.value.id, {
      title: book.value.title,
      author: book.value.author,
      category: book.value.category,
      tags: book.value.tags,
      language: languageDraft.value,
    });
    book.value.language = updated.language;
    editingLanguage.value = false;
  } catch (e: any) {
    languageError.value = e?.response?.data?.error || t("books.languageSaveError");
  } finally {
    languageSaving.value = false;
  }
}

const summarizing = ref(false);
const summarizeTask = ref<Task | null>(null);
const summarizeError = ref("");
const rebuildError = ref("");
const rebuildConfirmOpen = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

// Any non-terminal task for this book — set either by onSummarize() below or,
// on a fresh page load / navigation back, by discovering one already running
// (triggered from elsewhere, e.g. re-ingestion or a summarize call from a
// previous visit) via findActiveTask(). Drives the generic "task running"
// banner; summarize-specific UI (buttons, progress line) still keys off
// summarizeTask/summarizing so it only lights up for that task type.
const CHAPTER_SUMMARY_TRUNCATE_LENGTH = 600;
// Chapter ids whose summary is currently shown in full — everything else
// renders truncated (see chapterSummaryText()) with a "展开" toggle.
const expandedChapters = ref(new Set<string>());

function isChapterSummaryLong(summary: string): boolean {
  return summary.length > CHAPTER_SUMMARY_TRUNCATE_LENGTH;
}

function chapterSummaryText(ch: { id: string; summary: string }): string {
  if (expandedChapters.value.has(ch.id) || !isChapterSummaryLong(ch.summary)) return ch.summary;
  return ch.summary.slice(0, CHAPTER_SUMMARY_TRUNCATE_LENGTH - 100) + "…";
}

function toggleChapterSummary(id: string) {
  if (expandedChapters.value.has(id)) {
    expandedChapters.value.delete(id);
  } else {
    expandedChapters.value.add(id);
  }
  // Set mutation alone doesn't trigger reactivity on a ref<Set> — replace it.
  expandedChapters.value = new Set(expandedChapters.value);
}

// Latest stage message for the summarize task — e.g. summary.py's per-chapter
// "N/total 《title》 生成中…已输出 X 字" ticks for a chapter that's taking a
// while, so a long chapter doesn't just sit at the same percentage with no
// sign anything is happening.
const summarizeStageMessage = computed(() => {
  const log = summarizeTask.value?.stages_log;
  return log?.length ? log[log.length - 1].message : "";
});

const activeTask = ref<Task | null>(null);
const activeTaskLabel = computed(() => {
  const task = activeTask.value;
  if (!task) return "";
  const stage = task.stages_log?.length ? task.stages_log[task.stages_log.length - 1].stage : task.status;
  return t("books.activeTask", {
    type: t(`taskType.${task.type}`, task.type),
    stage: t(`taskStage.${stage}`, stage),
    progress: task.progress,
  });
});

// A rebuild re-parses/re-chunks/re-embeds the book (POST /books/{id}/rebuild,
// same as the books-list page's "重建" button) — it replaces book.chapters
// out from under any in-flight summarize run, so the two are mutually
// exclusive: summarizing is disabled while a rebuild's ingest task is
// running, and vice versa (see the template).
const rebuilding = computed(() => activeTask.value?.type === "ingest");

// Three states, per how much of the map-reduce has already landed in the DB:
// - none started: only "Summarize Book" (restart, though restart/continue
//   are equivalent here since there's nothing to resume).
// - some chapters summarized but no book-level summary yet (partial run,
//   e.g. interrupted or failed midway): offer both "Continue" (resume,
//   skip chapters already done) and "Restart" (redo everything).
// - book summary present (a full run completed): only "Restart" — a
//   "continue" from a finished state would be a no-op.
const summarizeState = computed<"none" | "partial" | "done">(() => {
  if (!book.value) return "none";
  if (book.value.summary) return "done";
  if (book.value.chapters.some((ch) => ch.summary)) return "partial";
  return "none";
});

async function load() {
  loading.value = true;
  try {
    book.value = await getBook(route.params.id as string);
    await findActiveTask();
  } finally {
    loading.value = false;
  }
}

// Picks up a task already running against this book — e.g. an ingest/rebuild
// triggered from the books list, or a summarize call from a previous visit —
// so the "in progress" state survives a page reload/navigation instead of
// only appearing when onSummarize() was clicked in this same session.
async function findActiveTask() {
  if (!book.value || pollTimer) return;
  const { items } = await listTasks({ book_id: book.value.id, size: 5 });
  const running = items.find((t) => t.status === "pending" || t.status === "processing");
  if (!running) return;

  if (running.type === "summarize") {
    summarizing.value = true;
    summarizeTask.value = running;
  } else {
    activeTask.value = running;
  }
  pollTimer = setInterval(() => pollTask(running.id), 2000);
  await pollTask(running.id);
}

async function onSummarize(mode: "restart" | "continue") {
  if (!book.value) return;
  summarizeError.value = "";
  summarizing.value = true;
  try {
    const { task_id } = await summarizeBook(book.value.id, mode);
    pollTimer = setInterval(() => pollTask(task_id), 2000);
    await pollTask(task_id);
  } catch (e: any) {
    summarizing.value = false;
    summarizeError.value = e?.response?.data?.error || t("books.summarizeError");
  }
}

function onRebuild() {
  if (!book.value) return;
  rebuildConfirmOpen.value = true;
}

async function doRebuild() {
  if (!book.value) return;
  rebuildError.value = "";
  try {
    const { task_id } = await rebuildBook(book.value.id);
    // Placeholder so the "重建中…" button/banner switch on immediately —
    // pollTask overwrites this with the real task on its first tick, same
    // as onSummarize does implicitly via summarizing.value.
    const now = new Date().toISOString();
    activeTask.value = {
      id: task_id,
      book_id: book.value.id,
      type: "ingest",
      status: "pending",
      progress: 0,
      error_msg: "",
      stages_log: [],
      created_at: now,
      updated_at: now,
    };
    pollTimer = setInterval(() => pollTask(task_id), 2000);
    await pollTask(task_id);
  } catch (e: any) {
    rebuildError.value = e?.response?.data?.error || t("books.rebuildError");
  }
}

async function pollTask(taskId: string) {
  const task = await getTask(taskId);
  if (task.type === "summarize") {
    summarizeTask.value = task;
  } else {
    activeTask.value = task;
  }
  // Reload the book on every tick too — e.g. chapter summaries land one at a
  // time (the map step) well before the task itself completes (the reduce
  // step), so this is what makes each chapter's summary appear as it's ready.
  book.value = await getBook(route.params.id as string);

  if (task.status === "completed" || task.status === "failed") {
    stopPolling();
    summarizing.value = false;
    activeTask.value = null;
    if (task.status === "failed") {
      if (task.type === "summarize") {
        summarizeError.value = task.error_msg || t("books.summarizeError");
      } else {
        rebuildError.value = task.error_msg || t("books.rebuildError");
      }
    }
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
      <div class="detail-grid">
        <div class="info-card">
          <h1>{{ book.title || book.id }}</h1>
          <dl class="meta">
            <dt>{{ t("books.table.author") }}</dt>
            <dd>{{ book.author || "—" }}</dd>
            <dt>{{ t("books.table.format") }}</dt>
            <dd>{{ book.source_format }}</dd>
            <dt>{{ t("books.table.status") }}</dt>
            <dd><span :class="['badge', book.status]">{{ t(`status.${book.status}`, book.status) }}</span></dd>
            <dt>{{ t("books.language") }}</dt>
            <dd class="language-row">
              <template v-if="editingLanguage">
                <select v-model="languageDraft" :disabled="languageSaving">
                  <option v-for="opt in languageOptions" :key="opt.code" :value="opt.code">{{ opt.name }}</option>
                </select>
                <button class="icon-btn" :disabled="languageSaving" :title="t('common.save')" @click="saveLanguage">
                  ✓
                </button>
                <button class="icon-btn" :disabled="languageSaving" :title="t('common.cancel')" @click="cancelEditLanguage">
                  ✕
                </button>
              </template>
              <template v-else>
                {{ languageName(book.language) || "—" }}
                <button class="icon-btn" :title="t('common.edit')" @click="startEditLanguage">
                  <svg viewBox="0 0 20 20" width="14" height="14" aria-hidden="true">
                    <path
                      fill="currentColor"
                      d="M14.85 2.85a1.5 1.5 0 0 1 2.12 0l.18.18a1.5 1.5 0 0 1 0 2.12l-9.3 9.3-3.03.9.9-3.03 9.13-9.13Zm-10.4 10.4-.7 2.36a.5.5 0 0 0 .62.62l2.36-.7-2.28-2.28Z"
                    />
                  </svg>
                </button>
              </template>
            </dd>
          </dl>
          <p v-if="languageError" class="error">{{ languageError }}</p>
        </div>
        <div class="keyword-card">
          <h2>{{ t("books.keywords") }}</h2>
          <KeywordCloud :keywords="book.keywords">
            <template #empty>{{ t("books.noKeywords") }}</template>
          </KeywordCloud>
        </div>
      </div>

      <p v-if="activeTask" class="active-task">{{ activeTaskLabel }}</p>

      <div class="summary-section">
        <div class="summary-header">
          <h2>{{ t("books.bookSummary") }}</h2>
          <div class="summary-actions">
            <template v-if="summarizing">
              <button class="ghost" disabled>{{ t("books.summarizing") }}</button>
            </template>
            <template v-else>
              <button
                v-if="summarizeState === 'partial'"
                class="ghost"
                :disabled="!book.chapters.length || rebuilding"
                @click="onSummarize('continue')"
              >
                {{ t("books.continueSummarize") }}
              </button>
              <button
                class="ghost"
                :disabled="!book.chapters.length || rebuilding"
                :title="!book.chapters.length ? t('books.noChaptersToSummarize') : undefined"
                @click="onSummarize('restart')"
              >
                {{ summarizeState === "none" ? t("books.summarize") : t("books.resummarize") }}
              </button>
            </template>
            <button class="ghost" :disabled="summarizing || rebuilding" @click="onRebuild">
              {{ rebuilding ? t("books.rebuilding") : t("books.rebuild") }}
            </button>
          </div>
        </div>
        <p v-if="summarizing && summarizeTask" class="progress-line">
          {{ t("books.summarizeProgress", { progress: summarizeTask.progress }) }}
          <span v-if="summarizeStageMessage">· {{ summarizeStageMessage }}</span>
        </p>
        <p v-if="summarizeError" class="error">{{ summarizeError }}</p>
        <p v-if="rebuildError" class="error">{{ rebuildError }}</p>
        <p v-if="book.summary" class="summary-text">{{ book.summary }}</p>
        <p v-else-if="!summarizing" class="empty">{{ t("books.noSummaryYet") }}</p>
      </div>

      <h2>{{ t("books.chapters") }}</h2>
      <ol v-if="book.chapters.length" class="chapters">
        <li v-for="ch in book.chapters" :key="ch.id">
          <div class="chapter-title">{{ ch.title }}</div>
          <p v-if="ch.summary" class="chapter-summary">
            {{ chapterSummaryText(ch) }}
            <button v-if="isChapterSummaryLong(ch.summary)" class="link-btn" @click="toggleChapterSummary(ch.id)">
              {{ expandedChapters.has(ch.id) ? t("books.collapseSummary") : t("books.expandSummary") }}
            </button>
          </p>
        </li>
      </ol>
      <p v-else>{{ t("books.noChapters") }}</p>
    </template>

    <ConfirmDialog
      v-model="rebuildConfirmOpen"
      :title="t('books.rebuild')"
      :message="t('books.confirmRebuild')"
      @confirm="doRebuild"
    />
  </section>
</template>

<style scoped>
/* Left: book info card (title + metadata). Right: content-keyword cloud
   card. Equal-width columns on wide screens; below 900px they stack into
   one column, keyword card second, so the page never scrolls horizontally. */
.detail-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 1.5rem;
  align-items: start;
  margin: 1rem 0;
}
@media (max-width: 900px) {
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
.info-card h1 {
  margin: 0 0 0.5rem;
}
.keyword-card {
  padding: 1rem 1.25rem;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.keyword-card h2 {
  margin: 0 0 0.75rem;
  font-size: 1rem;
}
.meta {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 0.25rem 1rem;
  margin: 0;
  font-size: 0.9rem;
}
.meta dt {
  opacity: 0.7;
}
.language-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}
.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border);
  background: transparent;
  color: inherit;
  border-radius: 5px;
  width: 1.6rem;
  height: 1.6rem;
  padding: 0;
  cursor: pointer;
  font-size: 0.8rem;
  line-height: 1;
}
.icon-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.language-row select {
  font-size: 0.85rem;
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
.summary-actions {
  display: flex;
  gap: 0.5rem;
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
.link-btn {
  border: none;
  background: none;
  padding: 0;
  margin-left: 0.25rem;
  color: var(--accent);
  cursor: pointer;
  font-size: inherit;
  opacity: 1;
  white-space: nowrap;
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
.active-task {
  margin: 0.75rem 0 0;
  padding: 0.4rem 0.75rem;
  border-radius: 6px;
  background: var(--code-bg);
  font-size: 0.85rem;
  opacity: 0.85;
}
</style>
