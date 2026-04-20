<script setup lang="ts">
import { ref } from "vue";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";

defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const tab = ref<"claude-desktop" | "claude-code" | "cursor" | "zed" | "windsurf">("claude-desktop");
const copied = ref(false);

const URL = "https://vibecell.dev";

function tryOneClick() {
  const deepLink = `claude://add-connector?url=${encodeURIComponent(URL)}`;
  window.location.href = deepLink;
}

async function copyUrl() {
  await navigator.clipboard.writeText(URL);
  copied.value = true;
  setTimeout(() => (copied.value = false), 1800);
}
</script>

<template>
  <div
    v-if="open"
    class="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50"
    @click.self="emit('close')"
  >
    <div class="glass rounded-lg p-6 max-w-lg w-full mx-4">
      <div class="flex items-start justify-between mb-4">
        <h2 class="text-display text-fg-primary tracking-tight">Connect your editor</h2>
        <button class="text-fg-muted hover:text-fg-body" @click="emit('close')">✕</button>
      </div>

      <nav class="flex gap-1 mb-4 border-b border-border flex-wrap">
        <button
          v-for="t in ['claude-desktop', 'claude-code', 'cursor', 'zed', 'windsurf']"
          :key="t"
          class="px-3 py-2 text-small text-fg-muted hover:text-fg-body transition-colors"
          :class="{ 'text-fg-primary border-b-2 border-signal-green -mb-px': tab === t }"
          @click="tab = t as any"
        >
          {{
            t === "claude-desktop" ? "Claude Desktop" :
            t === "claude-code" ? "Claude Code" :
            t === "cursor" ? "Cursor" :
            t === "zed" ? "Zed" : "Windsurf"
          }}
        </button>
      </nav>

      <div v-if="tab === 'claude-desktop'">
        <PrimaryButton @click="tryOneClick" class="w-full mb-4">
          Try one-click · opens Claude Desktop
        </PrimaryButton>
        <p class="text-small text-fg-muted text-center mb-4">— or copy the URL manually —</p>
        <ol class="text-body text-fg-body space-y-2 mb-4 list-none pl-0">
          <li>1. Open Claude Desktop → Settings → Connectors</li>
          <li>2. Click "Add Remote Server"</li>
          <li>3. Paste the URL below</li>
          <li>4. Follow the sign-in prompt in your browser</li>
        </ol>
      </div>

      <div v-else-if="tab === 'claude-code'">
        <p class="text-body text-fg-body mb-4">
          In your project's <code class="font-mono text-small">.mcp.json</code>:
        </p>
        <pre class="glass rounded p-3 text-small font-mono overflow-x-auto mb-4">{{ `{
  "mcpServers": {
    "vibecell": {
      "type": "http",
      "url": "${URL}/mcp"
    }
  }
}` }}</pre>
        <p class="text-small text-fg-muted">Claude Code discovers the OAuth flow automatically on first tool call.</p>
      </div>

      <div v-else-if="tab === 'cursor'">
        <ol class="text-body text-fg-body space-y-2 mb-4 list-none pl-0">
          <li>1. Cursor → Settings → Model Context Protocol</li>
          <li>2. Add remote server with the URL below</li>
          <li>3. Cursor prompts for OAuth in your browser</li>
        </ol>
      </div>

      <div v-else-if="tab === 'zed'">
        <ol class="text-body text-fg-body space-y-2 mb-4 list-none pl-0">
          <li>1. Zed → Settings → AI → Context Servers</li>
          <li>2. Click "Add Remote", paste URL below</li>
        </ol>
      </div>

      <div v-else>
        <ol class="text-body text-fg-body space-y-2 mb-4 list-none pl-0">
          <li>1. Windsurf → Settings → Cascade → MCP Servers</li>
          <li>2. Click "Add Remote Server", paste URL below</li>
        </ol>
      </div>

      <div class="flex items-center gap-2 glass rounded-md p-3">
        <code class="flex-1 text-small font-mono text-fg-body truncate">{{ URL }}</code>
        <button
          class="shrink-0 text-small text-fg-muted hover:text-fg-body px-3 py-1 rounded border border-border"
          @click="copyUrl"
        >
          {{ copied ? "✓ Copied" : "Copy" }}
        </button>
      </div>

      <p class="text-small text-fg-muted mt-4 pt-4 border-t border-border">
        Works with any MCP client. <code class="font-mono">vibecell.run</code> (local command execution)
        needs the <code class="font-mono">hangar</code> CLI —
        install with <code class="font-mono">curl vibecell.dev/install.sh | sh</code>.
      </p>
    </div>
  </div>
</template>
