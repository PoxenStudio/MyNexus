<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import {
  cancelBookDataImport,
  confirmBookDataImport,
  getActiveBookImport,
  getBook,
  getTransferJob,
  importBookData,
  rebuildBook,
  summarizeBook,
  updateBook,
  updateBookSummary,
  type BookDetail,
  type TransferJob,
} from "../../api/books";
import { fetchBookTokenUsage, formatTokens, type BookTokenUsage } from "../../api/token";
import { apiClient } from "../../api/client";
import { listTasks, cancelTask, type Task } from "../../api/tasks";
import AppIcon from "../../components/AppIcon.vue";
import BarChart from "../../components/charts/BarChart.vue";
import ConfirmDialog from "../../components/ConfirmDialog.vue";
import DefinitionList from "../../components/DefinitionList.vue";
import KeywordCloud from "../../components/KeywordCloud.vue";
import MarkdownContent from "../../components/MarkdownContent.vue";
import { setPageTitleSuffix } from "../../composables/pageTitle";
import { languageName, languageOptions } from "../../utils/languageCodes";

const { t } = useI18n();
const route = useRoute();
const book = ref<BookDetail | null>(null);
const loading = ref(true);

// Cover image (see core-api's BookHandler.Cover) — relative to apiClient's
// base URL like AuthHandler's avatar_url (see auth store's fullAvatarUrl for
// the same pattern). "" whenever the book has none yet (not ingested, or
// Worker produced nothing — shouldn't normally happen once ingest
// completes, since a title-generated fallback always fills the gap, see
// worker/src/util/cover_generator.py) or the <img> failed to load, in
// either case falling back to a plain title-initial placeholder below.
const coverBroken = ref(false);
watch(
  () => book.value?.id,
  () => {
    coverBroken.value = false;
  },
);
const coverUrl = computed(() => {
  if (!book.value?.cover_url || coverBroken.value) return "";
  return apiClient.defaults.baseURL + book.value.cover_url;
});
const coverInitial = computed(() => (book.value?.title || book.value?.id || "?").charAt(0).toUpperCase());

const tokenUsage = ref<BookTokenUsage | null>(null);
const tokenLoading = ref(false);
const importInput = ref<HTMLInputElement | null>(null);
const transferJob = ref<TransferJob | null>(null);
const transferError = ref("");
const transferBusy = ref(false);
let transferPollTimer: ReturnType<typeof setInterval> | null = null;

function callSiteLabel(site: string): string {
  const base = site.replace(/^summary\./, "").replace(/\.segment\.\d+$/, "").replace(/_\d+$/, "");
  const key = `tokens.callSite.${base}`;
  const translated = t(key);
  return translated === key ? base : translated;
}

const callsiteChartData = computed(() => {
  if (!tokenUsage.value) return [];
  return tokenUsage.value.breakdown.map((b) => ({
    label: callSiteLabel(b.call_site),
    value: b.total_tokens,
  }));
});

async function loadTokenUsage() {
  if (!book.value) return;
  // pollTask re-runs this every 2s; only the first load may show the
  // "加载中" placeholder, later refreshes swap data in silently (no flicker).
  if (tokenUsage.value === null) tokenLoading.value = true;
  try {
    tokenUsage.value = await fetchBookTokenUsage(book.value.id);
  } catch {
    // keep previously shown numbers on a refresh hiccup
  } finally {
    tokenLoading.value = false;
  }
}

// Tab title shows "详情 - <书名>" while this view is open (see App.vue),
// falling back to the book id if a title hasn't loaded/generated yet.
watch(
  () => book.value?.title || book.value?.id,
  (name) => setPageTitleSuffix(name || null),
  { immediate: true },
);

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

// Manual touch-up of the generated whole-book summary (typo/wrong fact/
// phrasing) — a plain textarea, not a rich editor: this is meant for small
// edits to already-generated Markdown text, not authoring it from scratch.
const editingSummary = ref(false);
const summaryDraft = ref("");
const summarySaving = ref(false);
const summaryEditError = ref("");

function startEditSummary() {
  if (!book.value) return;
  summaryDraft.value = book.value.summary;
  summaryEditError.value = "";
  editingSummary.value = true;
}

function cancelEditSummary() {
  editingSummary.value = false;
}

