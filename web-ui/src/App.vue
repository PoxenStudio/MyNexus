<script setup lang="ts">
import { watchEffect } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

const { t, locale } = useI18n();
const route = useRoute();

// Re-derive on every route change and every locale switch so the tab title
// stays in sync with both (a plain router.afterEach would miss locale-only
// changes since it only fires on navigation).
watchEffect(() => {
  locale.value; // establish reactive dependency
  const titleKey = route.meta.titleKey as string | undefined;
  document.title = titleKey ? `MyNexus | ${t(titleKey)}` : "MyNexus";
});
</script>

<template>
  <router-view />
</template>
