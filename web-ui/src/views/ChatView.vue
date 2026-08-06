<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import * as chatApi from "../api/chat";
import * as booksApi from "../api/books";
import AppIcon from "../components/AppIcon.vue";

const { t } = useI18n();

const sessions = ref<chatApi.ChatSession[]>([]);
const activeSessionId = ref<string | null>(null);
const messages = ref<{ role: string; content: string; citations?: chatApi.Citation[] }[]>([]);
const input = ref("");
const sending = ref(false);
const loadingSessions = ref(true);

// Citations only carry book_id/chapter_id, not titles (see api/chat.ts) — this
// caches resolved book details (title + chapter list) per book_id so each
// unique book is only fetched once no matter how many citations reference it.
const bookCache = ref<Record<string, booksApi.BookDetail>>({});
const loadingBookIds = new Set<string>();

async function ensureBookLoaded(bookId: string) {
  if (bookCache.value[bookId] || loadingBookIds.has(bookId)) return;
  loadingBookIds.add(bookId);
  try {
    bookCache.value[bookId] = await booksApi.getBook(bookId);
  } catch {
    // Leave unresolved — the template falls back to showing the raw id.
  } finally {
    loadingBookIds.delete(bookId);
  }
}

function loadCitationBooks(citations: chatApi.Citation[]) {
  new Set(citations.map((c) => c.book_id)).forEach(ensureBookLoaded);
}

function citationBookTitle(c: chatApi.Citation): string {
  return bookCache.value[c.book_id]?.title ?? c.book_id;
}

function citationChapterTitle(c: chatApi.Citation): string {
  return bookCache.value[c.book_id]?.chapters.find((ch) => ch.id === c.chapter_id)?.title ?? c.chapter_id;
}

async function loadSessions() {
  loadingSessions.value = true;
  try {
    sessions.value = await chatApi.listSessions();
  } finally {
    loadingSessions.value = false;
  }
}

async function openSession(id: string) {
  activeSessionId.value = id;
  const detail = await chatApi.getSession(id);
  messages.value = detail.messages.map((m) => ({ role: m.role, content: m.content, citations: m.citations }));
  detail.messages.forEach((m) => m.citations?.length && loadCitationBooks(m.citations));
}

function newSession() {
  activeSessionId.value = null;
  messages.value = [];
}

function onComposerKeydown(e: KeyboardEvent) {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    onSend();
  }
}

async function onSend() {
  const text = input.value.trim();
  if (!text || sending.value) return;

  messages.value.push({ role: "user", content: text });
  messages.value.push({ role: "assistant", content: "" });
  input.value = "";
  sending.value = true;

  try {
    const { sessionId } = await chatApi.streamCompletion(
      activeSessionId.value,
      messages.value.slice(0, -1),
      [],
      (delta) => {
        messages.value[messages.value.length - 1].content += delta;
      },
      (citations) => {
        messages.value[messages.value.length - 1].citations = citations;
        loadCitationBooks(citations);
      },
    );
    if (!activeSessionId.value && sessionId) {
      activeSessionId.value = sessionId;
      await loadSessions();
    }
  } catch {
    messages.value[messages.value.length - 1].content = t("chat.error");
  } finally {
    sending.value = false;
  }
}

async function onDelete(id: string) {
  if (!confirm(t("common.confirmDelete"))) return;
  await chatApi.deleteSession(id);
  if (activeSessionId.value === id) newSession();
  await loadSessions();
}

const editingSessionId = ref<string | null>(null);
const editingTitle = ref("");

function startEdit(s: chatApi.ChatSession) {
  editingSessionId.value = s.id;
  editingTitle.value = s.title || "";
}

function cancelEdit() {
  editingSessionId.value = null;
}

async function saveEdit() {
  const id = editingSessionId.value;
  if (!id) return;
  const title = editingTitle.value.trim();
  editingSessionId.value = null;
  if (!title) return;
  const session = sessions.value.find((s) => s.id === id);
  if (session && session.title === title) return;
  await chatApi.renameSession(id, title);
  await loadSessions();
}

onMounted(loadSessions);
</script>