async function saveSummary() {
  if (!book.value) return;
  summarySaving.value = true;
  summaryEditError.value = "";
  try {
    const updated = await updateBookSummary(book.value.id, summaryDraft.value);
    book.value.summary = updated.summary;
    editingSummary.value = false;
  } catch (e: any) {
    summaryEditError.value = e?.response?.data?.error || t("books.summarySaveError");
  } finally {
    summarySaving.value = false;
  }
}

const summarizing = ref(false);
const summarizeTask = ref<Task | null>(null);
const summarizeError = ref("");
const canceling = ref(false);
const rebuildError = ref("");
const rebuildConfirmOpen = ref(false);
let pollTimer: ReturnType<typeof setInterval> | null = null;

// Any non-terminal task for this book — set either by onSummarize() below or,
// on a fresh page load / navigation back, by discovering one already running
// (triggered from elsewhere, e.g. re-ingestion or a summarize call from a
// previous visit) via findActiveTask(). Drives the generic "task running"
// banner; summarize-specific UI (buttons, progress line) still keys off
// summarizeTask/summarizing so it only lights up for that task type.
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
  // Queued (waiting on worker.max_concurrent_tasks — see core-api's
  // internal/dispatch) wins over the stage log even if one somehow exists,
  // since a queued task hasn't actually started running yet regardless.
  const stage =
    task.status === "pending" && !task.dispatched
      ? "queued"
      : task.stages_log?.length
        ? task.stages_log[task.stages_log.length - 1].stage
        : task.status;
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
    await Promise.all([findActiveTask(), findActiveImport(), loadTokenUsage()]);
  } finally {
    loading.value = false;
  }
}

const transferIsActive = computed(
  () =>
    transferJob.value !== null &&
    ["pending", "processing", "awaiting_confirmation"].includes(transferJob.value.status),
);

async function findActiveImport() {
  if (!book.value) return;
  const active = await getActiveBookImport(book.value.id);
  if (!active) return;
  transferJob.value = active;
  if (active.status !== "awaiting_confirmation") startTransferPolling();
}

function chooseImportFile() {
  importInput.value?.click();
}

async function onImportFileSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  input.value = "";
  if (!file || !book.value) return;
  transferError.value = "";
  transferBusy.value = true;
  try {
    transferJob.value = await importBookData(book.value.id, file);
    startTransferPolling();
    await pollTransfer();
  } catch (e: any) {
    transferError.value = e?.response?.data?.error || t("books.dataImportError");
  } finally {
    transferBusy.value = false;
  }
}

function startTransferPolling() {
  if (transferPollTimer) return;
  transferPollTimer = setInterval(() => void pollTransfer(), 2000);
}

function stopTransferPolling() {
  if (!transferPollTimer) return;
  clearInterval(transferPollTimer);
  transferPollTimer = null;
}

async function pollTransfer() {
  if (!transferJob.value) return;
  try {
    transferJob.value = await getTransferJob(transferJob.value.id);
    if (transferJob.value.status === "awaiting_confirmation") {
      stopTransferPolling();
      return;
    }
    if (transferJob.value.status === "completed") {
      stopTransferPolling();
      book.value = await getBook(transferJob.value.book_id);
      return;
    }
    if (transferJob.value.status === "failed" || transferJob.value.status === "canceled") {
      stopTransferPolling();
      if (transferJob.value.status === "failed") {
        transferError.value = transferJob.value.error_msg || t("books.dataImportError");
      }
    }
  } catch (e: any) {
    transferError.value = e?.response?.data?.error || t("books.dataImportError");
    stopTransferPolling();
  }
}

async function confirmDataImport() {
  if (!transferJob.value) return;
  transferError.value = "";
  transferBusy.value = true;
  try {
    transferJob.value = await confirmBookDataImport(transferJob.value.id);
    startTransferPolling();
    await pollTransfer();
  } catch (e: any) {
    transferError.value = e?.response?.data?.error || t("books.dataImportError");
  } finally {
    transferBusy.value = false;
  }
}

async function cancelDataImport() {
  if (!transferJob.value) return;
  transferBusy.value = true;
  transferError.value = "";
  try {
    transferJob.value = await cancelBookDataImport(transferJob.value.id);
    stopTransferPolling();
  } catch (e: any) {
    transferError.value = e?.response?.data?.error || t("books.dataImportError");
  } finally {
    transferBusy.value = false;
  }
}

