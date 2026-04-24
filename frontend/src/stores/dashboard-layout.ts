import { defineStore } from "pinia";
import { ref, watch } from "vue";

/**
 * Drag-and-drop dashboard layout state.
 *
 * Each project keeps its own 12-column × variable-row grid. Users can drag
 * cards around, resize via the corner handle, remove cards they don't need,
 * and add them back later from the "+ add widget" menu. Layouts live in
 * localStorage for now (per-project key) — we can move to the backend once
 * multi-device sync becomes a priority.
 */

export interface WidgetLayout {
  /** Stable widget id — must match a key in the widget registry. */
  i: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** True = hidden from the grid. Still in the array so "add widget" can re-show. */
  hidden?: boolean;
  /**
   * Set to true the first time the user manually resizes this widget.
   * When true the auto-sizer stops touching h so the user-chosen size
   * survives a page reload. Cleared by the right-click "auto-size to
   * content" action or on show-from-hidden.
   */
  userSized?: boolean;
  /** Optional per-widget min/max overrides (from registry by default). */
  minW?: number;
  minH?: number;
  maxW?: number;
}

const STORAGE_PREFIX = "vc:dashboard-layout:";

function storageKey(slug: string): string {
  return `${STORAGE_PREFIX}${slug}`;
}

export const useDashboardLayoutStore = defineStore("dashboard-layout", () => {
  /** Current project slug that the store is hydrated for. */
  const activeSlug = ref<string | null>(null);
  /** Layout array for the active project. */
  const layout = ref<WidgetLayout[]>([]);
  /** Edit-mode toggle — enables drag-handles + resize + remove buttons. */
  const editMode = ref(false);

  /** Load or initialise a layout for a slug. Call on project-detail mount. */
  function hydrate(slug: string, defaultLayout: WidgetLayout[]): void {
    activeSlug.value = slug;
    if (typeof localStorage === "undefined") {
      layout.value = cloneLayout(defaultLayout);
      return;
    }
    const raw = localStorage.getItem(storageKey(slug));
    if (!raw) {
      layout.value = cloneLayout(defaultLayout);
      return;
    }
    try {
      const parsed = JSON.parse(raw) as WidgetLayout[];
      if (!Array.isArray(parsed) || parsed.length === 0) throw new Error("empty");
      // Merge: start with default layout (so any newly-added widget shows up
      // at the end instead of being silently missing), then override x/y/w/h
      // from stored layout for the widgets that exist.
      const byId = new Map(parsed.map((w) => [w.i, w]));
      const merged: WidgetLayout[] = [];
      // First: defaults that the user hasn't stored yet (new widget since
      // their layout was saved) → appended with default position.
      let appendY = Math.max(0, ...parsed.map((w) => w.y + w.h));
      for (const def of defaultLayout) {
        const stored = byId.get(def.i);
        if (stored) {
          merged.push({ ...def, ...stored });
        } else {
          merged.push({ ...def, y: appendY });
          appendY += def.h;
        }
      }
      // Preserve any stored widget ids that are no longer in the registry
      // (e.g. if we ever remove a card type) — drop them silently.
      layout.value = merged;
    } catch {
      layout.value = cloneLayout(defaultLayout);
    }
  }

  function persist(): void {
    if (!activeSlug.value || typeof localStorage === "undefined") return;
    localStorage.setItem(
      storageKey(activeSlug.value),
      JSON.stringify(layout.value),
    );
  }

  /** Toggle edit mode. */
  function toggleEdit(): void {
    editMode.value = !editMode.value;
  }

  /** Hide a widget (doesn't delete — can be re-added). */
  function hideWidget(id: string): void {
    const w = layout.value.find((l) => l.i === id);
    if (w) {
      w.hidden = true;
      persist();
    }
  }

  /** Show a previously-hidden widget, parking it at the bottom. */
  function showWidget(id: string): void {
    const w = layout.value.find((l) => l.i === id);
    if (w) {
      w.hidden = false;
      // Move to end so it doesn't collide with existing layout.
      const maxY = Math.max(0, ...layout.value
        .filter((l) => !l.hidden && l.i !== id)
        .map((l) => l.y + l.h));
      w.y = maxY;
      persist();
    }
  }

  /** Drop everything back to factory defaults. */
  function resetToDefault(defaultLayout: WidgetLayout[]): void {
    layout.value = cloneLayout(defaultLayout);
    persist();
  }

  // Auto-persist on any layout mutation (drag, resize, etc.). Debounced so a
  // drag doesn't hammer localStorage on every move frame.
  let saveHandle: ReturnType<typeof setTimeout> | null = null;
  watch(layout, () => {
    if (saveHandle) clearTimeout(saveHandle);
    saveHandle = setTimeout(persist, 250);
  }, { deep: true });

  return {
    activeSlug,
    layout,
    editMode,
    hydrate,
    persist,
    toggleEdit,
    hideWidget,
    showWidget,
    resetToDefault,
  };
});

function cloneLayout(layout: WidgetLayout[]): WidgetLayout[] {
  return layout.map((w) => ({ ...w }));
}
