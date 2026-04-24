<script setup lang="ts">
/**
 * The drag-and-drop dashboard grid. Renders the visible widget cards via
 * grid-layout-plus with per-project layouts persisted in localStorage.
 *
 * View mode (default): no drag, no handles, no resize — page looks and
 *   feels like a static dashboard.
 * Edit mode (toggle with the pencil button in the bar): drag any card by
 *   its header, resize from the bottom-right corner, click × to hide a
 *   card, right-click for a context menu (pin size, duplicate size,
 *   remove, restore-all), open the "+ add widget" popover to bring hidden
 *   cards back.
 */
import { computed, onBeforeUnmount, ref, watch, nextTick } from "vue";
import { GridLayout } from "grid-layout-plus";

import { useDashboardLayoutStore } from "@/stores/dashboard-layout";
import { DEFAULT_LAYOUT, widgetById } from "./widget-registry";

// Grid spacing constants — match the <GridLayout> props below so the
// auto-sizer's math reproduces grid-layout-plus's own geometry.
const ROW_HEIGHT = 40;
const MARGIN_V = 16;

const props = defineProps<{ project: { slug: string; [k: string]: unknown } }>();

const store = useDashboardLayoutStore();

// Hydrate the layout for the current project on mount + on slug change.
watch(
  () => props.project.slug,
  (slug) => store.hydrate(slug, DEFAULT_LAYOUT),
  { immediate: true },
);

// Hidden widget pool (shown in the "+ add widget" menu).
const hiddenWidgets = computed(() =>
  store.layout
    .filter((l) => l.hidden)
    .map((l) => widgetById(l.i))
    .filter((w): w is NonNullable<typeof w> => Boolean(w)),
);

// ── Context menu (right-click on a widget) ────────────────────────────────
interface MenuState {
  x: number;
  y: number;
  widgetId: string;
}
const contextMenu = ref<MenuState | null>(null);

function onWidgetContextMenu(e: MouseEvent, widgetId: string) {
  if (!store.editMode) return;
  e.preventDefault();
  contextMenu.value = { x: e.clientX, y: e.clientY, widgetId };
}
function closeContextMenu() {
  contextMenu.value = null;
}
function onGlobalClick() {
  if (contextMenu.value) closeContextMenu();
}
// Close context menu on any outside click.
window.addEventListener("click", onGlobalClick);
onBeforeUnmount(() => window.removeEventListener("click", onGlobalClick));

// Convenient sizing presets from the context menu. Any explicit size pick
// counts as user-driven, so lock the auto-sizer for that widget.
function resize(id: string, w: number, h: number) {
  const widget = store.layout.find((l) => l.i === id);
  if (!widget) return;
  widget.w = Math.max(widget.minW ?? 1, w);
  widget.h = Math.max(widget.minH ?? 1, h);
  userSized.value.add(id);
  closeContextMenu();
}
function setFullWidth(id: string) {
  const widget = store.layout.find((l) => l.i === id);
  if (!widget) return;
  widget.w = 12;
  widget.x = 0;
  userSized.value.add(id);
  closeContextMenu();
}
function removeWidget(id: string) {
  store.hideWidget(id);
  closeContextMenu();
}
function restoreDefaults() {
  if (!confirm("Reset the dashboard layout to factory defaults?")) return;
  store.resetToDefault(DEFAULT_LAYOUT);
  contextMenu.value = null;
  addMenuOpen.value = false;
}

// ── "+ Add widget" popover ─────────────────────────────────────────────────
const addMenuOpen = ref(false);

function addWidget(id: string) {
  store.showWidget(id);
  addMenuOpen.value = false;
  // Freshly-shown widget should size to content, not keep its stale h.
  userSized.value.delete(id);
  nextTick(() => autoFit(id));
}

// ── Auto-sizing ────────────────────────────────────────────────────────────
//
// Every widget gets a ResizeObserver on its measured-content element.
// When that content's natural height doesn't match the grid cell height,
// we update layout[i].h so the cell hugs the content exactly — no more
// "big empty glass box below short content" problem.
//
// Auto-sizing stops for a widget the moment the user manually resizes it
// (tracked in `userSized`). That way dragging the corner to set a custom
// height sticks. `addWidget` clears the flag so re-added widgets go back
// to auto-fit by default.
//
// A per-widget debounce prevents resize → layout-change → re-measure →
// resize feedback loops. 60ms is enough to settle Vue's render cycle.

