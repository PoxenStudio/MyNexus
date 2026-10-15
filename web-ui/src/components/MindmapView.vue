<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { Transformer } from "markmap-lib";
import { Markmap } from "markmap-view";
import { useThemeStore } from "../stores/theme";

const props = defineProps<{
  markdown: string;
  title?: string;
}>();

const theme = useThemeStore();
const isDark = computed(() => theme.mode === "dark");

const transformer = new Transformer();
const svgRef = ref<SVGSVGElement | null>(null);
const modalSvgRef = ref<SVGSVGElement | null>(null);
const mm = shallowRef<Markmap | null>(null);
const modalMm = shallowRef<Markmap | null>(null);
const expanded = ref(false);

const root = computed(() => {
  if (!props.markdown) return null;
  return transformer.transform(props.markdown).root;
});

const MM_OPTIONS = { autoFit: true, fitRatio: 0.85, duration: 300, maxWidth: 320, paddingX: 16 };

function render() {
  if (!svgRef.value || !root.value) return;
  if (mm.value) {
    mm.value.setData(root.value);
    mm.value.fit();
    return;
  }
  mm.value = Markmap.create(svgRef.value, MM_OPTIONS, root.value);
}

function renderModal() {
  if (!modalSvgRef.value || !root.value) return;
  modalMm.value?.destroy?.();
  modalMm.value = Markmap.create(modalSvgRef.value, MM_OPTIONS, root.value);
}

function fit(target: Markmap | null = mm.value) {
  target?.fit();
}

function openModal() {
  expanded.value = true;
  document.addEventListener("keydown", onKeydown);
  window.addEventListener("resize", onResize);
  nextTick(renderModal);
}

function closeModal() {
  expanded.value = false;
  document.removeEventListener("keydown", onKeydown);
  window.removeEventListener("resize", onResize);
  modalMm.value?.destroy?.();
  modalMm.value = null;
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === "Escape") closeModal();
}

function onResize() {
  fit(modalMm.value);
}

function download(target?: SVGSVGElement | null) {
  const svg = target ?? svgRef.value;
  if (!svg) return;
  const g = svg.querySelector("g");
  let x = -600, y = -600, w = 2400, h = 1800;
  if (g) {
    try {
      const bbox = g.getBBox();
      const pad = 60;
      x = bbox.x - pad;
      y = bbox.y - pad;
      w = bbox.width + pad * 2;
      h = bbox.height + pad * 2;
    } catch {
      // keep defaults if the svg is not laid out
    }
  }
  const clone = svg.cloneNode(true) as SVGSVGElement;
  clone.setAttribute("viewBox", `${x} ${y} ${w} ${h}`);
  clone.setAttribute("width", String(w));
  clone.setAttribute("height", String(h));
  clone.style.width = "";
  clone.style.height = "";
  clone.classList.remove("markmap-dark");
  const bg = document.createElementNS("http://www.w3.org/2000/svg", "rect");
  bg.setAttribute("x", String(x));
  bg.setAttribute("y", String(y));
  bg.setAttribute("width", String(w));
  bg.setAttribute("height", String(h));
  bg.setAttribute("fill", "#ffffff");
  clone.insertBefore(bg, clone.firstChild);
  const fix = (s: string) =>
    s
      .replace(/var\(--foreground\)/g, "#333")
      .replace(/var\(--background\)/g, "#fff")
      .replace(/var\(--muted\)/g, "#f5f5f5")
      .replace(/var\(--markmap-text-color[^)]*\)/g, "#333")
      .replace(/var\(--markmap-a-color[^)]*\)/g, "#0097e6")
      .replace(/var\(--markmap-code-bg[^)]*\)/g, "#f0f0f0")
      .replace(/var\(--markmap-code-color[^)]*\)/g, "#555")
      .replace(/var\(--markmap-circle-open-bg[^)]*\)/g, "#fff");
  const data = fix(new XMLSerializer().serializeToString(clone));
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
  closeModal();
});
</script>

<template>
  <div class="mindmap-wrap" :class="{ 'markmap-dark': isDark }">
    <div class="mindmap-header">
      <span class="mindmap-title">{{ title || "思维导图" }}</span>
      <div class="mindmap-actions">
        <button type="button" class="mm-btn" title="复原" @click="fit()">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="1 4 1 10 7 10" />
            <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
          </svg>
        </button>
        <button type="button" class="mm-btn" title="放大显示" @click="openModal">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <polyline points="15 3 21 3 21 9" />
            <polyline points="9 21 3 21 3 15" />
            <line x1="21" y1="3" x2="14" y2="10" />
            <line x1="3" y1="21" x2="10" y2="14" />
          </svg>
        </button>
        <button type="button" class="mm-btn" title="下载 SVG" @click="download()">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
        </button>
      </div>
    </div>
    <div class="mindmap-body">
      <svg ref="svgRef" class="mindmap-svg" />
    </div>
  </div>

  <Teleport to="body">
    <div v-if="expanded" class="mm-overlay" @click.self="closeModal">
      <div class="mm-modal" :class="{ 'markmap-dark': isDark }">
        <div class="mindmap-header mm-modal-header">
          <span class="mindmap-title">{{ title || "思维导图" }}</span>
          <div class="mindmap-actions">
            <button type="button" class="mm-btn" title="复原" @click="fit(modalMm)">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="1 4 1 10 7 10" />
                <path d="M3.51 15a9 9 0 1 0 2.13-9.36L1 10" />
              </svg>
            </button>
            <button type="button" class="mm-btn" title="下载 SVG" @click="download(modalSvgRef)">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="7 10 12 15 17 10" />
                <line x1="12" y1="15" x2="12" y2="3" />
              </svg>
            </button>
            <button type="button" class="mm-btn" title="关闭 (Esc)" @click="closeModal">
              <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18" />
                <line x1="6" y1="6" x2="18" y2="18" />
              </svg>
            </button>
          </div>
        </div>
        <div class="mm-modal-body">
          <svg ref="modalSvgRef" class="mindmap-svg" />
        </div>
        <div class="mm-modal-footer">双击放大 · 拖动移动 · 滚轮缩放 · 点击节点展开/收起 · Esc 关闭</div>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.mindmap-wrap {
  border: 1px solid var(--border);
  border-radius: 10px;
  background: var(--surface);
  overflow: hidden;
  margin-top: 0.5rem;
}
.mindmap-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.4rem 0.6rem;
  border-bottom: 1px solid var(--border);
  background: var(--surface-variant);
}
.mindmap-title {
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text);
}
.mindmap-actions {
  display: flex;
  gap: 0.15rem;
}
.mm-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 6px;
  background: transparent;
  color: var(--text);
  opacity: 0.7;
  cursor: pointer;
}
.mm-btn:hover {
  background: var(--surface-hover);
  opacity: 1;
}
.mindmap-body {
  height: 380px;
  overflow: hidden;
}
.mindmap-svg {
  width: 100%;
  height: 100%;
}

.mm-overlay {
  position: fixed;
  inset: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.55);
  backdrop-filter: blur(2px);
}
.mm-modal {
  width: 75vw;
  height: 75vh;
  display: flex;
  flex-direction: column;
  border: 1px solid var(--border);
  border-radius: 12px;
  background: var(--surface);
  box-shadow: var(--shadow);
  overflow: hidden;
}
.mm-modal-header {
  flex: 0 0 auto;
}
.mm-modal-body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
}
.mm-modal-footer {
  flex: 0 0 auto;
  padding: 0.35rem 0.75rem;
  border-top: 1px solid var(--border);
  font-size: 0.72rem;
  color: var(--text);
  opacity: 0.55;
}
</style>