// Picks up a task already running against this book — e.g. an ingest/rebuild
// triggered from the books list, or a summarize call from a previous visit —
// so the "in progress" state survives a page reload/navigation instead of
// only appearing when onSummarize() was clicked in this same session.
//
// Starts polling the book's *current* active task, not a fixed id — this is
// what lets the rebuild-ingest → auto-summarize chain flow into the
// summarize-progress line without a manual refresh. See pollTask() below.
async function findActiveTask() {
  if (!book.value || pollTimer) return;
  const { items } = await listTasks({ book_id: book.value.id, size: 5 });
  const running = items.find((t) => t.status === "pending" || t.status === "processing");
  if (!running) return;
  pollTimer = setInterval(() => pollTask(), 2000);
  await pollTask();
}

async function onSummarize(mode: "restart" | "continue") {
  if (!book.value) return;
  summarizeError.value = "";
  summarizing.value = true;
  try {
    await summarizeBook(book.value.id, mode);
    if (!pollTimer) pollTimer = setInterval(() => pollTask(), 2000);
    await pollTask();
  } catch (e: any) {
    summarizing.value = false;
    summarizeError.value = e?.response?.data?.error || t("books.summarizeError");
  }
}

function onRebuild() {
  if (!book.value) return;
  rebuildConfirmOpen.value = true;
}

async function onCancelSummarize() {
  if (!summarizeTask.value) return;
  canceling.value = true;
  summarizeError.value = "";
  try {
    await cancelTask(summarizeTask.value.id);
  } catch (e: any) {
    summarizeError.value = e?.response?.data?.error || t("books.summarizeError");
  } finally {
    canceling.value = false;
  }
}

async function doRebuild() {
  if (!book.value) return;
  rebuildError.value = "";
  try {
    await rebuildBook(book.value.id);
    pollTimer = setInterval(() => pollTask(), 2000);
    await pollTask();
  } catch (e: any) {
    rebuildError.value = e?.response?.data?.error || t("books.rebuildError");
  }
}

