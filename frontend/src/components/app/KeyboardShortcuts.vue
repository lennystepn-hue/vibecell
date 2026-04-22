<script setup lang="ts">
/**
 * Global keyboard-shortcut registry + on-demand help overlay (`?` to open).
 * Mount once in App.vue. Listens on window and routes to the right action:
 *   - ⌘K / Ctrl+K  → toggle command palette
 *   - ?            → toggle this help overlay
 *   - g p          → go to projects (/p)
 *   - g s          → focus search bar
 *   - g f          → go to portfolio
 *   - Esc          → close overlay
 *
 * Ignores keypresses when the user is typing inside an input / textarea /
 * contenteditable so shortcuts never clobber real typing.
 */
import { onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { useCommandPaletteStore } from "@/stores/command-palette";

const router = useRouter();
const palette = useCommandPaletteStore();
const open = ref(false);

// Two-key "g…" sequences like Gmail. Tracks whether we're mid-sequence.
let pendingG: ReturnType<typeof setTimeout> | null = null;

function isTyping(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName;
  if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return true;
  if (target.isContentEditable) return true;
  return false;
}

function handleKey(e: KeyboardEvent) {
  // Always allow Esc to close the overlay, even in fields.
  if (e.key === "Escape" && open.value) {
    open.value = false;
    return;
  }
  if (isTyping(e.target)) return;

  const meta = e.metaKey || e.ctrlKey;

  // ⌘K / Ctrl+K → palette
  if (meta && e.key.toLowerCase() === "k") {
    e.preventDefault();
    palette.toggle();
    return;
  }

  // ? → help
  if (e.key === "?" || (e.shiftKey && e.key === "/")) {
    e.preventDefault();
    open.value = !open.value;
    return;
  }

  // g then p/s/f sequences.
  if (e.key === "g" && !meta) {
    if (pendingG) clearTimeout(pendingG);
    pendingG = setTimeout(() => { pendingG = null; }, 900);
    return;
  }
  if (pendingG) {
    if (e.key === "p") { router.push("/p"); pendingG = null; return; }
    if (e.key === "s") {
      pendingG = null;
      router.push("/search").catch(() => undefined);
      return;
    }
    if (e.key === "f") { router.push("/portfolio"); pendingG = null; return; }
    pendingG = null;
  }
}

onMounted(() => window.addEventListener("keydown", handleKey));
onBeforeUnmount(() => window.removeEventListener("keydown", handleKey));

const groups: Array<{ title: string; items: Array<{ keys: string[]; label: string }> }> = [
  {
    title: "Navigation",
    items: [
      { keys: ["g", "p"], label: "Go to projects" },
      { keys: ["g", "s"], label: "Go to search" },
      { keys: ["g", "f"], label: "Go to portfolio" },
    ],
  },
  {
    title: "Command",
    items: [
      { keys: ["⌘", "K"], label: "Toggle command palette" },
      { keys: ["?"], label: "Show this help" },
      { keys: ["Esc"], label: "Close overlays" },
    ],
  },
];
</script>

<template>
  <Teleport to="body">
    <transition
      enter-active-class="transition-opacity duration-150"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-100"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-[80] flex items-center justify-center px-4"
        style="background: rgba(3, 6, 10, 0.65); backdrop-filter: blur(6px)"
        @click.self="open = false"
      >
        <div
          class="glass rounded-xl w-full max-w-md p-6 shadow-2xl"
          style="background: rgba(13,18,26,0.96)"
        >
          <header class="flex items-start justify-between mb-4">
            <div>
              <h3 class="mono-label text-fg-muted">// shortcuts</h3>
              <p class="text-small text-fg-subtle mt-0.5">Press <kbd class="kbd">?</kbd> anytime.</p>
            </div>
            <button
              class="text-fg-muted hover:text-fg-body transition-colors"
              aria-label="Close"
              @click="open = false"
            >✕</button>
          </header>

          <div class="space-y-5">
            <section v-for="g in groups" :key="g.title">
              <p class="mono-label text-fg-subtle mb-2">{{ g.title }}</p>
              <ul class="space-y-1.5">
                <li
                  v-for="item in g.items"
                  :key="item.label"
                  class="flex items-center justify-between"
                >
                  <span class="text-small text-fg-body">{{ item.label }}</span>
                  <span class="flex items-center gap-1">
                    <kbd v-for="k in item.keys" :key="k" class="kbd">{{ k }}</kbd>
                  </span>
                </li>
              </ul>
            </section>
          </div>
        </div>
      </div>
    </transition>
  </Teleport>
</template>

<style scoped>
.kbd {
  font-family: ui-monospace, "SF Mono", Menlo, monospace;
  font-size: 11px;
  line-height: 1;
  padding: 3px 6px;
  border-radius: 4px;
  background: rgba(138,180,255,0.08);
  border: 1px solid rgba(138,180,255,0.18);
  color: var(--fg-body);
  min-width: 22px;
  text-align: center;
}
</style>