<template>
  <section class="chat-page">
    <aside class="sessions">
      <button class="new-session" @click="newSession">
        <AppIcon name="add" :size="18" />
        {{ t("chat.newSession") }}
      </button>
      <div v-if="loadingSessions">{{ t("common.loading") }}</div>
      <div v-else-if="!sessions.length" class="empty">{{ t("common.empty") }}</div>
      <div
        v-for="s in sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === activeSessionId }"
      >
        <input
          v-if="editingSessionId === s.id"
          v-model="editingTitle"
          class="session-title-input"
          :placeholder="t('chat.untitled')"
          autofocus
          @keydown.enter="saveEdit"
          @keydown.escape="cancelEdit"
          @blur="saveEdit"
          @click.stop
        />
        <span v-else class="session-title" @click="openSession(s.id)">{{ s.title || t("chat.untitled") }}</span>
        <span class="session-actions">
          <button
            class="icon-btn-sm"
            type="button"
            :title="t('common.edit')"
            :aria-label="t('common.edit')"
            @click.stop="startEdit(s)"
          >
            <AppIcon name="edit" :size="15" />
          </button>
          <button
            class="icon-btn-sm danger"
            type="button"
            :title="t('common.delete')"
            :aria-label="t('common.delete')"
            @click.stop="onDelete(s.id)"
          >
            <AppIcon name="trash" :size="15" />
          </button>
        </span>
      </div>
    </aside>

    <div class="thread">
      <div class="messages" :class="{ 'is-empty': !messages.length }">
        <div v-for="(m, i) in messages" :key="i" class="message" :class="m.role">
          <span v-if="m.role === 'assistant'" class="assistant-icon" :title="t('chat.assistant')">
            <span aria-hidden="true">✴</span>
            <span class="sr-only">{{ t("chat.assistant") }}</span>
          </span>
          <span
            v-if="m.role === 'assistant' && !m.content && sending && i === messages.length - 1"
            class="thinking-dots"
            :aria-label="t('chat.thinking')"
          >
            <span></span><span></span><span></span>
          </span>
          <p v-else>{{ m.content }}</p>
          <div v-if="m.citations?.length" class="citations">
            <details v-for="(c, ci) in m.citations" :key="c.chunk_id" class="citation-card">
              <summary>
                <span class="citation-index">{{ ci + 1 }}</span>
                <span class="citation-meta">
                  <span class="citation-book">{{ citationBookTitle(c) }}</span>
                  <span class="citation-chapter">{{ citationChapterTitle(c) }}</span>
                </span>
                <span class="citation-score">{{ Math.round(c.score * 100) }}%</span>
              </summary>
              <p class="citation-snippet">{{ c.content }}</p>
            </details>
          </div>
        </div>
        <p v-if="!messages.length" class="empty">{{ t("chat.emptyThread") }}</p>
      </div>
      <form class="composer-card" @submit.prevent="onSend">
        <textarea
          v-model="input"
          class="composer-input"
          rows="3"
          :placeholder="t('chat.placeholder')"
          :disabled="sending"
          @keydown="onComposerKeydown"
        ></textarea>
        <button
          class="composer-send"
          type="submit"
          :disabled="sending"
          :title="t('chat.send')"
          :aria-label="t('chat.send')"
        >
          <AppIcon name="arrowUp" :size="20" />
        </button>
      </form>
    </div>
  </section>
</template>

