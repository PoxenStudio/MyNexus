<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import * as chatApi from "../api/chat";

const { t } = useI18n();

const sessions = ref<chatApi.ChatSession[]>([]);
const activeSessionId = ref<string | null>(null);
const messages = ref<{ role: string; content: string }[]>([]);
const input = ref("");
const sending = ref(false);
const loadingSessions = ref(true);

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
  messages.value = detail.messages.map((m) => ({ role: m.role, content: m.content }));
}

function newSession() {
  activeSessionId.value = null;
  messages.value = [];
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

onMounted(loadSessions);
</script>

<template>
  <section class="chat-page">
    <aside class="sessions">
      <button class="new-session" @click="newSession">{{ t("chat.newSession") }}</button>
      <div v-if="loadingSessions">{{ t("common.loading") }}</div>
      <div v-else-if="!sessions.length" class="empty">{{ t("common.empty") }}</div>
      <div
        v-for="s in sessions"
        :key="s.id"
        class="session-item"
        :class="{ active: s.id === activeSessionId }"
      >
        <span class="session-title" @click="openSession(s.id)">{{ s.title || t("chat.untitled") }}</span>
        <button class="ghost" @click="onDelete(s.id)">{{ t("common.delete") }}</button>
      </div>
    </aside>

    <div class="thread">
      <div class="messages">
        <div v-for="(m, i) in messages" :key="i" class="message" :class="m.role">
          <strong>{{ m.role === "user" ? t("chat.you") : t("chat.assistant") }}</strong>
          <p>{{ m.content }}</p>
        </div>
        <p v-if="!messages.length" class="empty">{{ t("chat.emptyThread") }}</p>
      </div>
      <form class="composer" @submit.prevent="onSend">
        <input v-model="input" :placeholder="t('chat.placeholder')" :disabled="sending" />
        <button type="submit" :disabled="sending">{{ t("chat.send") }}</button>
      </form>
    </div>
  </section>
</template>

<style scoped>
.chat-page {
  display: flex;
  gap: 1.5rem;
  height: calc(100vh - 3rem);
}
.sessions {
  width: 220px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  overflow-y: auto;
}
.new-session {
  padding: 0.5rem;
  border-radius: 6px;
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
.thread {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.messages {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  padding-right: 0.5rem;
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
.composer {
  display: flex;
  gap: 0.5rem;
  margin-top: 1rem;
}
.composer input {
  flex: 1;
  padding: 0.6rem 0.8rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: transparent;
  color: inherit;
}
.composer button {
  padding: 0.6rem 1.2rem;
  border-radius: 6px;
  border: none;
  background: var(--accent);
  color: white;
  cursor: pointer;
  font-weight: 600;
}
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.2rem 0.5rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
  font-size: 0.8rem;
}
.empty {
  opacity: 0.6;
  font-size: 0.9rem;
}
</style>
