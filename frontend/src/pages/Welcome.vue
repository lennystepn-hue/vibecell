<script setup lang="ts">
/**
 * Onboarding — one screen.
 *
 * What this replaces: a three-step wizard that created an *empty* project in
 * step 1, offered *six* editor tabs in step 2, and landed in an *empty*
 * console in step 3. Every aha-moment Vibecell has happened after it ended,
 * where no new user was still watching. Step 2 also asked for a decision —
 * "which editor tab applies to me?" — that a new user is not yet equipped to
 * make.
 *
 * Now: one action, then the user watches their portfolio build itself.
 *
 * Why the one-liner is the primary path and the deep link is secondary: the
 * line runs `hangar setup`, which wires up *every* MCP client on the machine.
 * The deep link configures Claude Desktop and nothing else. Ranking them by
 * which is easier to click would have put the weaker one first.
 *
 * Routing contract, unchanged from the old wizard:
 *   • reachable at /welcome for anyone authed
 *   • ProjectsIndex redirects here on first empty-dashboard hit, gated by a
 *     localStorage flag so it doesn't keep re-firing
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import Card from "@/components/ui/Card.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";

import { useAuthStore } from "@/stores/auth";
import { useOnboardingStore } from "@/stores/onboarding";

const auth = useAuthStore();
const onboarding = useOnboardingStore();
const router = useRouter();

const ONBOARDING_FLAG = "vibecell_onboarding_done";
const BASE = "https://vibecell.dev";

// ----- Platform ------------------------------------------------------------

type Os = "windows" | "macos" | "linux";

/**
 * A browser cannot see which applications are installed — only which OS it is
 * running on. That is the honest ceiling: pick the *likely* path, and make
 * the fallback free rather than pretending to know what is on the disk.
 */
function detectOs(): Os {
  if (typeof navigator === "undefined") return "macos";
  const ua = navigator.userAgent.toLowerCase();
  if (ua.includes("win")) return "windows";
  if (ua.includes("mac")) return "macos";
  return "linux";
}

const os = ref<Os>(detectOs());
const osLabel = computed(() =>
  os.value === "windows" ? "PowerShell" : os.value === "macos" ? "Terminal" : "your shell",
);

const oneLiner = computed(() => {
  const p = onboarding.pairing;
  if (!p) return null;
  return os.value === "windows" ? p.install_ps1 : p.install_sh;
});

// ----- Copy ----------------------------------------------------------------

const copied = ref(false);
let copyResetHandle: ReturnType<typeof setTimeout> | null = null;

async function copyLine() {
  if (!oneLiner.value) return;
  try {
    await navigator.clipboard.writeText(oneLiner.value);
    copied.value = true;
    if (copyResetHandle) clearTimeout(copyResetHandle);
    copyResetHandle = setTimeout(() => (copied.value = false), 2000);
  } catch {
    /* clipboard blocked — the line is select-all on screen either way */
  }
}

// ----- Deep link, with failure detection ------------------------------------

type DeepLinkState = "idle" | "trying" | "failed";
const deepLink = ref<DeepLinkState>("idle");
let deepLinkTimer: ReturnType<typeof setTimeout> | null = null;

function clearDeepLinkTimer() {
  if (deepLinkTimer) {
    clearTimeout(deepLinkTimer);
    deepLinkTimer = null;
  }
}

function onVisibilityChange() {
  // The tab losing focus means the OS handed the URL to an application, so a
  // protocol handler exists. If that never happens, nothing is registered.
  if (document.visibilityState === "hidden" && deepLink.value === "trying") {
    deepLink.value = "idle";
    clearDeepLinkTimer();
  }
}

/**
 * Fire a deep link and find out whether anything caught it.
 *
 * There is no API that answers "is Claude Desktop installed?". Watching for
 * the tab to lose focus is the only signal available: fire, wait ~1.5s, and
 * if focus never moved, say so plainly instead of leaving the user to work
 * out why nothing happened.
 */