const contentEls = new Map<string, HTMLElement>();
const observers = new Map<string, ResizeObserver>();
const fitTimers = new Map<string, ReturnType<typeof setTimeout>>();
const userSized = ref<Set<string>>(new Set());
// Widgets whose h the auto-sizer is about to update. The layout-watch
// below uses this to distinguish our own programmatic h changes from
// changes driven by user resize.
const autoFittingIds = new Set<string>();

function registerContentEl(id: string, el: HTMLElement | null): void {
  if (!el) {
    const existing = observers.get(id);
    if (existing) { existing.disconnect(); observers.delete(id); }
    contentEls.delete(id);
    return;
  }
  contentEls.set(id, el);
  if (!observers.has(id)) {
    const ro = new ResizeObserver(() => scheduleAutoFit(id));
    ro.observe(el);
    observers.set(id, ro);
    scheduleAutoFit(id);
  }
}

function scheduleAutoFit(id: string): void {
  const existing = fitTimers.get(id);
  if (existing) clearTimeout(existing);
  fitTimers.set(id, setTimeout(() => {
    fitTimers.delete(id);
    autoFit(id);
  }, 60));
}

function autoFit(id: string): void {
  if (userSized.value.has(id)) return;
  const el = contentEls.get(id);
  if (!el) return;
  const measured = el.scrollHeight;
  if (measured === 0) return;
  // Inverse of grid-layout-plus's cell formula:
  //   cellHeight = h * ROW_HEIGHT + (h - 1) * MARGIN_V
  //   ⇒ h = (cellHeight + MARGIN_V) / (ROW_HEIGHT + MARGIN_V)
  const desiredH = Math.max(
    3,
    Math.ceil((measured + MARGIN_V) / (ROW_HEIGHT + MARGIN_V)),
  );
  const item = store.layout.find((l) => l.i === id);
  if (item && item.h !== desiredH) {
    // Mark this h change as self-authored so the layout watch below
    // doesn't misattribute it to a user resize.
    autoFittingIds.add(id);
    item.h = desiredH;
    // Clear on the NEXT tick. Double-nextTick is paranoid but cheap —
    // gives grid-layout-plus a frame to paint before we stop guarding.
    nextTick(() => nextTick(() => { autoFittingIds.delete(id); }));
  }
}

// Layout watcher. grid-layout-plus's `@item-resized` event is a Vue-2
// emit-style that doesn't always reach us when using the slot pattern.
// Instead we watch store.layout directly: whenever h or w for a widget
// changes AND it isn't flagged as an auto-fit update, we assume the
// user did it — that's when we lock auto-sizing for that widget.
let lastSnapshot = new Map<string, { h: number; w: number }>();
watch(
  () => store.layout.map((l) => ({ i: String(l.i), h: l.h, w: l.w })),
  (next) => {
    const nextMap = new Map(next.map((n) => [n.i, { h: n.h, w: n.w }]));
    for (const [id, now] of nextMap) {
      const prev = lastSnapshot.get(id);
      if (prev && (prev.h !== now.h || prev.w !== now.w)) {
        if (!autoFittingIds.has(id)) {
          userSized.value.add(id);
        }
      }
    }
    lastSnapshot = nextMap;
  },
  { deep: true, immediate: true, flush: "post" },
);

function onItemResized(i: string | number): void {
  // Kept as a safety-net handler in case grid-layout-plus's event does
  // fire — the watcher above is the primary detection path.
  userSized.value.add(String(i));
}

onBeforeUnmount(() => {
  observers.forEach((ro) => ro.disconnect());
  observers.clear();
  fitTimers.forEach((t) => clearTimeout(t));
  fitTimers.clear();
});

// Re-enable auto-fit for a widget (from the right-click menu).
function autoSizeAgain(id: string): void {
  userSized.value.delete(id);
  scheduleAutoFit(id);
  closeContextMenu();
}
</script>

