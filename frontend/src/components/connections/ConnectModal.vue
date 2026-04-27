<script setup lang="ts">
import { computed, ref, watch } from "vue";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { INSTALL_PROMPT_PITCH, VIBECELL_INSTALL_PROMPT } from "@/lib/installPrompt";
import { useConnectionsStore } from "@/stores/connections";

type Tab = "ai-prompt" | "claude-desktop" | "claude-code" | "cursor" | "zed" | "windsurf";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const BASE = "https://vibecell.dev";
const MCP_URL = `${BASE}/mcp`;

const connections = useConnectionsStore();
const tab = ref<Tab>(detectBestTab());
const copiedKey = ref<string | null>(null);
const oneClickAttempted = ref(false);
const connectionCountAtOpen = ref<number>(0);
const pollHandle = ref<ReturnType<typeof setInterval> | null>(null);

// Default tab is the AI-paste prompt — that's the slickest path. The
// per-editor tabs remain for users who prefer the manual flow. We keep
// the auto-detect helper around for the "if the user picks the per-editor
// path, suggest which one" use case (currently unused, but cheap to retain).
function detectBestTab(): Tab {
  return "ai-prompt";
}

const claudeCodeCommand = computed(
  () => `claude mcp add vibecell ${MCP_URL} --transport http --scope user`,
);

const claudeCodeConfig = JSON.stringify({
  mcpServers: {
    vibecell: { type: "http", url: MCP_URL },
  },
}, null, 2);

const cursorDeepLink = computed(() => {
  const config = { name: "vibecell", url: MCP_URL, type: "http" };
  const b64 = btoa(JSON.stringify(config));
  return `cursor://anysphere.cursor-deeplink/mcp/install?name=vibecell&config=${b64}`;
});

const zedConfig = JSON.stringify({
  context_servers: {
    vibecell: {
      command: { path: "npx", args: ["-y", "mcp-remote", MCP_URL] },
    },
  },
}, null, 2);

const windsurfCommand = computed(
  () => `windsurf mcp add vibecell ${MCP_URL} --transport http`,
);

// Close, reset + start/stop polling whenever the modal open state changes.
// Polling lets us show a live "✓ Connected" banner the instant the user
// completes the OAuth dance in another tab.
watch(() => props.open, (isOpen) => {
  if (isOpen) {
    oneClickAttempted.value = false;
    tab.value = detectBestTab();
    void preloadUrl();
    void connections.refresh();
    connectionCountAtOpen.value = connections.list.length;
    if (!pollHandle.value) {
      pollHandle.value = setInterval(() => connections.refresh(), 3000);
    }
  } else {
    if (pollHandle.value) {
      clearInterval(pollHandle.value);
      pollHandle.value = null;
    }
  }
});

// When a NEW connection appears while the modal is open we've succeeded.
const newConnection = computed(() => {
  if (!props.open) return null;
  const extra = connections.list.length - connectionCountAtOpen.value;
  if (extra <= 0) return null;
  // Return the most-recently-connected entry.
  return [...connections.list].sort((a, b) => {
    const ta = a.connected_at ? new Date(a.connected_at).getTime() : 0;
    const tb = b.connected_at ? new Date(b.connected_at).getTime() : 0;
    return tb - ta;
  })[0];
});

async function preloadUrl() {
  // Silently prime the clipboard so paste-anywhere works even before the
  // user clicks the copy button.
  try {
    await navigator.clipboard.writeText(MCP_URL);
  } catch {
    /* clipboard may be denied before a user gesture — ignore */
  }
}

async function copy(text: string, key: string) {
  try {
    await navigator.clipboard.writeText(text);
    copiedKey.value = key;
    setTimeout(() => {
      if (copiedKey.value === key) copiedKey.value = null;
    }, 1800);
  } catch {
    /* clipboard denied — the user can still select manually */
  }
}

function tryClaudeDesktopOneClick() {
  oneClickAttempted.value = true;
  // `claude://` is Claude Desktop's registered URI scheme for adding a remote
  // connector. If Claude Desktop is installed, it pops up asking to confirm
  // the addition. If not installed, the navigation silently fails and we
  // surface the manual-fallback instructions below.
  void copy(BASE, "desktop-one-click");
  window.location.href = `claude://add-connector?url=${encodeURIComponent(BASE)}`;
}

function tryCursorOneClick() {
  oneClickAttempted.value = true;
  void copy(MCP_URL, "cursor-one-click");
  window.location.href = cursorDeepLink.value;
}

function close() {
  emit("close");
}
</script>