<style scoped>
.chat-page {
  display: flex;
  gap: 1.5rem;
  /* Fit exactly inside AppLayout's content area: viewport minus the app
     bar, the footer, and the .content padding (1.5rem top + bottom). */
  height: calc(100svh - var(--app-bar-height, 56px) - var(--footer-height, 40px) - 3rem);
  min-height: 0;
}
.sessions {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow-y: auto;
  padding-right: 1rem;
  border-right: 1px solid var(--border);
}
.new-session {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.4rem;
  padding: 0.5rem;
  border-radius: 999px;
  border: 1px solid var(--border);
  background: var(--accent-bg);
  color: var(--accent);
  cursor: pointer;
  font-weight: 600;
}
.session-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.25rem;
  padding: 0.4rem 0.5rem;
  border-radius: 6px;
}
.session-item.active,
.session-item:hover {
  background: var(--code-bg);
}
.session-title {
  cursor: pointer;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.session-title-input {
  flex: 1;
  min-width: 0;
  padding: 0.15rem 0.3rem;
  border: 1px solid var(--accent);
  border-radius: 4px;
  background: var(--surface, transparent);
  color: inherit;
  font: inherit;
}
.session-actions {
  display: flex;
  align-items: center;
  gap: 0.15rem;
  flex-shrink: 0;
  opacity: 0;
  transition: opacity 0.12s ease;
}
.session-item:hover .session-actions,
.session-item.active .session-actions {
  opacity: 1;
}
.icon-btn-sm {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  padding: 0;
  border: none;
  border-radius: 50%;
  background: transparent;
  color: inherit;
  opacity: 0.7;
  cursor: pointer;
}
.icon-btn-sm:hover {
  opacity: 1;
  background: var(--surface-hover);
}
.icon-btn-sm.danger {
  color: var(--danger, #e5484d);
}
.icon-btn-sm.danger:hover {
  background: color-mix(in srgb, var(--danger, #e5484d) 15%, transparent);
}
.thread {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-right: 0.5rem;
}
.messages.is-empty {
  justify-content: flex-end;
  align-items: center;
  text-align: center;
}
.message {
  padding: 0.6rem 0.8rem;
  border-radius: 8px;
  max-width: 80%;
}
.message p {
  margin: 0.25rem 0 0;
  white-space: pre-wrap;
}
.message.user {
  align-self: flex-end;
  background: var(--accent-bg);
}
.message.assistant {
  align-self: flex-start;
  background: var(--code-bg);
}
.assistant-icon {
  display: block;
  font-size: 18px;
  line-height: 1;
  opacity: 0.75;
}
.sr-only {
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
.thinking-dots {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  margin: 0.35rem 0 0;
}
.thinking-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  opacity: 0.4;
  animation: thinking-bounce 1s infinite ease-in-out;
}
.thinking-dots span:nth-child(2) {
  animation-delay: 0.15s;
}
.thinking-dots span:nth-child(3) {
  animation-delay: 0.3s;
}
@keyframes thinking-bounce {
  0%,
  80%,
  100% {
    opacity: 0.4;
    transform: translateY(0);
  }
  40% {
    opacity: 1;
    transform: translateY(-3px);
  }
}
.citations {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.6rem;
}
.citation-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface, #fff);
  box-shadow: var(--elevation-1, 0 1px 2px rgba(0, 0, 0, 0.06));
  overflow: hidden;
}
.citation-card summary {
  display: flex;
  align-items: center;
  gap: 0.55rem;
  padding: 0.4rem 0.65rem;
  cursor: pointer;
  list-style: none;
  font-size: 0.8rem;
}
.citation-card summary::-webkit-details-marker {
  display: none;
}
.citation-card:hover summary {
  background: var(--surface-hover);
}
.citation-index {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  background: var(--accent-bg);
  color: var(--accent);
  font-size: 0.7rem;
  font-weight: 700;
}
.citation-meta {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: 0.4rem;
  overflow: hidden;
}
.citation-book {
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.citation-chapter {
  opacity: 0.65;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-size: 0.75rem;
}
.citation-score {
  flex-shrink: 0;
  padding: 0.1rem 0.45rem;
  border-radius: 999px;
  background: var(--code-bg);
  font-size: 0.7rem;
  opacity: 0.75;
}
.citation-snippet {
  margin: 0;
  padding: 0.5rem 0.65rem 0.65rem;
  border-top: 1px solid var(--border);
  font-size: 0.8rem;
  line-height: 1.5;
  opacity: 0.85;
  white-space: pre-wrap;
}
.composer-card {
  position: relative;
  flex-shrink: 0;
  display: flex;
  margin-top: 1rem;
  padding: 0.75rem 5.5rem 0.75rem 1rem;
  border: 1px solid var(--border);
  border-radius: 1.5rem;
  background: var(--surface, transparent);
}
.composer-input {
  flex: 1;
  min-height: calc(1.4em * 3);
  resize: none;
  border: none;
  outline: none;
  background: transparent;
  color: inherit;
  font: inherit;
  line-height: 1.4;
  padding: 0.3rem 0;
}
.composer-send {
  position: absolute;
  right: 1rem;
  bottom: 0.75rem;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  padding: 0;
  border-radius: 50%;
  border: none;
  background: var(--accent);
  color: white;
  cursor: pointer;
}
.composer-send:disabled {
  opacity: 0.6;
  cursor: default;
}
.empty {
  opacity: 0.6;
  font-size: 0.9rem;
}
</style>