function tryDeepLink(url: string) {
  deepLink.value = "trying";
  clearDeepLinkTimer();
  deepLinkTimer = setTimeout(() => {
    if (deepLink.value === "trying") deepLink.value = "failed";
  }, 1500);
  window.location.href = url;
}

const claudeDesktopLink = `claude://add-connector?url=${encodeURIComponent(BASE)}`;

// ----- Manual fallback -----------------------------------------------------

/** The six tabs became one quiet link. Nobody should have to pick from six. */
const showManual = ref(false);
const mcpUrl = `${BASE}/mcp`;

// ----- Progress ------------------------------------------------------------

const log = computed(() => {
  const rows: Array<{ key: string; mark: "ok" | "run" | "skip"; text: string }> = [];

  if (onboarding.paired) {
    rows.push({ key: "paired", mark: "ok", text: "device paired" });
  }
  for (const c of onboarding.clients) {
    rows.push({
      key: `client:${c.client}`,
      mark: c.ok ? "ok" : "skip",
      text: c.ok ? `${c.client} configured` : `${c.client} — ${c.reason ?? "not found"}`,
    });
  }
  if (onboarding.repoCount !== null) {
    rows.push({
      key: "scan",
      mark: "ok",
      text: `${onboarding.repoCount} repositor${onboarding.repoCount === 1 ? "y" : "ies"} found`,
    });
  }
  for (const p of onboarding.projects) {
    rows.push({
      key: `project:${p.slug}`,
      mark: p.enriched ? "ok" : "run",
      text: p.enriched ? `${p.name} — ${p.pitch ?? "ready"}` : `reading ${p.name}…`,
    });
  }
  return rows;
});

const started = computed(() => log.value.length > 0);

// ----- Finish --------------------------------------------------------------

function markDone() {
  try {
    localStorage.setItem(ONBOARDING_FLAG, "1");
  } catch {
    /* private mode */
  }
}

function finish() {
  markDone();
  // Straight into the first project we just built, or the portfolio if
  // something went sideways. Deliberately no projects-store fetch here: this
  // screen renders nothing from that list, and a network call whose only
  // purpose is a fallback route is a call not worth making.
  const first = onboarding.projects[0]?.slug;
  router.replace(first ? `/p/${first}` : "/p");
}

function skipAll() {
  markDone();
  router.replace("/p");
}

// The completion screen with triage is #8. Until it lands, `done` surfaces
// inline rather than auto-navigating — dropping the user somewhere the moment
// the last event arrives would rob them of the payoff they just watched.
watch(
  () => onboarding.done,
  (isDone) => {
    if (isDone) markDone();
  },
);

// ----- Lifecycle -----------------------------------------------------------

onMounted(() => {
  if (!auth.isAuthed) {
    router.replace({ path: "/login", query: { next: "/welcome" } });
    return;
  }
  document.addEventListener("visibilitychange", onVisibilityChange);
  onboarding.open();
  void onboarding.mintCode();
});