<template>
  <div class="relative">
    <!-- ── Dashboard toolbar ──────────────────────────────────────────────
         Always visible. In view mode it's a slim page-header band with the
         "//dashboard" label on the left and a single "rearrange" button on
         the right. In edit mode it expands with add-widget / reset / hint.
         Same outer box in both modes so the page doesn't jump when toggling. -->
    <header
      class="sticky top-[44px] z-20 flex items-center gap-3 mb-4 px-3 h-10 rounded-md transition-colors"
      :style="store.editMode
        ? 'background: rgba(92,200,164,0.06); border: 1px solid rgba(92,200,164,0.25); backdrop-filter: blur(8px)'
        : 'background: rgba(13,18,26,0.55); border: 1px solid var(--border-subtle); backdrop-filter: blur(8px)'"
    >
      <span class="mono-label text-fg-muted">// dashboard</span>
      <span v-if="store.editMode" class="text-[11px] text-signal-green font-mono">— edit mode</span>

      <!-- Edit-only: add widget + reset + hint (all pushed right of label) -->
      <template v-if="store.editMode">
        <div class="relative" @click.stop>
          <button
            type="button"
            class="flex items-center gap-2 h-7 px-2.5 rounded-md text-small font-mono border border-border hover:border-signal-green/60 hover:text-fg-body text-fg-muted transition-colors"
            :disabled="hiddenWidgets.length === 0"
            @click="addMenuOpen = !addMenuOpen"
          >
            <span aria-hidden="true">+</span>
            <span>add widget</span>
            <span v-if="hiddenWidgets.length > 0" class="text-fg-subtle">({{ hiddenWidgets.length }})</span>
          </button>
          <transition
            enter-active-class="transition ease-out duration-100"
            enter-from-class="opacity-0 -translate-y-1"
            enter-to-class="opacity-100 translate-y-0"
            leave-active-class="transition ease-in duration-75"
            leave-from-class="opacity-100"
            leave-to-class="opacity-0"
          >
            <div
              v-if="addMenuOpen && hiddenWidgets.length > 0"
              class="absolute top-9 left-0 z-30 w-72 rounded-md overflow-hidden shadow-xl"
              style="background: rgba(13,18,26,0.97); border: 1px solid rgba(138,180,255,0.14); backdrop-filter: blur(10px)"
            >
              <button
                v-for="w in hiddenWidgets"
                :key="w.id"
                class="w-full text-left px-3 py-2 flex items-start gap-2.5 hover:bg-white/[0.04] transition-colors"
                @click="addWidget(w.id)"
              >
                <span class="font-mono text-signal-green shrink-0">{{ w.icon }}</span>
                <span class="min-w-0 flex-1">
                  <span class="block text-small text-fg-body">{{ w.title }}</span>
                  <span class="block text-[11px] text-fg-subtle mt-0.5 truncate">{{ w.hint }}</span>
                </span>
              </button>
            </div>
          </transition>
        </div>
        <button
          type="button"
          class="text-small text-fg-subtle hover:text-fg-body font-mono transition-colors"
          title="Reset to default layout"
          @click="restoreDefaults"
        >reset</button>
        <span class="hidden lg:inline text-[11px] text-fg-subtle font-mono">
          drag header · resize corner · right-click for sizes
        </span>
      </template>

      <!-- Toggle button pinned to the right in both modes. -->
      <button
        type="button"
        class="ml-auto flex items-center gap-2 px-3 h-7 rounded-md text-small font-mono transition-all"
        :class="store.editMode
          ? 'bg-signal-green hover:opacity-90'
          : 'text-fg-muted hover:text-fg-body border border-border hover:border-border-strong'"
        :style="store.editMode ? 'color:#070b10' : ''"
        :title="store.editMode ? 'Exit edit mode' : 'Rearrange cards'"
        @click="store.toggleEdit()"
      >
        <span aria-hidden="true">{{ store.editMode ? "✓" : "✎" }}</span>
        <span>{{ store.editMode ? "done" : "rearrange" }}</span>
      </button>
    </header>

    <!-- ── Grid ───────────────────────────────────────────────────────── -->
    <!-- margin = [horizontal, vertical] px between items. Back to 16/16
         — the original spacing reads best with the toolbar band above. -->

    <GridLayout
      v-model:layout="store.layout"
      :class="{ 'grid-is-editing': store.editMode }"
      :col-num="12"
      :row-height="ROW_HEIGHT"
      :is-draggable="store.editMode"
      :is-resizable="store.editMode"
      :margin="[16, MARGIN_V]"
      :use-css-transforms="true"
      :vertical-compact="true"
      :resizable-handles="['s', 'e', 'se']"
      :drag-ignore-from="'input, textarea, select, button, a, label, .no-drag, [contenteditable]'"
      @item-resized="onItemResized"
    >
      <template #item="{ item }">
        <!-- Skip rendering hidden widgets entirely. -->
        <template v-if="!(item as any).hidden && widgetById(String(item.i))">
          <!-- max-h-full lets the card HUG its content while capping at the
               grid-cell height. View-mode and edit-mode now produce the
               SAME card height — edit mode adds only a ring + tiny corner
               icons (no top strip that pushes content down), so exiting
               edit doesn't leave phantom padding. -->
          <article
            class="widget relative h-full w-full overflow-hidden rounded-lg transition-shadow"
            :class="store.editMode
              ? 'ring-1 ring-signal-green/30 cursor-move'
              : ''"
            @contextmenu="onWidgetContextMenu($event, String(item.i))"
          >
            <!-- Edit-mode corner affordances: tiny drag hint (top-left,
                 pointer-events-none) + remove button (top-right,
                 .no-drag so clicks don't start a drag). -->
            <template v-if="store.editMode">
              <span
                class="absolute top-1.5 left-2 z-20 font-mono text-[10px] text-signal-green/70 pointer-events-none select-none tracking-widest"
                aria-hidden="true"
              >⠿</span>
              <button
                type="button"
                class="no-drag absolute top-1 right-1 z-20 w-6 h-6 rounded-md flex items-center justify-center text-fg-subtle hover:text-signal-red hover:bg-signal-red/10 transition-colors text-small font-mono"
                :title="`Remove ${widgetById(String(item.i))?.title ?? ''}`"
                @click.stop="removeWidget(String(item.i))"
              >✕</button>
            </template>

            <!-- Scroll container fills the cell (h-full). Content inside
                 is measured by registerContentEl so the auto-sizer can
                 keep the cell right-sized for the content. Hidden
                 scrollbar kicks in only if the user has manually sized
                 the card smaller than its content. -->
            <div
              class="widget-scroll h-full overflow-y-auto"
              :ref="(el: any) => registerContentEl(String(item.i), el as HTMLElement | null)"
            >
              <component
                :is="widgetById(String(item.i))!.component"
                v-bind="widgetById(String(item.i))!.props(project)"
              />
            </div>
          </article>
        </template>
      </template>
    </GridLayout>

    <!-- ── Right-click context menu ───────────────────────────────────── -->
    <div
      v-if="contextMenu"
      class="fixed z-50 rounded-md py-1 min-w-[200px] shadow-xl"
      :style="{
        top: contextMenu.y + 'px',
        left: contextMenu.x + 'px',
        background: 'rgba(13,18,26,0.97)',
        backdropFilter: 'blur(10px)',
        border: '1px solid rgba(138,180,255,0.14)',
      }"
      @click.stop
      @contextmenu.prevent
    >
      <div class="mono-label px-3 py-1 opacity-60">// {{ widgetById(contextMenu.widgetId)?.title }}</div>
      <button class="w-full text-left px-3 py-1.5 text-small text-signal-green hover:bg-white/5 transition-colors"
        @click="autoSizeAgain(contextMenu.widgetId)">auto-size to content</button>
      <div class="border-t my-1" style="border-color: rgba(138,180,255,0.08)" />
      <button class="w-full text-left px-3 py-1.5 text-small text-fg-body hover:bg-white/5 transition-colors"
        @click="setFullWidth(contextMenu.widgetId)">full width</button>
      <button class="w-full text-left px-3 py-1.5 text-small text-fg-body hover:bg-white/5 transition-colors"
        @click="resize(contextMenu.widgetId, 8, 5)">wide (8w × 5h)</button>
      <button class="w-full text-left px-3 py-1.5 text-small text-fg-body hover:bg-white/5 transition-colors"
        @click="resize(contextMenu.widgetId, 6, 5)">half (6w × 5h)</button>
      <button class="w-full text-left px-3 py-1.5 text-small text-fg-body hover:bg-white/5 transition-colors"
        @click="resize(contextMenu.widgetId, 4, 4)">compact (4w × 4h)</button>
      <div class="border-t my-1" style="border-color: rgba(138,180,255,0.08)" />
      <button class="w-full text-left px-3 py-1.5 text-small text-signal-red hover:bg-signal-red/10 transition-colors"
        @click="removeWidget(contextMenu.widgetId)">remove</button>
    </div>
  </div>
