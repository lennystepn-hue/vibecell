<script setup lang="ts">
/**
 * Onboarding wizard — 3 cockpit-styled steps that turn a freshly-signed-up
 * user into a wired-up Vibecell user in under a minute.
 *
 *   01 · spin up your first project   (inline create OR import from GitHub)
 *   02 · pair your editor             (Claude Desktop one-click / Code paste)
 *   03 · console live                 (open project, ship)
 *
 * Routing contract:
 *   • Reachable at /welcome for anyone authed.
 *   • ProjectsIndex auto-redirects here on first empty-dashboard hit
 *     (gated by localStorage flag so it doesn't keep re-firing).
 *   • Calling `finish()` writes the flag and navigates to the freshly-created
 *     project (or /p if user skipped step 1 entirely).
 *
 * Auto-advance:
 *   • Step 1 → 2 fires the moment the projects list becomes non-empty.
 *   • Step 2 → 3 fires when a new OAuth connection (Claude Desktop, Cursor,
 *     Claude Code) shows up via the connections-store poll.
 */
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import TextField from "@/components/ui/TextField.vue";

import { api } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useConnectionsStore } from "@/stores/connections";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";

const auth = useAuthStore();
const projects = useProjectsStore();
const connections = useConnectionsStore();
const toast = useToastStore();
const router = useRouter();

const ONBOARDING_FLAG = "vibecell_onboarding_done";

// ----- Step state ----------------------------------------------------------

type Step = 1 | 2 | 3;
const step = ref<Step>(1);

// ----- Step 1: create first project ---------------------------------------

const projectName = ref("");
const projectSlug = ref("");
const projectEmoji = ref("📦");
const creating = ref(false);
const createError = ref<string | null>(null);
const createdSlug = ref<string | null>(null);

function autoSlug(from: string): string {
  return from
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

watch(projectName, (v) => {
  if (!projectSlug.value || projectSlug.value === autoSlug(projectName.value.slice(0, -1))) {
    projectSlug.value = autoSlug(v);
  }
});

const canCreate = computed(
  () => projectName.value.trim().length > 0 && projectSlug.value.trim().length > 0 && !creating.value,
);

async function createProject() {
  createError.value = null;
  creating.value = true;
  const { data, error: apiError, response } = await api.POST("/api/v1/projects", {
    body: {
      name: projectName.value.trim(),
      slug: projectSlug.value.trim(),
      emoji: projectEmoji.value.trim() || null,
      pitch: null,
      status: "building",
    },
  });
  creating.value = false;

  if (apiError || !data) {
    const detail = (apiError as { detail?: string } | undefined)?.detail;
    createError.value = detail ?? `Couldn't create project (${response?.status ?? "unknown"})`;
    return;
  }
  toast.push(`Created ${data.name}`, "success");
  createdSlug.value = data.slug;
  await projects.fetchList();
  step.value = 2;
}

// ----- Step 2: pair editor -------------------------------------------------

type EditorTab = "claude-desktop" | "claude-code" | "cursor" | "zed" | "windsurf";

const tab = ref<EditorTab>(detectBestTab());
const oneClickAttempted = ref(false);
const copiedKey = ref<string | null>(null);
const connectionCountAtStart = ref(0);
const pollHandle = ref<ReturnType<typeof setInterval> | null>(null);

const BASE = "https://vibecell.dev";
const MCP_URL = `${BASE}/mcp`;

function detectBestTab(): EditorTab {
  if (typeof navigator === "undefined") return "claude-desktop";
  const ua = navigator.userAgent.toLowerCase();
  const platform = (navigator.platform ?? "").toLowerCase();
  if (platform.includes("mac") || ua.includes("mac os")) return "claude-desktop";
  if (platform.includes("win")) return "claude-desktop";
  return "claude-code";
}

const claudeCodeCommand = computed(
  () => `claude mcp add vibecell ${MCP_URL} --transport http --scope user`,
);
const cursorDeepLink = computed(() => {
  const config = { name: "vibecell", url: MCP_URL, type: "http" };
  const b64 = btoa(JSON.stringify(config));
  return `cursor://anysphere.cursor-deeplink/mcp/install?name=vibecell&config=${b64}`;
});
const zedConfig = JSON.stringify(
  { context_servers: { vibecell: { command: { path: "npx", args: ["-y", "mcp-remote", MCP_URL] } } } },
  null,
  2,
);
const windsurfCommand = computed(
  () => `windsurf mcp add vibecell ${MCP_URL} --transport http`,
);

async function copy(text: string, key: string) {
  try {
    await navigator.clipboard.writeText(text);
    copiedKey.value = key;
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = null;
    }, 1800);
  } catch {
    /* ignore */
  }
}

