import { onMounted, onUnmounted } from "vue";

interface Options {
  key: string;       // e.g. "k"
  meta?: boolean;    // ⌘ on mac, ctrl on pc (we check either)
  preventDefault?: boolean;
}

/**
 * Register a global keydown handler. Returns cleanup via onUnmounted.
 * Use `meta: true` to require cmd/ctrl modifier (cross-OS).
 */
export function useShortcut(options: Options, handler: (ev: KeyboardEvent) => void): void {
  function onKey(ev: KeyboardEvent) {
    if (ev.key.toLowerCase() !== options.key.toLowerCase()) return;
    if (options.meta && !(ev.metaKey || ev.ctrlKey)) return;
    if (!options.meta && (ev.metaKey || ev.ctrlKey)) return;
    if (options.preventDefault !== false) ev.preventDefault();
    handler(ev);
  }
  onMounted(() => window.addEventListener("keydown", onKey));
  onUnmounted(() => window.removeEventListener("keydown", onKey));
}
