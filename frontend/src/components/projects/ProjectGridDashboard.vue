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
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { GridLayout } from "grid-layout-plus";

import { useDashboardLayoutStore } from "@/stores/dashboard-layout";
import { DEFAULT_LAYOUT, widgetById } from "./widget-registry";

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

// Convenient sizing presets from the context menu.
function resize(id: string, w: number, h: number) {
  const widget = store.layout.find((l) => l.i === id);
  if (!widget) return;
  widget.w = Math.max(widget.minW ?? 1, w);
  widget.h = Math.max(widget.minH ?? 1, h);
  closeContextMenu();
}
function setFullWidth(id: string) {
  const widget = store.layout.find((l) => l.i === id);
  if (!widget) return;
  widget.w = 12;
  widget.x = 0;
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
}

// We only want grid-layout-plus to react to drag/resize when editMode is on —
// setting isDraggable + isResizable to false keeps it a plain static grid.
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
      :col-num="12"
      :row-height="40"
      :is-draggable="store.editMode"
      :is-resizable="store.editMode"
      :margin="[16, 16]"
      :use-css-transforms="true"
      :vertical-compact="true"
      drag-allow-from=".widget-drag-handle"
    >
      <template #item="{ item }">
        <!-- Skip rendering hidden widgets entirely. -->
        <template v-if="!(item as any).hidden && widgetById(String(item.i))">
          <article
            class="widget relative h-full w-full overflow-hidden rounded-lg transition-shadow"
            :class="store.editMode
              ? 'ring-1 ring-border hover:ring-signal-green/40 hover:shadow-[0_0_0_1px_rgba(92,200,164,0.15)]'
              : ''"
            @contextmenu="onWidgetContextMenu($event, String(item.i))"
          >
            <!-- Drag handle overlay (only in edit mode, pinned above the scroll) -->
            <div
              v-if="store.editMode"
              class="widget-drag-handle absolute inset-x-0 top-0 h-8 z-20 cursor-move flex items-center justify-between px-3"
              :title="widgetById(String(item.i))?.title"
              style="background: linear-gradient(to bottom, rgba(13,18,26,0.92), transparent);"
            >
              <span class="font-mono text-[10px] text-fg-subtle opacity-60 pointer-events-none">
                ⠿ {{ widgetById(String(item.i))?.title }}
              </span>
              <button
                type="button"
                class="text-fg-subtle hover:text-signal-red transition-colors text-small font-mono"
                title="Remove (you can re-add from + add widget)"
                @click.stop="removeWidget(String(item.i))"
              >✕</button>
            </div>

            <!-- Scrollable inner container. Hides the native scrollbar via the
                 `.widget-scroll` helper below; the fade masks at top + bottom
                 hint at cropped content in both directions without a visible
                 bar. -->
            <div
              class="widget-scroll h-full overflow-y-auto"
              :class="store.editMode ? 'pt-8' : ''"
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
.vue-grid-item.vue-grid-placeholder {
  background: rgba(92, 200, 164, 0.15) !important;
  border: 2px dashed rgba(92, 200, 164, 0.45);
  opacity: 1;
  transition-duration: 80ms;
  border-radius: 8px;
  z-index: 2;
  user-select: none;
}
.vue-grid-item.resizing {
  opacity: 0.9;
  z-index: 3;
}
.vue-grid-item > .vue-resizable-handle {
  position: absolute;
  width: 20px;
  height: 20px;
  bottom: 0;
  right: 0;
  cursor: se-resize;
  background-image: linear-gradient(
    135deg,
    transparent 0%,
    transparent 50%,
    var(--signal-green, #5cc8a4) 50%,
    var(--signal-green, #5cc8a4) 60%,
    transparent 60%,
    transparent 70%,
    var(--signal-green, #5cc8a4) 70%,
    var(--signal-green, #5cc8a4) 80%,
    transparent 80%
  );
  opacity: 0;
  transition: opacity 120ms;
  border-bottom-right-radius: 8px;
  z-index: 10;
}
.vue-grid-item:hover > .vue-resizable-handle,
.vue-grid-item.resizing > .vue-resizable-handle {
  opacity: 0.7;
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

/* A tiny radial shadow at the bottom inside edge of every card. Sits ABOVE
   content, fades to nothing when you're scrolled to the end, gives a
   soft "more below" hint without a bar. 4 px tall — imperceptible on
   short cards, exactly what you want on overflowing ones. */
.widget::after {
  content: "";
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  height: 12px;
  background: linear-gradient(to top, rgba(7, 11, 16, 0.55), rgba(7, 11, 16, 0));
  pointer-events: none;
  border-bottom-left-radius: 8px;
  border-bottom-right-radius: 8px;
  z-index: 2;
}
</style>
