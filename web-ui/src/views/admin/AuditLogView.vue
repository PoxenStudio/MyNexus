<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { listAuditLog, type AuditLogEntry } from "../../api/audit";

const { t } = useI18n();
const entries = ref<AuditLogEntry[]>([]);
const loading = ref(true);

async function load() {
  loading.value = true;
  try {
    const res = await listAuditLog({ size: 100 });
    entries.value = res.items;
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <section>
    <h1>{{ t("audit.title") }}</h1>
    <button class="ghost" @click="load">{{ t("common.refresh") }}</button>

    <div v-if="loading">{{ t("common.loading") }}</div>
    <table v-else-if="entries.length">
      <thead>
        <tr>
          <th>{{ t("audit.table.time") }}</th>
          <th>{{ t("audit.table.actor") }}</th>
          <th>{{ t("audit.table.action") }}</th>
          <th>{{ t("audit.table.target") }}</th>
          <th>{{ t("audit.table.detail") }}</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="e in entries" :key="e.id">
          <td>{{ new Date(e.created_at).toLocaleString() }}</td>
          <td class="mono">{{ e.actor }}</td>
          <td class="mono">{{ e.action }}</td>
          <td class="mono">{{ e.target_type }}{{ e.target_id ? ":" + e.target_id.slice(0, 8) : "" }}</td>
          <td>{{ e.detail }}</td>
        </tr>
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
.mono {
  font-family: var(--mono);
  font-size: 0.8rem;
}
button.ghost {
  border: 1px solid var(--border);
  background: transparent;
  padding: 0.3rem 0.6rem;
  border-radius: 6px;
  cursor: pointer;
  color: inherit;
}
</style>