function tryClaudeDesktopOneClick() {
  oneClickAttempted.value = true;
  void copy(BASE, "desktop-one-click");
  window.location.href = `claude://add-connector?url=${encodeURIComponent(BASE)}`;
}

function tryCursorOneClick() {
  oneClickAttempted.value = true;
  void copy(MCP_URL, "cursor-one-click");
  window.location.href = cursorDeepLink.value;
}

function startConnectionPoll() {
  connectionCountAtStart.value = connections.list.length;
  if (!pollHandle.value) {
    pollHandle.value = setInterval(() => connections.refresh(), 3000);
  }
}

function stopConnectionPoll() {
  if (pollHandle.value) {
    clearInterval(pollHandle.value);
    pollHandle.value = null;
  }
}

// Auto-advance to step 3 the moment a brand-new connection appears.
watch(
  () => connections.list.length,
  (next) => {
    if (step.value === 2 && next > connectionCountAtStart.value) {
      step.value = 3;
      stopConnectionPoll();
    }
  },
);

watch(step, (s) => {
  if (s === 2) startConnectionPoll();
  else stopConnectionPoll();
});

onBeforeUnmount(stopConnectionPoll);

// ----- Step 3 / finish -----------------------------------------------------

function markDone() {
  try {
    localStorage.setItem(ONBOARDING_FLAG, "1");
  } catch {
    /* ignore — private mode etc. */
  }
}

function finish() {
  markDone();
  if (createdSlug.value) {
    router.replace(`/p/${createdSlug.value}`);
  } else if (projects.list.length > 0) {
    router.replace(`/p/${projects.list[0]!.slug}`);
  } else {
    router.replace("/p");
  }
}

function skipAll() {
  markDone();
  router.replace("/p");
}

// ----- Lifecycle -----------------------------------------------------------