</template>

<style>
/* grid-layout-plus needs these base styles. Rolled into global scope so the
   library's generated inline classNames can target them.  */
.vue-grid-layout {
  position: relative;
  transition: height 200ms ease;
}
.vue-grid-item {
  transition: all 220ms cubic-bezier(0.2, 0.6, 0.2, 1);
  touch-action: none;
}
/* grid-layout-plus emits the placeholder WITHOUT the vue-grid-item class,
   so we have to target just .vue-grid-placeholder. The previous
   compound selector never matched and the library's default red-ish
   tone leaked through. Override with signal-green so the drop-zone
   preview matches the rest of the edit-mode UI. */
.vue-grid-placeholder {
  background: rgba(92, 200, 164, 0.16) !important;
  border: 2px dashed rgba(92, 200, 164, 0.5) !important;
  opacity: 1 !important;
  transition-duration: 80ms;
  border-radius: 8px;
  z-index: 2;
  user-select: none;
}
.vue-grid-item.resizing {
  opacity: 0.9;
  z-index: 3;
}
/* Resize handle — bottom-right corner of each grid cell. Invisible in view
   mode (we hide it by not being resizable at all at the grid-layout-plus
   level). In edit mode we force it visible by default (low opacity) so
   the user always sees where to grab, and brighter on hover. */
