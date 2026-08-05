<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { listTasks, retryTask, type Task } from "../../api/tasks";

const { t } = useI18n();
const tasks = ref<Task[]>([]);
const loading = ref(true);
const retrying = ref<string | null>(null);
const expanded = ref<string | null>(null);

async function load() {
  loading.value = true;
  try {
    const res = await listTasks({ size: 100 });
    tasks.value = res.items;
  } finally {
    loading.value = false;
  }
}

async function onRetry(id: string) {
  retrying.value = id;
  try {
    await retryTask(id);
    await load();
  } finally {
    retrying.value = null;
  }
}

function toggleExpand(id: string) {
  expanded.value = expanded.value === id ? null : id;
}

onMounted(load);
</script>

<template>
  <section>
    <h1>{{ t("tasks.title") }}</h1>
    <button class="ghost" @click="load">{{ t("common.refresh") }}</button>

    <div v-if="loading">{{ t("common.loading") }}</div>
    <table v-else-if="tasks.length">
      <thead>
        <tr>
          <th>{{ t("tasks.table.id") }}</th>
          <th>{{ t("tasks.table.bookId") }}</th>
          <th>{{ t("tasks.table.status") }}</th>
          <th>{{ t("tasks.table.progress") }}</th>
          <th>{{ t("tasks.table.error") }}</th>
          <th>{{ t("tasks.table.updatedAt") }}</th>
          <th>{{ t("tasks.table.actions") }}</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="task in tasks" :key="task.id">
          <tr class="row" @click="toggleExpand(task.id)">
            <td class="mono">{{ task.id.slice(0, 8) }}</td>
            <td class="mono">{{ task.book_id.slice(0, 8) }}</td>
            <td><span :class="['badge', task.status]">{{ t(`status.${task.status}`, task.status) }}</span></td>
            <td>{{ task.progress }}%</td>
            <td class="error">{{ task.error_msg }}</td>
            <td>{{ new Date(task.updated_at).toLocaleString() }}</td>
            <td>
              <button
                v-if="task.status === 'failed'"
                class="ghost"
                :disabled="retrying === task.id"
                @click.stop="onRetry(task.id)"
              >
                {{ t("common.retry") }}
              </button>
            </td>
          </tr>
          <tr v-if="expanded === task.id" class="log-row">
            <td colspan="7">
              <ol v-if="task.stages_log?.length" class="stage-log">
                <li v-for="(entry, i) in task.stages_log" :key="i">
                  <span class="stage-name">{{ entry.stage }}</span>
                  <span class="stage-progress">{{ entry.progress }}%</span>
                  <span v-if="entry.message" class="stage-message">{{ entry.message }}</span>
                  <span class="stage-time">{{ new Date(entry.at).toLocaleString() }}</span>
                </li>
              </ol>
              <p v-else class="empty">{{ t("tasks.noStages") }}</p>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
    <p v-else>{{ t("common.empty") }}</p>
  </section>
</template>

<style scoped>
table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 1rem;
}
th, td {
  text-align: left;
  padding: 0.5rem 0.75rem;
  border-bottom: 1px solid var(--border);
  font-size: 0.9rem;
}
.row {
  cursor: pointer;
}
.row:hover {
  background: var(--code-bg);
}
.mono {
  font-family: var(--mono);
  font-size: 0.8rem;
}
.error {
  color: #dc2626;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.badge {
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  background: var(--code-bg);
}
.badge.completed, .badge.ready { color: #16a34a; }
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
button.ghost:disabled {
  opacity: 0.5;
  cursor: default;
}
.log-row td {
  background: var(--code-bg);
}
.stage-log {
  margin: 0;
  padding-left: 1.25rem;
  display: flex;
  flex-direction: column;
  gap: 0.35rem;
  font-size: 0.85rem;
}
.stage-log li {
  display: flex;
  gap: 0.75rem;
  align-items: baseline;
}
.stage-name {
  font-weight: 600;
}
.stage-progress {
  opacity: 0.7;
}
.stage-message {
  color: #dc2626;
}
.stage-time {
  margin-left: auto;
  opacity: 0.6;
  font-size: 0.8rem;
}
.empty {
  margin: 0;
  opacity: 0.6;
  font-size: 0.85rem;
}
</style>