onMounted(async () => {
  if (!auth.isAuthed) {
    router.replace({ path: "/login", query: { next: "/welcome" } });
    return;
  }
  await Promise.all([projects.fetchList(), connections.refresh()]);

  // Resume in the right step if user reloads mid-flow.
  if (projects.list.length > 0 && step.value === 1) {
    createdSlug.value = projects.list[0]!.slug;
    step.value = 2;
  }
  if (
    step.value === 2 &&
    connections.list.some((c) => c.type === "oauth")
  ) {
    step.value = 3;
  }
});
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] px-6 py-12">
    <div class="w-full max-w-[640px] mx-auto">
      <!-- Header brand mark -->
      <div class="flex items-center gap-2 mb-10 text-fg-subtle">
        <span class="text-signal-green font-mono text-section">◈</span>
        <span class="font-mono text-small tracking-[0.08em] uppercase">Vibecell · welcome</span>
      </div>

      <!-- Step indicator: 01 / 02 / 03 -->
      <ol class="flex items-center gap-3 mb-10 select-none">
        <li
          v-for="(n, i) in [1, 2, 3] as const"
          :key="n"
          class="flex items-center gap-3 flex-1"
        >
          <div class="flex items-center gap-2.5 min-w-0">
            <span
              class="w-7 h-7 rounded-md flex items-center justify-center font-mono text-[11px] tracking-tight transition-colors"
              :style="
                step === n
                  ? { background: 'var(--signal-green)', color: 'var(--bg-body-to)', boxShadow: '0 0 0 1px var(--signal-green), 0 0 12px rgba(92,200,164,0.25)' }
                  : step > n
                  ? { background: 'var(--signal-green-bg)', color: 'var(--signal-green)', border: '1px solid var(--signal-green)' }
                  : { background: 'transparent', color: 'var(--fg-subtle)', border: '1px solid var(--border)' }
              "
            >
              {{ String(n).padStart(2, "0") }}
            </span>
            <span
              class="font-mono text-small uppercase tracking-[0.06em] truncate"
              :style="step === n ? { color: 'var(--fg-primary)' } : { color: 'var(--fg-subtle)' }"
            >
              {{ n === 1 ? "first project" : n === 2 ? "pair editor" : "console live" }}
            </span>
          </div>
          <span
            v-if="i < 2"
            class="flex-1 h-px"
            :style="{
              background:
                step > n ? 'var(--signal-green)' : 'var(--border)',
            }"
          />
        </li>
      </ol>

      <!-- ─── STEP 1 · spin up first project ─────────────────────────────── -->
      <transition
        enter-from-class="opacity-0 translate-y-1"
        enter-active-class="transition-all duration-med ease-out"
        enter-to-class="opacity-100 translate-y-0"
        mode="out-in"
      >
        <section v-if="step === 1" key="step-1" class="glass rounded-lg p-7">
          <header class="mb-6">
            <MonoLabel>step 01</MonoLabel>
            <h1 class="text-display text-fg-primary tracking-tight mt-2">
              Spin up your first project.
            </h1>
            <p class="text-body text-fg-muted mt-2">
              Vibecell tracks one project at a time. Name it, ship it, log it.
              You can rename, archive, or import more anytime.
            </p>
          </header>

          <form class="flex flex-col gap-4" @submit.prevent="createProject">
            <div class="grid grid-cols-[1fr_120px] gap-3">
              <TextField
                v-model="projectName"
                label="name"
                placeholder="Butlr"
                :autofocus="true"
              />
              <TextField v-model="projectEmoji" label="emoji" placeholder="📦" />
            </div>
            <TextField
              v-model="projectSlug"
              label="slug"
              placeholder="butlr"
              :error="createError"
            />

            <div class="flex items-center justify-between mt-2">
              <RouterLink
                to="/import/github"
                class="font-mono text-small text-fg-subtle hover:text-fg-body transition-colors inline-flex items-center gap-1.5"
              >
                <span aria-hidden="true">↗</span>
                <span>or import from GitHub</span>
              </RouterLink>
              <PrimaryButton
                type="submit"
                size="lg"
                :disabled="!canCreate"
                :loading="creating"
              >
                <span>Create &amp; continue</span>
                <span v-if="!creating" class="font-mono text-small opacity-70" aria-hidden="true">⏎</span>
              </PrimaryButton>
            </div>
          </form>

          <footer class="mt-7 pt-5 border-t border-border flex items-center justify-between">
            <span class="font-mono text-small text-fg-subtle">// 1 of 3 · ~30s remaining</span>
            <button
              type="button"
              class="text-small text-fg-subtle hover:text-fg-body transition-colors"
              @click="skipAll"
            >
              Skip onboarding →
            </button>
          </footer>
        </section>

        <!-- ─── STEP 2 · pair editor ───────────────────────────────────── -->
        <section v-else-if="step === 2" key="step-2" class="glass rounded-lg p-7">
          <header class="mb-6">
            <MonoLabel>step 02</MonoLabel>
            <h1 class="text-display text-fg-primary tracking-tight mt-2">
              Pair your editor.
            </h1>
            <p class="text-body text-fg-muted mt-2">
              The Vibecell MCP plugs straight into Claude Desktop, Claude Code, Cursor &amp; co.
              Sign-in once, no env vars, no API keys. We'll auto-advance the moment we see your first call.
            </p>
          </header>

          <!-- Tabs -->
          <nav class="flex gap-1 mb-5 border-b border-border flex-wrap">
            <button
              v-for="t in (['claude-desktop', 'claude-code', 'cursor', 'zed', 'windsurf'] as const)"
              :key="t"
              type="button"
              class="px-3 py-2 text-small transition-colors"
              :class="tab === t
                ? 'text-fg-primary border-b-2 border-signal-green -mb-px'
                : 'text-fg-muted hover:text-fg-body'"
              @click="tab = t"
            >
              {{
                t === "claude-desktop" ? "Claude Desktop" :
                t === "claude-code" ? "Claude Code" :
                t === "cursor" ? "Cursor" :
                t === "zed" ? "Zed" : "Windsurf"
              }}
            </button>
          </nav>

          <!-- Claude Desktop -->
          <div v-if="tab === 'claude-desktop'" class="space-y-4">
            <PrimaryButton class="w-full" @click="tryClaudeDesktopOneClick">
              {{ oneClickAttempted ? "Retry — open Claude Desktop" : "One-click · Add to Claude Desktop →" }}
            </PrimaryButton>
            <p v-if="oneClickAttempted" class="text-small text-fg-muted text-center">
              Nothing happened? The URL is on your clipboard. Paste it into
              <strong>Settings → Connectors → Add Remote Server</strong>.
            </p>
            <details class="group" :open="oneClickAttempted">
              <summary class="cursor-pointer text-small text-fg-muted hover:text-fg-body select-none transition-colors">
                <span class="group-open:hidden">Manual setup</span>
                <span class="hidden group-open:inline">Manual ▾</span>
              </summary>
              <ol class="text-body text-fg-body space-y-2 mt-3 list-none pl-0">
                <li><span class="font-mono text-fg-subtle">1.</span> Claude Desktop → <strong>Settings → Connectors</strong></li>
                <li><span class="font-mono text-fg-subtle">2.</span> <strong>Add Remote Server</strong></li>
                <li><span class="font-mono text-fg-subtle">3.</span> Paste the URL below + finish OAuth in your browser</li>
              </ol>
              <div class="flex items-center gap-2 mt-3 p-3 rounded-md" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.1)">
                <code class="flex-1 text-small font-mono text-fg-body truncate">{{ BASE }}</code>
                <button
                  type="button"
                  class="shrink-0 text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border transition-colors"
                  @click="copy(BASE, 'desktop-url')"
                >{{ copiedKey === 'desktop-url' ? "✓ Copied" : "Copy" }}</button>
              </div>
            </details>
          </div>

          <!-- Claude Code -->
          <div v-else-if="tab === 'claude-code'" class="space-y-4">
            <p class="text-small text-fg-muted">Run this in your terminal:</p>
            <div class="flex items-center gap-2 p-3 rounded-md" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.12)">
              <code class="flex-1 text-small font-mono text-fg-primary break-all">{{ claudeCodeCommand }}</code>
              <PrimaryButton class="shrink-0" @click="copy(claudeCodeCommand, 'cc-cmd')">
                {{ copiedKey === 'cc-cmd' ? "✓" : "Copy" }}
              </PrimaryButton>
            </div>
            <p class="text-small text-fg-subtle">
              OAuth opens in your browser on the first tool call. No env vars, no restart.
            </p>
          </div>

          <!-- Cursor -->
          <div v-else-if="tab === 'cursor'" class="space-y-4">
            <PrimaryButton class="w-full" @click="tryCursorOneClick">
              One-click · Add to Cursor →
            </PrimaryButton>
            <p class="text-small text-fg-subtle text-center">
              Pre-fills the MCP server config in Cursor. Confirm in-app to install.
            </p>
            <details class="group">
              <summary class="cursor-pointer text-small text-fg-muted hover:text-fg-body select-none">
                <span class="group-open:hidden">Manual setup</span>
                <span class="hidden group-open:inline">Manual ▾</span>
              </summary>
              <ol class="text-body text-fg-body space-y-2 mt-3 list-none pl-0">
                <li><span class="font-mono text-fg-subtle">1.</span> Cursor → <strong>Settings → MCP</strong> → Add remote server</li>
                <li><span class="font-mono text-fg-subtle">2.</span> Paste URL below, finish OAuth in browser</li>
              </ol>
              <div class="flex items-center gap-2 mt-3 p-3 rounded-md" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.1)">
                <code class="flex-1 text-small font-mono text-fg-body truncate">{{ MCP_URL }}</code>
                <button
                  type="button"
                  class="shrink-0 text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border transition-colors"
                  @click="copy(MCP_URL, 'cursor-url')"
                >{{ copiedKey === 'cursor-url' ? "✓ Copied" : "Copy" }}</button>
              </div>
            </details>
          </div>

          <!-- Zed -->
          <div v-else-if="tab === 'zed'" class="space-y-4">
            <p class="text-small text-fg-muted">
              Zed needs <code class="font-mono">mcp-remote</code> as the stdio bridge. Add to <code class="font-mono">settings.json</code>:
            </p>
            <pre class="rounded-md p-3 text-small font-mono overflow-x-auto" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.1); color:#cfd4dc">{{ zedConfig }}</pre>
            <div class="flex justify-end">
              <button
                type="button"
                class="text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border transition-colors"
                @click="copy(zedConfig, 'zed-json')"
              >{{ copiedKey === 'zed-json' ? "✓ Copied" : "Copy JSON" }}</button>
            </div>
          </div>

          <!-- Windsurf -->
          <div v-else class="space-y-4">
            <div class="flex items-center gap-2 p-3 rounded-md" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.12)">
              <code class="flex-1 text-small font-mono text-fg-primary break-all">{{ windsurfCommand }}</code>
              <PrimaryButton class="shrink-0" @click="copy(windsurfCommand, 'ws-cmd')">
                {{ copiedKey === 'ws-cmd' ? "✓" : "Copy" }}
              </PrimaryButton>
            </div>
            <p class="text-small text-fg-subtle">
              Or: Windsurf → Cascade → MCP Servers → Add Remote Server, paste <code class="font-mono">{{ MCP_URL }}</code>.
            </p>
          </div>

          <footer class="mt-7 pt-5 border-t border-border flex items-center justify-between">
            <span class="font-mono text-small text-fg-subtle inline-flex items-center gap-2">
              <span class="w-1.5 h-1.5 rounded-full bg-fg-subtle animate-pulse" />
              waiting for first tool call…
            </span>
            <button
              type="button"
              class="text-small text-fg-subtle hover:text-fg-body transition-colors"
              @click="step = 3"
            >
              I'll do this later →
            </button>
          </footer>
        </section>

        <!-- ─── STEP 3 · console live ──────────────────────────────────── -->
        <section v-else key="step-3" class="glass rounded-lg p-7">
          <header class="mb-6">
            <MonoLabel>step 03</MonoLabel>
            <h1 class="text-display text-fg-primary tracking-tight mt-2">
              Console live.
            </h1>
            <p class="text-body text-fg-muted mt-2">
              Vibecell now logs sessions, tracks todos, records ships, and stitches it all into
              a project console you can resurrect on any device.
            </p>
          </header>

          <ul class="space-y-3">
            <li class="flex items-start gap-3 p-4 rounded-md" style="background: var(--bg-elevated); border: 1px solid var(--border)">
              <span class="font-mono text-section text-signal-green leading-none">◢</span>
              <div class="min-w-0">
                <p class="text-body text-fg-primary font-medium">Open your project console</p>
                <p class="text-small text-fg-muted mt-0.5">All-in-one cockpit: focus, todos, decisions, ships, telemetry.</p>
              </div>
            </li>
            <li class="flex items-start gap-3 p-4 rounded-md" style="background: var(--bg-elevated); border: 1px solid var(--border)">
              <span class="font-mono text-section text-signal-green leading-none">◇</span>
              <div class="min-w-0">
                <p class="text-body text-fg-primary font-medium">Tell Claude what you want</p>
                <p class="text-small text-fg-muted mt-0.5">Vibecell auto-logs commits and silent drift. The SKILL takes over from here.</p>
              </div>
            </li>
            <li class="flex items-start gap-3 p-4 rounded-md" style="background: var(--bg-elevated); border: 1px solid var(--border)">
              <span class="font-mono text-section text-signal-green leading-none">↑</span>
              <div class="min-w-0">
                <p class="text-body text-fg-primary font-medium">Ship.</p>
                <p class="text-small text-fg-muted mt-0.5">When it's live, hit Ship and we changelog it for you.</p>
              </div>
            </li>
          </ul>

          <footer class="mt-7 pt-5 border-t border-border flex items-center justify-between">
            <span class="font-mono text-small text-fg-subtle">// 7-day trial active · cancel anytime</span>
            <PrimaryButton size="lg" @click="finish">
              <span>Open project →</span>
            </PrimaryButton>
          </footer>
        </section>
      </transition>
    </div>
  </div>
</template>