.vue-grid-item > .vue-resizable-handle {
  position: absolute;
  width: 22px;
  height: 22px;
  bottom: 0;
  right: 0;
  cursor: se-resize;
  background-image: linear-gradient(
    135deg,
    transparent 0%,
    transparent 45%,
    var(--signal-green, #5cc8a4) 45%,
    var(--signal-green, #5cc8a4) 55%,
    transparent 55%,
    transparent 65%,
    var(--signal-green, #5cc8a4) 65%,
    var(--signal-green, #5cc8a4) 75%,
    transparent 75%,
    transparent 85%,
    var(--signal-green, #5cc8a4) 85%,
    var(--signal-green, #5cc8a4) 95%,
    transparent 95%
  );
  opacity: 0;
  transition: opacity 120ms;
  border-bottom-right-radius: 8px;
  z-index: 15;
}
.grid-is-editing .vue-grid-item > .vue-resizable-handle {
  /* Always half-visible in edit mode so the user can see grab-zones. */
  opacity: 0.55;
}
.grid-is-editing .vue-grid-item:hover > .vue-resizable-handle,
.vue-grid-item.resizing > .vue-resizable-handle {
  opacity: 1;
}

/* Side-edge resize handles (south + east). grid-layout-plus adds each as
   a sibling .vue-resizable-handle with a direction-specific class. We
   want them to be invisible grab-zones along the edges, not diagonal
   corners. */
.vue-grid-item > .vue-resizable-handle-s {
  background-image: none;
  width: 100%;
  height: 10px;
  left: 0;
  right: 0;
  bottom: -2px;
  cursor: s-resize;
  opacity: 0;
  transition: opacity 120ms;
  border-radius: 0 0 8px 8px;
}
.vue-grid-item > .vue-resizable-handle-e {
  background-image: none;
  width: 10px;
  height: 100%;
  top: 0;
  right: -2px;
  bottom: 0;
  cursor: e-resize;
  opacity: 0;
  transition: opacity 120ms;
  border-radius: 0 8px 8px 0;
}
.grid-is-editing .vue-grid-item:hover > .vue-resizable-handle-s,
.grid-is-editing .vue-grid-item:hover > .vue-resizable-handle-e {
  /* Subtle signal-green tint so you can see the grab zone lights up. */
  background: linear-gradient(to bottom, transparent, rgba(92, 200, 164, 0.25));
  opacity: 0.9;
}
.grid-is-editing .vue-grid-item:hover > .vue-resizable-handle-e {
  background: linear-gradient(to right, transparent, rgba(92, 200, 164, 0.25));
}

/* ─── Widget-internal scrolling ─────────────────────────────────────────
   When a card is sized smaller than its content, the inner div scrolls
   but the native scrollbar is hidden entirely — user didn't want an
   ugly gutter. Scrolling works via wheel, trackpad, touch, keyboard.
   Scroll chaining is LEFT ON (default) so hitting the top/bottom of a
   widget bubbles up to the page scroll — otherwise the user gets stuck
   unable to scroll the whole page when their cursor happens to be over
   a card. */
.widget-scroll {
  scrollbar-width: none;            /* Firefox */
  -ms-overflow-style: none;         /* legacy Edge */
  scroll-behavior: smooth;
}
.widget-scroll::-webkit-scrollbar {
  display: none;                    /* Chrome / Safari / Opera / Edge */
  width: 0;
  height: 0;
}

/* (Previous ::after bottom-fade removed — it was overlaying the resize
   handle area and making the corner grab-zone harder to spot in edit
   mode. The hidden-scrollbar already signals overflow well enough.) */
</style>
