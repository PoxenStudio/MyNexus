<script setup lang="ts">
import { onMounted, ref } from "vue";
import { fetchHealth, type SystemHealth } from "../api/system";

const health = ref<SystemHealth | null>(null);
const error = ref("");

onMounted(async () => {
  try {
    health.value = await fetchHealth();
  } catch (e) {
    error.value = "无法连接 Core API，请确认服务已启动";
  }
});
</script>

<template>
  <section>
    <h1>MyNexus</h1>
    <p>项目骨架已初始化。</p>
    <p v-if="health">
      Core API 状态：<strong>{{ health.status }}</strong>
      （database: {{ health.database }}）
    </p>
    <p v-else-if="error" class="error">{{ error }}</p>
    <p v-else>加载中...</p>
  </section>
</template>

<style scoped>
.error {
  color: #c0392b;
}
</style>
