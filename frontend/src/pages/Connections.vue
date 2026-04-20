<script setup lang="ts">
import { onMounted, ref } from "vue";

import ConnectModal from "@/components/connections/ConnectModal.vue";
import SettingsNav from "@/components/settings/SettingsNav.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useConnectionsStore } from "@/stores/connections";
import type { Connection } from "@/stores/connections";

const connections = useConnectionsStore();
const revokeTarget = ref<Connection | null>(null);
const revoking = ref(false);
const connectOpen = ref(false);

onMounted(() => connections.refresh());

function relative(ts: string | null): string {
  if (!ts) return "never";
  const ms = Date.now() - new Date(ts).getTime();
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

async function confirmRevoke() {
  if (!revokeTarget.value) return;
  revoking.value = true;
  try {
    await connections.revoke(revokeTarget.value.id, revokeTarget.value.type);
    revokeTarget.value = null;
  } finally {
    revoking.value = false;
  }
}
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <SettingsNav />
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-[900px] mx-auto px-8 py-8">
        <header class="mb-6">
          <h1 class="text-display text-fg-primary tracking-tight">Connections</h1>
          <p class="text-body text-fg-muted mt-1">Apps and clients with access to your workspaces.</p>
        </header>

        <div v-if="connections.loading && connections.list.length === 0" class="text-fg-muted mono-label">
          loading…
        </div>

        <div v-else-if="connections.error" class="glass rounded-lg p-4 border border-signal-red/40 text-signal-red">
          {{ connections.error }}
        </div>

        <div v-else-if="connections.list.length === 0" class="glass rounded-lg p-6 text-center text-fg-muted">
          No connections yet. Connect Claude Desktop, Cursor, Zed, or another MCP client
          to get started — see <RouterLink to="/" class="text-fg-body underline">home</RouterLink>.
        </div>

        <div v-else class="space-y-3">
          <div
            v-for="c in connections.list"
            :key="c.id"
            class="glass rounded-lg p-4"
          >
            <div class="flex items-start justify-between gap-4">
              <div class="flex items-start gap-3 min-w-0">
                <div class="w-10 h-10 rounded-md bg-bg-surface-hi flex items-center justify-center text-lg shrink-0">
                  <span v-if="c.icon === 'claude'">🔷</span>
                  <span v-else-if="c.icon === 'cursor'">📐</span>
                  <span v-else-if="c.icon === 'zed'">⚡</span>
                  <span v-else-if="c.icon === 'windsurf'">🪂</span>
                  <span v-else-if="c.icon === 'cli'">🪄</span>
                  <span v-else>🔌</span>
                </div>
                <div class="min-w-0 flex-1">
                  <div class="text-body text-fg-primary font-medium truncate">{{ c.name }}</div>
                  <div class="text-small text-fg-muted mt-0.5">
                    {{ c.type === "oauth" ? "MCP client" : "Paired device" }} ·
                    Connected {{ relative(c.connected_at) }} · Last used {{ relative(c.last_used_at) }}
                  </div>
                  <div v-if="c.type === 'oauth'" class="text-small text-fg-muted mt-1 tabular-nums">
                    {{ c.tool_calls_today }} tool calls today · {{ c.tool_calls_total }} total
                  </div>
                </div>
              </div>
              <button
                class="shrink-0 text-small text-fg-muted hover:text-signal-red px-3 py-1.5 rounded border border-border hover:border-signal-red transition-colors"
                @click="revokeTarget = c"
              >
                {{ c.type === "cli" ? "Unpair" : "Revoke" }}
              </button>
            </div>
          </div>
        </div>

        <div class="mt-8">
          <button
            class="text-small text-fg-muted hover:text-fg-body transition-colors"
            @click="connectOpen = true"
          >
            + Connect another app
          </button>
        </div>
      </div>
    </div>

    <ConnectModal :open="connectOpen" @close="connectOpen = false" />

    <!-- Revoke confirm modal -->
    <div
      v-if="revokeTarget"
      class="fixed inset-0 bg-black/40 backdrop-blur-sm flex items-center justify-center z-50"
      @click.self="revokeTarget = null"
    >
      <div class="glass rounded-lg p-6 max-w-md w-full mx-4">
        <h3 class="text-body text-fg-primary font-medium">
          {{ revokeTarget.type === "cli" ? "Unpair" : "Revoke" }} {{ revokeTarget.name }}?
        </h3>
        <p class="text-small text-fg-muted mt-2">
          This will disconnect {{ revokeTarget.name }} immediately. You can reconnect anytime.
        </p>
        <div class="flex justify-end gap-2 mt-6">
          <button
            class="px-3 py-2 text-body text-fg-muted hover:text-fg-body"
            @click="revokeTarget = null"
          >
            Cancel
          </button>
          <PrimaryButton :disabled="revoking" @click="confirmRevoke">
            {{ revoking ? "Revoking…" : (revokeTarget.type === "cli" ? "Unpair" : "Revoke") }}
          </PrimaryButton>
        </div>
      </div>
    </div>
  </div>
</template>