onBeforeUnmount(() => {
  document.removeEventListener("visibilitychange", onVisibilityChange);
  clearDeepLinkTimer();
  if (copyResetHandle) clearTimeout(copyResetHandle);
  onboarding.close();
});
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] px-6 py-12">
    <div class="w-full max-w-[620px] mx-auto">
      <div class="flex items-center gap-2 mb-10 text-fg-subtle">
        <span class="text-signal-green font-mono text-section">◈</span>
        <span class="font-mono text-micro tracking-label uppercase">Vibecell · setup</span>
      </div>

      <!-- ─── The one action ──────────────────────────────────────────── -->
      <Card>
        <h1 class="text-display text-fg-primary tracking-tight">Let Claude set this up.</h1>
        <p class="text-body text-fg-muted mt-2">
          One line in {{ osLabel }}. It pairs this machine, wires up every AI editor it
          finds, and then Claude reads your repos and fills in your projects — while you
          watch below.
        </p>

        <div
          class="mt-6 rounded-md p-3 font-mono text-small text-fg-primary break-all select-all"
          style="background: rgb(var(--bg-surface-rgb) / 0.5); border: 1px solid var(--border-default)"
        >{{ oneLiner ?? "…" }}</div>

        <PrimaryButton size="lg" class="w-full mt-3" :disabled="!oneLiner" @click="copyLine">
          {{ copied ? "✓ Copied — paste it into your terminal" : "Copy the line" }}
        </PrimaryButton>

        <p class="text-micro text-fg-subtle mt-3">
          The code in that line works once and expires in 10 minutes. We refresh it for you
          while this page is open.
        </p>

        <!-- Secondary: no terminal. Configures Claude Desktop only, which is
             why it sits below rather than above. -->
        <footer class="mt-6 pt-5 border-t border-border-subtle">
          <button
            v-if="deepLink !== 'failed'"
            type="button"
            class="text-small text-fg-muted hover:text-fg-body transition-colors"
            @click="tryDeepLink(claudeDesktopLink)"
          >
            Rather not use a terminal? Set up Claude Desktop only →
          </button>
          <p v-else class="text-small text-fg-muted">
            Claude Desktop didn't respond — it may not be installed. The line above works
            everywhere, and sets up more.
          </p>

          <button
            type="button"
            class="block mt-3 text-small text-fg-subtle hover:text-fg-body transition-colors"
            @click="showManual = !showManual"
          >
            {{ showManual ? "Hide manual setup" : "Different editor · set it up by hand" }}
          </button>

          <div v-if="showManual" class="mt-3 space-y-2">
            <p class="text-small text-fg-muted">
              Add a remote MCP server pointing at this URL. Every editor calls that screen
              something different — MCP, Connectors, Context Servers.
            </p>
            <code
              class="block rounded p-2 font-mono text-small text-fg-body break-all select-all"
              style="background: rgb(var(--bg-surface-rgb) / 0.5)"
            >{{ mcpUrl }}</code>
          </div>
        </footer>
      </Card>

      <!-- ─── Live progress ──────────────────────────────────────────── -->
      <Card class="mt-5" title="progress">
        <template #meta>
          <span v-if="onboarding.connected">· live</span>
        </template>

        <p v-if="!started" class="text-small text-fg-subtle">
          Waiting for the line to run. Nothing happens here until you paste it.
        </p>

        <ul v-else class="space-y-1.5">
          <li
            v-for="row in log"
            :key="row.key"
            class="flex items-start gap-2.5 font-mono text-small"
          >
            <span
              class="shrink-0"
              :class="{
                'text-signal-green': row.mark === 'ok',
                'text-signal-blue': row.mark === 'run',
                'text-fg-subtle': row.mark === 'skip',
              }"
              aria-hidden="true"
            >{{ row.mark === "ok" ? "✓" : row.mark === "run" ? "◐" : "○" }}</span>
            <span :class="row.mark === 'skip' ? 'text-fg-subtle' : 'text-fg-body'">
              {{ row.text }}
            </span>
          </li>
        </ul>

        <footer
          v-if="onboarding.done"
          class="mt-6 pt-5 border-t border-border-subtle flex items-center justify-between gap-4"
        >
          <div class="min-w-0">
            <MonoLabel>done</MonoLabel>
            <p class="text-body text-fg-primary mt-1">
              {{ onboarding.finalProjectCount ?? onboarding.projects.length }} projects are in.
              You typed nothing.
            </p>
          </div>
          <PrimaryButton size="lg" @click="finish">Open →</PrimaryButton>
        </footer>
      </Card>

      <div class="flex justify-end mt-4">
        <button
          type="button"
          class="text-small text-fg-subtle hover:text-fg-body transition-colors"
          @click="skipAll"
        >
          Skip setup →
        </button>
      </div>
    </div>
  </div>
</template>
