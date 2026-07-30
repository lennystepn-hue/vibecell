<script setup lang="ts">
/**
 * What's wrong right now — above everything, or nothing at all.
 *
 * The console renders 16 widgets of equal visual weight in a fixed order. It
 * looks identical whether the live URL is down and the project is blocked, or
 * everything is fine and it just shipped. Urgency is per-project and changes
 * hourly; a static grid cannot express it.
 *
 * This bar is the exception channel. It sits above the grid, outside it — so
 * it cannot be dragged away or lost in a saved layout — and it renders
 * **nothing** when there is nothing wrong. A permanent "all good" banner is
 * chrome, and chrome is what this is meant to cut.
 *
 * `blocked_by` also appears in the focus card, and that duplication is
 * deliberate: a blocker buried in the third card of sixteen is precisely the
 * failure being fixed. Everything else here is either absent from the grid or
 * only visible after scrolling.
 */
import { computed, onBeforeUnmount, ref, watch } from "vue";

type Severity = "critical" | "warning";

interface Alert {
  key: string;
  severity: Severity;
  text: string;
  /** Widget id to scroll to, when the detail lives in a card. */
  target?: string;
}

const props = defineProps<{
  project: {
    slug: string;
    context?: {
      blocked_by?: string | null;
      known_issues?: unknown[] | null;
      open_questions?: unknown[] | null;
    } | null;
    [k: string]: unknown;
  };
}>();

// ----- Health -------------------------------------------------------------

/**
 * Fetched here rather than read from the health card, because the card owns
 * its own request and exposing that upward would couple a widget to the page
 * chrome. One extra GET on a page that already makes several is the cheaper
 * trade.
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
    /* offline or aborted — the bar simply omits the health row */
  }
}

watch(() => props.project.slug, (slug) => {
  healthStatus.value = null;
  if (slug) void loadHealth(slug);
}, { immediate: true });

onBeforeUnmount(() => abort?.abort());

// ----- Derivation ---------------------------------------------------------

function count(list: unknown[] | null | undefined): number {
  return Array.isArray(list) ? list.length : 0;
}

const alerts = computed<Alert[]>(() => {
  const ctx = props.project.context ?? {};
  const out: Alert[] = [];

  // Ordered by what stops work soonest. A blocker means nothing else on this
  // project can move, so it outranks a dead URL.
  const blocked = ctx.blocked_by?.trim();
  if (blocked) {
    out.push({ key: "blocked", severity: "critical", text: `Blocked — ${blocked}`, target: "focus" });
  }

  if (healthStatus.value === "down" || healthStatus.value === "error") {
    out.push({
      key: "health",
      severity: "critical",
      text: healthStatus.value === "down" ? "Live URL is down" : "Healthcheck is erroring",
      target: "health",
    });
  }

  const issues = count(ctx.known_issues);
  if (issues > 0) {
    out.push({
      key: "issues",
      severity: "warning",
      text: `${issues} known issue${issues === 1 ? "" : "s"}`,
      target: "focus",
    });
  }

  const questions = count(ctx.open_questions);
  if (questions > 0) {
    out.push({
      key: "questions",
      severity: "warning",
      text: `${questions} open question${questions === 1 ? "" : "s"}`,
      target: "focus",
    });
  }

  return out;
});

const hasCritical = computed(() => alerts.value.some((a) => a.severity === "critical"));

function focusWidget(id?: string) {
  if (!id) return;
  document
    .querySelector(`[data-widget="${id}"]`)
    ?.scrollIntoView({ behavior: "smooth", block: "center" });
}
</script>

<template>
  <!-- Silent when clean. There is no "everything is fine" state to render. -->
  <section
    v-if="alerts.length"
    class="mb-5 rounded-lg px-4 py-3"
    :style="hasCritical
      ? 'background: var(--signal-red-bg); border: 1px solid rgb(var(--signal-red-rgb) / 0.3)'
      : 'background: var(--signal-amber-bg); border: 1px solid rgb(var(--signal-amber-rgb) / 0.25)'"
    aria-live="polite"
  >
    <ul class="flex flex-wrap items-center gap-x-5 gap-y-2">
      <li
        v-for="a in alerts"
        :key="a.key"
        class="flex items-center gap-2 text-small"
      >
        <span
          class="shrink-0 font-mono"
          :style="a.severity === 'critical'
            ? 'color: var(--signal-red)'
            : 'color: var(--signal-amber)'"
          aria-hidden="true"
        >{{ a.severity === "critical" ? "●" : "◐" }}</span>

        <button
          v-if="a.target"
          type="button"
          class="text-left hover:underline underline-offset-2 transition-colors"
          style="color: var(--fg-primary)"
          @click="focusWidget(a.target)"
        >{{ a.text }}</button>
        <span v-else style="color: var(--fg-primary)">{{ a.text }}</span>
      </li>
    </ul>
  </section>
</template>
