import { ref } from "vue";

// Lets a view append page-specific context (e.g. a book's title) to the tab
// title without owning document.title itself — App.vue still derives the
// base "MyNexus | <section>" string from route.meta.titleKey and appends
// this suffix when present. Views must clear it in onUnmounted so stale
// suffixes don't leak into the next page.
export const pageTitleSuffix = ref<string | null>(null);

export function setPageTitleSuffix(suffix: string | null) {
  pageTitleSuffix.value = suffix;
}
