<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";

const props = defineProps<{
  markdown: string;
  title?: string;
}>();

const transformer = new Transformer();
const svgRef = ref<SVGSVGElement | null>(null);
const mm = shallowRef<Markmap | null>(null);

const root = computed(() => {
  if (!props.markdown) return null;
  return transformer.transform(props.markdown).root;
});

function render() {
  if (!svgRef.value || !root.value) return;
  if (mm.value) {
    mm.value.setData(root.value);
    mm.value.fit();
    return;
  }
  mm.value = Markmap.create(
    svgRef.value,
    { autoFit: true, fitRatio: 0.8, duration: 300, maxWidth: 300, paddingX: 16 },
    root.value,
  );
}

function fit() {
  mm.value?.fit();
}

function download() {
  if (!svgRef.value) return;
  const g = svgRef.value.querySelector("g");
  let x = -500, y = -500, w = 2000, h = 1500;
  if (g) {
    try {
      const bbox = g.getBBox();
      const pad = 50;
      x = bbox.x - pad;
      y = bbox.y - pad;
      w = bbox.width + pad * 2;
      h = bbox.height + pad * 2;
    } catch {}
  }
  const clone = svgRef.value.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
  clone.setAttribute("width", String(w));
  clone.setAttribute("height", String(h));
  clone.style.width = "";
  clone.style.height = "";
  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("x", String(x));
  bg.setAttribute("y", String(y));
  bg.setAttribute("width", String(w));
  bg.setAttribute("height", String(h));
  bg.setAttribute("fill", "#fff");
  clone.insertBefore(bg, clone.firstChild);
  let data = new XMLSerializer().serializeToString(clone);
  data = data.replace(/var\(--foreground\)/g, "#333").replace(/var\(--background\)/g, "#fff").replace(/var\(--muted\)/g, "#f5f5f5");
  const blob = new Blob([data], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${props.title || "mindmap"}.svg`;
  a.click();
  URL.revokeObjectURL(url);
}

onMounted(render);
watch(root, render);
onBeforeUnmount(() => {
  mm.value?.destroy?.();
});
</script>

<template>
  <div class="mindmap-wrap">
    <div class="mindmap-header">
      <span class="mindmap-title">{{ title || "思维导图" }}</span>
      <div class="mindmap-actions">
        <button type="button" class="mm-btn" title="复原" @click="fit">↺</button>
        <button type="button" class="mm-btn" title="下载 SVG" @click="download">⬇</button>
      </div>
    </div>
    <div class="mindmap-body" data-mindmap="true">
      <svg ref="svgRef" class="mindmap-svg" />
    </div>
  </div>
</template>

<style scoped>
.mindmap-wrap {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface, #fff);
  overflow: hidden;
  margin-top: 0.5rem;
}
.mindmap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border);
  background: var(--code-bg, #f5f5f5);
}
.mindmap-title {
  font-size: 0.85rem;
  font-weight: 600;
  opacity: 0.8;
}
.mindmap-actions {
  display: flex;
  gap: 0.25rem;
}
.mm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: inherit;
  cursor: pointer;
  font-size: 14px;
}
.mm-btn:hover {
  background: var(--surface-hover, rgba(0, 0, 0, 0.06));
}
.mindmap-body {
  height: 380px;
  overflow: hidden;
}
.mindmap-svg {
  width: 100%;
  height: 100%;
}
</style>
