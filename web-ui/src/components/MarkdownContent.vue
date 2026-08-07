<script setup lang="ts">
// Renders LLM-generated markdown (chapter/book summaries, chat replies —
// see docs discussion on worker/src/pipelines/summary.py) as sanitized HTML.
// The text itself is never cleaned of newlines/markdown syntax anywhere in
// the pipeline (worker -> gRPC -> core-api -> DB), so what breaks formatting
// is a *display* rendering it as plain text; this component is the fix.
import DOMPurify from "dompurify";
import { marked } from "marked";
import { computed } from "vue";

const props = defineProps<{ content: string }>();

marked.setOptions({ breaks: true, gfm: true });

const html = computed(() => DOMPurify.sanitize(marked.parse(props.content || "", { async: false })));
</script>

<template>
  <div class="markdown-content" v-html="html"></div>
</template>

<style scoped>
.markdown-content {
  line-height: 1.6;
  word-break: break-word;
}
.markdown-content :deep(> :first-child) {
  margin-top: 0;
}
.markdown-content :deep(> :last-child) {
  margin-bottom: 0;
}
.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3),
.markdown-content :deep(h4) {
  margin: 1rem 0 0.5rem;
  line-height: 1.3;
}
.markdown-content :deep(h1) {
  font-size: 1.3em;
}
.markdown-content :deep(h2) {
  font-size: 1.15em;
}
.markdown-content :deep(h3) {
  font-size: 1.05em;
}
.markdown-content :deep(p) {
  margin: 0.6rem 0;
}
.markdown-content :deep(ul),
.markdown-content :deep(ol) {
  margin: 0.6rem 0;
  padding-left: 1.4rem;
}
.markdown-content :deep(li) {
  margin: 0.2rem 0;
}
.markdown-content :deep(strong) {
  font-weight: 700;
}
.markdown-content :deep(a) {
  color: var(--accent);
}
.markdown-content :deep(blockquote) {
  margin: 0.6rem 0;
  padding: 0.1rem 0.8rem;
  border-left: 3px solid var(--border);
  opacity: 0.85;
}
.markdown-content :deep(code) {
  padding: 0.1rem 0.3rem;
  border-radius: 4px;
  background: var(--code-bg);
  font-size: 0.9em;
}
.markdown-content :deep(pre) {
  margin: 0.6rem 0;
  padding: 0.6rem 0.8rem;
  border-radius: 8px;
  background: var(--code-bg);
  overflow-x: auto;
}
.markdown-content :deep(pre code) {
  padding: 0;
  background: none;
}
.markdown-content :deep(table) {
  border-collapse: collapse;
  margin: 0.6rem 0;
  max-width: 100%;
  display: block;
  overflow-x: auto;
}
.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid var(--border);
  padding: 0.3rem 0.6rem;
}
.markdown-content :deep(hr) {
  margin: 0.8rem 0;
  border: none;
  border-top: 1px solid var(--border);
}
</style>
