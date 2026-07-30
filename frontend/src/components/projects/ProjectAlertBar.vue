<script setup lang="ts">
/**
 * What is actively stopping work — above everything, or nothing at all.
 *
 * The console renders 16 widgets of equal weight in a fixed order. It looks
 * identical whether the live URL is down and the project is blocked, or
 * everything is fine and it just shipped. This bar is the exception channel:
 * it sits above the grid and outside it, so a saved layout can never bury it,
 * and it renders **nothing** the rest of the time.
 *
 * Deliberately narrow. The first version also listed known issues and open
 * questions, and that was wrong: a project can carry five known issues for
 * months and be perfectly healthy. Rendering standing context as an alarm
 * cries wolf, and a strip the user has learned to ignore is worse than no
 * strip — the one time something is genuinely on fire it looks identical.
 * Both counts already live on the focus card, where they read as context.
 *
 * So: two conditions, both of which mean work has actually stopped. On most
 * projects on most days this component renders nothing, which is the point.
 *
 * `blocked_by` also appears in the focus card, and that duplication is
 * intentional — a blocker buried in the third card of sixteen is the failure
 * being fixed.
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";

interface Alert {
  key: string;
  text: string;
  /** Widget id to scroll to, so the row is a route to the detail. */
  target: string;
}

const props = defineProps<{
  project: {
    slug: string;
    context?: { blocked_by?: string | null } | null;
    [k: string]: unknown;
  };
}>();

// ----- Health -------------------------------------------------------------

/**
 * Fetched here rather than read from the health card, because that card owns
 * its own request and exposing it upward would couple a widget to the page
 * chrome. A failed request stays silent rather than inventing an outage.
 */
const healthStatus = ref<string | null>(null);
let abort: AbortController | null = null;

async function loadHealth(slug: string) {
  abort?.abort();
  abort = new AbortController();
  try {
    const res = await fetch(`/api/v1/projects/${slug}/health`, {
      credentials: "include",
      signal: abort.signal,
    });
    if (!res.ok) return;
    const body = (await res.json()) as { last_status?: string; status?: string };
    healthStatus.value = body.last_status ?? body.status ?? null;
  } catch {
    /* offline or aborted — omit the health row */
  }
}

watch(
  () => props.project.slug,
  (slug) => {
    healthStatus.value = null;
    if (slug) void loadHealth(slug);
  },
  { immediate: true },
);

onBeforeUnmount(() => abort?.abort());

// ----- Derivation ---------------------------------------------------------

const alerts = computed<Alert[]>(() => {
  const out: Alert[] = [];

  // A blocker outranks a dead URL: nothing on this project can move at all.
  const blocked = props.project.context?.blocked_by?.trim();
  if (blocked) {
    out.push({ key: "blocked", text: `Blocked — ${blocked}`, target: "focus" });
  }

  if (healthStatus.value === "down" || healthStatus.value === "error") {
    out.push({
      key: "health",
      text: healthStatus.value === "down" ? "Live URL is down" : "Healthcheck is erroring",
      target: "health",
    });
  }

  return out;
});

function focusWidget(id: string) {
  document
    .querySelector(`[data-widget="${id}"]`)
    ?.scrollIntoView({ behavior: "smooth", block: "center" });
}
</script>

<template>
  <!-- Silent when nothing is stopping work. There is no "all good" state. -->
  <section
    v-if="alerts.length"
    class="mb-5 rounded-lg px-4 py-3"
    style="background: var(--signal-red-bg); border: 1px solid rgb(var(--signal-red-rgb) / 0.3)"
    aria-live="polite"
  >
    <ul class="flex flex-wrap items-center gap-x-5 gap-y-2">
      <li v-for="a in alerts" :key="a.key" class="flex items-center gap-2 text-small">
        <span class="shrink-0 font-mono text-signal-red" aria-hidden="true">●</span>
        <button
          type="button"
          class="text-left hover:underline underline-offset-2 transition-colors"
          style="color: var(--fg-primary)"
          @click="focusWidget(a.target)"
        >{{ a.text }}</button>
      </li>
    </ul>
  </section>
</template>
