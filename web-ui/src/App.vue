<script setup lang="ts">
import { watchEffect } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { pageTitleSuffix } from "./composables/pageTitle";

const { t, locale } = useI18n();
const route = useRoute();

// Re-derive on every route change and every locale switch so the tab title
// stays in sync with both (a plain router.afterEach would miss locale-only
// changes since it only fires on navigation). pageTitleSuffix lets a view
// (e.g. book detail) append page-specific context, like "详情 - 三体".
watchEffect(() => {
  locale.value; // establish reactive dependency
  const titleKey = route.meta.titleKey as string | undefined;
  const base = titleKey ? `MyNexus | ${t(titleKey)}` : "MyNexus";
  document.title = pageTitleSuffix.value ? `${base} - ${pageTitleSuffix.value}` : base;
});
</script>

<template>
  <router-view />
</template>