<template>
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
      class="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 px-4"
      @click.self="close"
    >
      <div class="glass rounded-xl p-6 max-w-xl w-full shadow-2xl relative">
        <div class="flex items-start justify-between mb-5">
          <div>
            <h2 class="text-display text-fg-primary tracking-tight">Connect your editor</h2>
            <p class="text-small text-fg-muted mt-1">One-click for Claude Desktop & Cursor. Copy-paste for everything else.</p>
          </div>
          <button class="text-fg-muted hover:text-fg-body p-1" @click="close" aria-label="Close">✕</button>
        </div>

        <!-- Live success banner — the instant we see a new connection row -->
        <transition
          enter-active-class="transition-all duration-300"
          enter-from-class="opacity-0 -translate-y-2"
          enter-to-class="opacity-100 translate-y-0"
        >
          <div
            v-if="newConnection"
            class="mb-4 rounded-lg p-4 flex items-center gap-3"
            style="background: rgba(92,200,164,0.09); border: 1px solid rgba(92,200,164,0.3)"
          >
            <span class="w-2 h-2 rounded-full bg-signal-green animate-pulse shrink-0" />
            <div class="flex-1 min-w-0">
              <p class="text-body text-fg-primary font-medium truncate">
                ✓ Connected — {{ newConnection.name }}
              </p>
              <p class="text-small text-fg-muted mt-0.5">
                Claude can now read your projects, log sessions, and record decisions.
              </p>
            </div>
            <button
              class="shrink-0 text-small px-3 py-1.5 rounded bg-signal-green hover:opacity-90 transition-opacity"
              style="color:#070b10"
              @click="close"
            >Done</button>
          </div>
        </transition>

        <nav class="flex gap-1 mb-5 border-b border-border flex-wrap">
          <button
            v-for="t in (['ai-prompt', 'claude-desktop', 'claude-code', 'cursor', 'zed', 'windsurf'] as const)"
            :key="t"
            class="px-3 py-2 text-small transition-colors"
            :class="tab === t
              ? 'text-fg-primary border-b-2 border-signal-green -mb-px'
              : 'text-fg-muted hover:text-fg-body'"
            @click="tab = t"
          >
            <template v-if="t === 'ai-prompt'">
              <span aria-hidden="true" class="text-signal-green mr-1">✦</span>Paste into AI
            </template>
            <template v-else>
              {{
                t === "claude-desktop" ? "Claude Desktop" :
                t === "claude-code" ? "Claude Code" :
                t === "cursor" ? "Cursor" :
                t === "zed" ? "Zed" : "Windsurf"
              }}
            </template>
          </button>
        </nav>

        <!-- ─── AI prompt ─────────────────────────────────────────── -->
        <div v-if="tab === 'ai-prompt'" class="space-y-4">
          <p class="text-small text-fg-muted">{{ INSTALL_PROMPT_PITCH }}</p>
          <div
            class="rounded-md p-4 font-mono text-[12px] leading-relaxed whitespace-pre-wrap select-all"
            style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.12); color:var(--fg-body); max-height:280px; overflow-y:auto"
          >{{ VIBECELL_INSTALL_PROMPT }}</div>
          <PrimaryButton class="w-full" @click="copy(VIBECELL_INSTALL_PROMPT, 'ai-prompt')">
            {{ copiedKey === 'ai-prompt' ? "✓ Copied — paste into your AI" : "Copy prompt" }}
          </PrimaryButton>
          <p class="text-small text-fg-subtle text-center">
            Paste into Claude / Cursor / Zed — it'll handle install + OAuth + first read on its own.
          </p>
        </div>

        <!-- ─── Claude Desktop ─────────────────────────────────────── -->
        <div v-if="tab === 'claude-desktop'" class="space-y-4">
          <PrimaryButton class="w-full" @click="tryClaudeDesktopOneClick">
            {{ oneClickAttempted ? "Retry — open Claude Desktop" : "One-click · Add to Claude Desktop →" }}
          </PrimaryButton>
          <p
            v-if="oneClickAttempted"
            class="text-small text-fg-muted text-center"
          >
            Nothing happened? Claude Desktop may not be installed, or the URI scheme isn't registered yet.
            Use the fallback below — we've pre-copied the URL for you.
          </p>

          <details class="group" :open="oneClickAttempted">
            <summary class="cursor-pointer text-small text-fg-muted hover:text-fg-body select-none transition-colors">
              <span class="group-open:hidden">Manual setup</span>
              <span class="hidden group-open:inline">Manual setup ▾</span>
            </summary>
            <ol class="text-body text-fg-body space-y-2 mt-3 list-none pl-0">
              <li><span class="font-mono text-fg-subtle">1.</span> Open Claude Desktop → <strong>Settings → Connectors</strong></li>
              <li><span class="font-mono text-fg-subtle">2.</span> Click <strong>"Add Remote Server"</strong></li>
              <li><span class="font-mono text-fg-subtle">3.</span> Paste the URL below</li>
              <li><span class="font-mono text-fg-subtle">4.</span> Follow the sign-in prompt in your browser</li>
            </ol>
            <div class="flex items-center gap-2 mt-3 p-3 rounded-md" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.1)">
              <code class="flex-1 text-small font-mono text-fg-body truncate">{{ BASE }}</code>
              <button
                class="shrink-0 text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border transition-colors"
                @click="copy(BASE, 'desktop-url')"
              >{{ copiedKey === 'desktop-url' ? "✓ Copied" : "Copy" }}</button>
            </div>
          </details>
        </div>

        <!-- ─── Claude Code ─────────────────────────────────────────── -->
        <div v-else-if="tab === 'claude-code'" class="space-y-4">
          <div>
            <p class="text-small text-fg-muted mb-2">Run this in your terminal — easiest path:</p>
            <div class="flex items-center gap-2 p-3 rounded-md" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.12)">
              <code class="flex-1 text-small font-mono text-fg-primary break-all">{{ claudeCodeCommand }}</code>
              <PrimaryButton class="shrink-0" @click="copy(claudeCodeCommand, 'cc-cmd')">
                {{ copiedKey === 'cc-cmd' ? "✓" : "Copy" }}
              </PrimaryButton>
            </div>
            <p class="text-small text-fg-subtle mt-2">
              OAuth flow opens in your browser on first tool call. No env vars, no restart needed.
            </p>
          </div>
          <details class="group">
            <summary class="cursor-pointer text-small text-fg-muted hover:text-fg-body select-none">
              <span class="group-open:hidden">Alt: add to <code class="font-mono">.mcp.json</code></span>
              <span class="hidden group-open:inline">.mcp.json ▾</span>
            </summary>
            <pre class="mt-3 rounded-md p-3 text-small font-mono overflow-x-auto" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.1); color:#cfd4dc">{{ claudeCodeConfig }}</pre>
            <div class="flex justify-end mt-2">
              <button
                class="text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border transition-colors"
                @click="copy(claudeCodeConfig, 'cc-json')"
              >{{ copiedKey === 'cc-json' ? "✓ Copied" : "Copy JSON" }}</button>
            </div>
          </details>
        </div>

        <!-- ─── Cursor ──────────────────────────────────────────────── -->
        <div v-else-if="tab === 'cursor'" class="space-y-4">
          <PrimaryButton class="w-full" @click="tryCursorOneClick">
            One-click · Add to Cursor →
          </PrimaryButton>
          <p class="text-small text-fg-subtle text-center">
            Opens Cursor and pre-fills the MCP server config. Confirm in-app to install.
          </p>
          <details class="group">
            <summary class="cursor-pointer text-small text-fg-muted hover:text-fg-body select-none">
              <span class="group-open:hidden">Manual setup</span>
              <span class="hidden group-open:inline">Manual ▾</span>
            </summary>
            <ol class="text-body text-fg-body space-y-2 mt-3 list-none pl-0">
              <li><span class="font-mono text-fg-subtle">1.</span> Cursor → <strong>Settings → Model Context Protocol</strong></li>
              <li><span class="font-mono text-fg-subtle">2.</span> <strong>Add remote server</strong> → paste URL below</li>
              <li><span class="font-mono text-fg-subtle">3.</span> Cursor opens the OAuth consent in your browser</li>
            </ol>
            <div class="flex items-center gap-2 mt-3 p-3 rounded-md" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.1)">
              <code class="flex-1 text-small font-mono text-fg-body truncate">{{ MCP_URL }}</code>
              <button
                class="shrink-0 text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border transition-colors"
                @click="copy(MCP_URL, 'cursor-url')"
              >{{ copiedKey === 'cursor-url' ? "✓ Copied" : "Copy" }}</button>
            </div>
          </details>
        </div>

        <!-- ─── Zed ─────────────────────────────────────────────────── -->
        <div v-else-if="tab === 'zed'" class="space-y-4">
          <p class="text-small text-fg-muted">
            Zed uses <code class="font-mono">mcp-remote</code> as a bridge since it speaks stdio.
            Add this block to <code class="font-mono">settings.json</code>:
          </p>
          <pre class="rounded-md p-3 text-small font-mono overflow-x-auto" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.1); color:#cfd4dc">{{ zedConfig }}</pre>
          <div class="flex justify-end">
            <button
              class="text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border transition-colors"
              @click="copy(zedConfig, 'zed-json')"
            >{{ copiedKey === 'zed-json' ? "✓ Copied" : "Copy JSON" }}</button>
          </div>
        </div>

        <!-- ─── Windsurf ────────────────────────────────────────────── -->
        <div v-else class="space-y-4">
          <div class="flex items-center gap-2 p-3 rounded-md" style="background:rgba(20,33,50,0.5); border:1px solid rgba(138,180,255,0.12)">
            <code class="flex-1 text-small font-mono text-fg-primary break-all">{{ windsurfCommand }}</code>
            <PrimaryButton class="shrink-0" @click="copy(windsurfCommand, 'ws-cmd')">
              {{ copiedKey === 'ws-cmd' ? "✓" : "Copy" }}
            </PrimaryButton>
          </div>
          <p class="text-small text-fg-subtle">
            Alternatively: Windsurf → Settings → Cascade → MCP Servers → Add Remote Server, paste
            <code class="font-mono">{{ MCP_URL }}</code>.
          </p>
        </div>

        <!-- Footer: watching for connection -->
        <div
          v-if="!newConnection"
          class="mt-5 pt-4 border-t border-border flex items-center gap-2 text-small text-fg-subtle"
        >
          <span class="w-1.5 h-1.5 rounded-full bg-fg-subtle animate-pulse" />
          Waiting for first tool call — I'll confirm when your client connects.
        </div>
      </div>
    </div>
  </transition>
</template>