async function pollTask() {
  if (!book.value) return;
  const { items } = await listTasks({ book_id: book.value.id, size: 5 });

  const active = items.find((t) => t.status === "pending" || t.status === "processing");

  if (active) {
    // Pick up a freshly-appeared summarize task chained off ingest completion
    // (or discovered on page load) — whichever non-terminal task is newest
    // wins, so we transition seamlessly between rebuild → auto-summarize
    // without a manual refresh.
    if (active.type === "summarize") {
      summarizeTask.value = active;
      summarizing.value = true;
      activeTask.value = null;
    } else {
      activeTask.value = active;
      summarizeTask.value = null;
    }
    book.value = await getBook(book.value.id);
    await loadTokenUsage();
    return;
  }

  // No non-terminal task — either we never started one (first tick after
  // the API returned), or the last one just finished. In either case,
  // settle UI into the idle state using whichever terminal task landed last.
  stopPolling();
  summarizing.value = false;
  const latest = items[0];
  activeTask.value = null;
  book.value = await getBook(book.value.id);
  await loadTokenUsage();

  if (latest && latest.status === "failed") {
    if (latest.type === "summarize") {
      summarizeError.value = latest.error_msg || t("books.summarizeError");
    } else if (latest.type === "ingest") {
      rebuildError.value = latest.error_msg || t("books.rebuildError");
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
onUnmounted(() => {
  stopPolling();
  stopTransferPolling();
  setPageTitleSuffix(null);
});
</script>

<template>
  <section>
    <router-link to="/books">&larr; {{ t("books.title") }}</router-link>

    <div v-if="loading">{{ t("common.loading") }}</div>
    <template v-else-if="book">
      <div class="detail-grid">
        <div class="info-card">
          <div class="info-card-body">
            <div class="cover">
              <img v-if="coverUrl" :src="coverUrl" :alt="book.title" @error="coverBroken = true" />
              <div v-else class="cover-fallback" aria-hidden="true">{{ coverInitial }}</div>
            </div>
            <div class="info-main">
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
                    <button
                      class="icon-btn"
                      :disabled="languageSaving"
                      :title="t('common.cancel')"
                      @click="cancelEditLanguage"
                    >
                      ✕
                    </button>
                  </template>
                  <template v-else>
                    {{ languageName(book.language) || "—" }}
                    <button class="icon-btn" :title="t('common.edit')" @click="startEditLanguage">
                      <AppIcon name="edit" :size="14" />
                    </button>
                  </template>
                </dd>
              </dl>
              <p v-if="languageError" class="error">{{ languageError }}</p>
              <div class="transfer-panel">
                <input
                  ref="importInput"
                  class="visually-hidden"
                  type="file"
                  accept=".zip,application/zip"
                  @change="onImportFileSelected"
                />
                <button
                  type="button"
                  class="ghost-btn"
                  :disabled="transferBusy || transferIsActive || Boolean(activeTask)"
                  @click="chooseImportFile"
                >
                  {{ transferBusy ? t("books.dataImportUploading") : t("books.importData") }}
                </button>
                <p v-if="transferJob && ['pending', 'processing'].includes(transferJob.status)" class="progress-line">
                  {{ t("books.dataImportProgress", { progress: transferJob.progress, stage: transferJob.stage }) }}
                </p>
                <div v-if="transferJob?.status === 'awaiting_confirmation' && transferJob.preview" class="transfer-preview">
                  <p>
                    {{ t("books.dataImportPreview", {
                      source: transferJob.preview.source_title,
                      target: transferJob.preview.target_title,
                      chapters: transferJob.preview.matched_chapters,
                      totalChapters: transferJob.preview.source_chapters,
                      vectors: transferJob.preview.matched_vectors,
                      totalVectors: transferJob.preview.source_vectors
                    }) }}
                  </p>
                  <p v-if="transferJob.preview.warning" class="transfer-warning">
                    {{ t("books.dataImportWarning") }}
                  </p>
                  <div class="transfer-actions">
                    <button type="button" class="primary" :disabled="transferBusy" @click="confirmDataImport">
                      {{ t("books.confirmDataImport") }}
                    </button>
                    <button type="button" class="ghost-btn" :disabled="transferBusy" @click="cancelDataImport">
                      {{ t("common.cancel") }}
                    </button>
                  </div>
                </div>
                <p v-if="transferJob?.status === 'completed'" class="transfer-success">
                  {{ t("books.dataImportCompleted") }}
                </p>
                <p v-if="transferError" class="error">{{ transferError }}</p>
              </div>
            </div>
          </div>
        </div>
        <div class="keyword-card">
          <h2>{{ t("books.keywords") }}</h2>
          <KeywordCloud :keywords="book.keywords">
            <template #empty>{{ t("books.noKeywords") }}</template>
          </KeywordCloud>
        </div>
      </div>

      <p v-if="activeTask" class="active-task">{{ activeTaskLabel }}</p>

      <div class="token-card">
        <h2>{{ t("books.tokenUsage") }}</h2>
        <div v-if="tokenLoading" class="token-loading">{{ t("common.loading") }}</div>
        <template v-else-if="tokenUsage">
          <div v-if="tokenUsage.total_tokens > 0" class="token-stats">
            <div class="token-stat">
              <span class="token-stat-label">{{ t("books.totalTokens") }}</span>
              <span class="token-stat-value">{{ formatTokens(tokenUsage.total_tokens) }}</span>
            </div>
            <div class="token-stat">
              <span class="token-stat-label">{{ t("books.promptTokens") }}</span>
              <span class="token-stat-value">{{ formatTokens(tokenUsage.prompt_tokens) }}</span>
            </div>
            <div class="token-stat">
              <span class="token-stat-label">{{ t("books.completionTokens") }}</span>
              <span class="token-stat-value">{{ formatTokens(tokenUsage.completion_tokens) }}</span>
            </div>
            <div class="token-stat">
              <span class="token-stat-label">{{ t("books.llmCalls") }}</span>
              <span class="token-stat-value">{{ tokenUsage.calls }}</span>
            </div>
          </div>
          <template v-if="callsiteChartData.length > 1">
            <h3>{{ t("books.tokenBreakdown") }}</h3>
            <BarChart :data="callsiteChartData" />
          </template>
          <p v-else class="token-empty">{{ t("books.noTokenUsage") }}</p>
        </template>
        <p v-else class="token-empty">{{ t("books.noTokenUsage") }}</p>
      </div>

      <div class="summary-section">
        <div class="summary-header">
          <h2>
            <span class="summary-dot" aria-hidden="true"></span>{{ t("books.bookSummary") }}
            <button
              v-if="summarizeState === 'done' && !summarizing && !rebuilding"
              class="icon-btn"
              :title="t('books.regenerateBookSummary')"
              @click="onSummarize('continue')"
            >
              <AppIcon name="refresh" :size="16" />
            </button>
            <button
              v-if="book.summary && !summarizing && !rebuilding && !editingSummary"
              class="icon-btn"
              :title="t('common.edit')"
              @click="startEditSummary"
            >
              <AppIcon name="edit" :size="14" />
            </button>
          </h2>
          <div class="summary-actions">
            <template v-if="summarizing">
                <button class="primary" disabled>{{ t("books.summarizing") }}</button>
                <button type="button" class="ghost-btn" :disabled="canceling" @click="onCancelSummarize">
                  {{ t("books.cancelSummarize") }}
                </button>
              </template>
            <template v-else>
              <button
                v-if="summarizeState === 'partial'"
                class="primary"
                :disabled="!book.chapters.length || rebuilding"
                :title="!book.chapters.length ? t('books.noChaptersToSummarize') : t('books.continueSummarizeTooltip')"
                @click="onSummarize('continue')"
              >
                {{ t("books.continueSummarize") }}
              </button>
              <button
                class="primary"
                :disabled="!book.chapters.length || rebuilding"
                :title="!book.chapters.length ? t('books.noChaptersToSummarize') : summarizeState === 'none' ? t('books.summarizeTooltip') : t('books.resummarizeTooltip')"
                @click="onSummarize('restart')"
              >
                {{ summarizeState === "none" ? t("books.summarize") : t("books.resummarize") }}
              </button>
            </template>
            <button class="primary" :disabled="summarizing || rebuilding" :title="t('books.rebuildTooltip')" @click="onRebuild">
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
        <div v-if="editingSummary" class="summary-edit">
          <textarea v-model="summaryDraft" class="summary-textarea" rows="12"></textarea>
          <p v-if="summaryEditError" class="error">{{ summaryEditError }}</p>
          <div class="summary-edit-actions">
            <button class="primary" :disabled="summarySaving" @click="saveSummary">
              {{ summarySaving ? t("common.loading") : t("common.save") }}
            </button>
            <button type="button" :disabled="summarySaving" @click="cancelEditSummary">
              {{ t("common.cancel") }}
            </button>
          </div>
        </div>
        <div v-else-if="book.summary" class="summary-body">
          <MarkdownContent :content="book.summary" class="summary-text" />
        </div>

        <details v-if="book.reading_guide" class="summary-section">
          <summary class="summary-section-summary">
            <h2>
              <span class="summary-dot" aria-hidden="true"></span>{{ t("books.readingGuide") }}
            </h2>
            <AppIcon name="chevronDown" :size="18" class="summary-section-toggle" />
          </summary>
          <div class="summary-body">
            <MarkdownContent :content="book.reading_guide" class="summary-text" />
          </div>
        </details>

        <details v-if="book.reference_index" class="summary-section">
          <summary class="summary-section-summary">
            <h2>
              <span class="summary-dot" aria-hidden="true"></span>{{ t("books.referenceIndex") }}
            </h2>
            <AppIcon name="chevronDown" :size="18" class="summary-section-toggle" />
          </summary>
          <div class="summary-body">
            <MarkdownContent :content="book.reference_index" class="summary-text" />
          </div>
        </details>
        <p v-if="!book.summary && !summarizing" class="empty">{{ t("books.noSummaryYet") }}</p>
      </div>

      <h2>{{ t("books.chapters") }}</h2>
      <ol v-if="book.chapters.length" class="chapters">
        <li v-for="ch in book.chapters" :key="ch.id">
          <details v-if="ch.summary" class="chapter-card" open>
            <summary class="chapter-title">
              <span class="chapter-dot" aria-hidden="true"></span>
              <span class="chapter-title-text">{{ ch.title }}</span>
              <AppIcon name="chevronDown" :size="18" class="chapter-toggle-icon" />
            </summary>
            <MarkdownContent :content="ch.summary" class="chapter-summary" />
            <div v-if="ch.keywords.length" class="chapter-extra">
              <h3>{{ t("books.chapterKeywords") }}</h3>
              <KeywordCloud :keywords="ch.keywords" />
            </div>
            <div v-if="ch.definitions.length" class="chapter-extra">
              <h3>{{ t("books.chapterDefinitions") }}</h3>
              <DefinitionList :definitions="ch.definitions" />
            </div>
          </details>
          <div v-else class="chapter-title chapter-title-plain">
            <span class="chapter-dot" aria-hidden="true"></span>
            <span class="chapter-title-text">{{ ch.title }}</span>
            <span class="chapter-status-pending">{{ t("books.chapterNotSummarized") }}</span>
            <button
              class="chapter-retry-btn"
              :class="{ 'is-loading': summarizing }"
              :disabled="summarizing"
              :title="summarizing ? t('books.summarizing') : t('books.retryChapterSummary')"
              @click="onSummarize('continue')"
            >
              <AppIcon name="refresh" :size="14" />
            </button>
          </div>
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
.info-card-body {
  display: flex;
  gap: 1.25rem;
  align-items: flex-start;
}
.info-main {
  flex: 1;
  min-width: 0;
}
.info-card h1 {
  margin: 0 0 0.5rem;
}
/* Fixed-size box (2:3, a typical book-cover ratio) so the layout doesn't
   jump around while the image loads or when a book has none yet — the
   fallback below fills exactly the same box. */
.cover {
  flex-shrink: 0;
  width: 96px;
  height: 144px;
  border-radius: 6px;
  overflow: hidden;
  box-shadow: var(--elevation-1, 0 1px 3px rgba(0, 0, 0, 0.15));
  background: var(--code-bg);
}
.cover img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.cover-fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  font-size: 2rem;
  font-weight: 700;
  color: var(--accent);
  background: var(--accent-bg);
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
.transfer-panel {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
.transfer-preview {
  flex-basis: 100%;
  padding: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: 0.85rem;
}
.transfer-preview p {
  margin: 0;
}
.transfer-preview .transfer-warning {
  margin-top: 0.5rem;
  color: var(--warning, #a16207);
}
.transfer-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
  margin-top: 0.75rem;
}
.transfer-actions button {
  padding: 0.35rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  font: inherit;
  font-size: 0.85rem;
}
.transfer-actions .primary {
  border: 1px solid var(--accent);
  background: var(--accent);
  color: var(--on-accent, #fff);
}
.transfer-actions .ghost-btn {
  border: 1px solid var(--border);
  background: transparent;
  color: inherit;
}
.transfer-success {
  margin: 0;
  color: var(--success, #16803c);
  font-size: 0.85rem;
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.summary-section {
  margin: 1.5rem 0;
  padding: 1rem 1.25rem;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.summary-section-summary {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  list-style: none;
}
.summary-section-summary::-webkit-details-marker {
  display: none;
}
.summary-section-toggle {
  flex-shrink: 0;
  opacity: 0.6;
  transition: transform 0.15s ease;
}
.summary-section[open] .summary-section-toggle {
  transform: rotate(180deg);
}
.summary-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 1rem;
}
.summary-header h2 {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin: 0;
  font-size: 1rem;
}
.summary-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--neon-blue, #1e90ff);
  box-shadow: 0 0 4px var(--neon-blue, #1e90ff);
}
.summary-actions {
  display: flex;
  gap: 0.5rem;
}
.ghost-btn {
  border: 1px solid var(--border);
  background: transparent;
  color: inherit;
  padding: 0.35rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
}
.ghost-btn:disabled {
  opacity: 0.5;
  cursor: default;
}
.progress-line {
  font-size: 0.85rem;
  opacity: 0.75;
  margin: 0.5rem 0 0;
}
.summary-body {
  margin: 0.75rem 0 0;
}
.summary-text {
  font-size: 17.6px;
}
.summary-edit {
  margin: 0.75rem 0 0;
}
.summary-textarea {
  width: 100%;
  box-sizing: border-box;
  padding: 0.6rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: 1.5;
  resize: vertical;
}
.summary-edit-actions {
  display: flex;
  gap: 0.5rem;
  margin-top: 0.5rem;
}
.summary-edit-actions button {
  padding: 0.4rem 1rem;
  border-radius: 6px;
  cursor: pointer;
  font: inherit;
}
.summary-edit-actions button[type="button"] {
  border: 1px solid var(--border);
  background: transparent;
  color: inherit;
}
.empty {
  margin: 0.75rem 0 0;
  opacity: 0.6;
  font-size: 0.9rem;
}
.chapters {
  list-style: none;
  padding-left: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}
.chapter-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-weight: 500;
}
.chapter-title-text {
  flex: 1;
  min-width: 0;
}
.chapter-title-plain {
  padding: 0.4rem 0.65rem;
}
.chapter-dot {
  flex-shrink: 0;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--neon-green, #39ff14);
  box-shadow: 0 0 4px var(--neon-green, #39ff14);
}
.chapter-status-pending {
  margin-left: 0.5rem;
  padding: 0.05rem 0.4rem;
  font-size: 0.7rem;
  border-radius: 999px;
  background: var(--warning-bg, rgba(245, 158, 11, 0.12));
  color: var(--warning, #f59e0b);
  line-height: 1.4;
  flex-shrink: 0;
}
.chapter-retry-btn {
  margin-left: auto;
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg);
  color: var(--text-h);
  cursor: pointer;
  transition: color 0.15s ease, border-color 0.15s ease;
}
.chapter-retry-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
}
.chapter-retry-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}
.chapter-retry-btn.is-loading svg {
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.chapter-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface, #fff);
  box-shadow: var(--elevation-1, 0 1px 2px rgba(0, 0, 0, 0.06));
  overflow: hidden;
}
.chapter-card summary {
  padding: 0.5rem 0.65rem;
  cursor: pointer;
  list-style: none;
}
.chapter-card summary::-webkit-details-marker {
  display: none;
}
.chapter-card:hover summary {
  background: var(--surface-hover);
}
.chapter-toggle-icon {
  flex-shrink: 0;
  opacity: 0.6;
  transition: transform 0.15s ease;
}
.chapter-card[open] .chapter-toggle-icon {
  transform: rotate(180deg);
}
.chapter-card .chapter-summary {
  margin: 0;
  padding: 0 0.65rem 0.65rem;
  border-top: 1px solid var(--border);
  padding-top: 0.5rem;
  font-size: 0.85rem;
  opacity: 0.85;
}
.chapter-card .chapter-extra {
  padding: 0 0.65rem 0.65rem;
}
.chapter-card .chapter-extra h3 {
  margin: 0 0 0.35rem;
  font-size: 0.75rem;
  font-weight: 600;
  opacity: 0.6;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: var(--code-bg);
}
/* Summarize/rebuild are the important actions on this page, not secondary
   ones, so they get the app's solid .primary treatment (see e.g.
   AdminAccountView.vue/UsersView.vue) rather than an outlined ghost button. */
button.primary {
  border: none;
  background: var(--accent);
  padding: 0.35rem 0.8rem;
  border-radius: 6px;
  cursor: pointer;
  color: white;
  font-size: 0.85rem;
  font-weight: 600;
  transition: background-color 0.15s ease;
}
button.primary:hover:not(:disabled) {
  background: color-mix(in srgb, var(--accent) 85%, black);
}
button.primary:disabled {
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
.token-card {
  margin: 1.5rem 0;
  padding: 1rem 1.25rem;
  border: 1px solid var(--border);
  border-radius: 10px;
}
.token-card h2 {
  margin: 0 0 0.75rem;
  font-size: 1rem;
}
.token-card h3 {
  margin: 1rem 0 0.5rem;
  font-size: 0.85rem;
  opacity: 0.7;
  font-weight: 500;
}
.token-loading,
.token-empty {
  font-size: 0.85rem;
  opacity: 0.6;
}
.token-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(110px, 1fr));
  gap: 0.75rem;
}
.token-stat {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
  padding: 0.5rem 0.6rem;
  border-radius: 6px;
  background: var(--code-bg);
}
.token-stat-label {
  font-size: 0.7rem;
  opacity: 0.65;
  text-transform: uppercase;
  letter-spacing: 0.03em;
}
.token-stat-value {
  font-size: 1.1rem;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--accent);
}
</style>
