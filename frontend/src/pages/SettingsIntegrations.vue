<script setup lang="ts">
import { onMounted, ref } from "vue";

import SettingsNav from "@/components/settings/SettingsNav.vue";
import SettingsSection from "@/components/settings/SettingsSection.vue";

import { api } from "@/api/client";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Integration = components["schemas"]["IntegrationOut"];

const toast = useToastStore();
const loading = ref(true);
const integrations = ref<Integration[]>([]);
const disconnecting = ref(false);

async function load() {
  loading.value = true;
  const { data } = await api.GET("/api/v1/integrations");
  loading.value = false;
  integrations.value = data ?? [];
}

async function disconnectGithub() {
  if (!confirm("Disconnect GitHub? Your existing projects stay; you just lose repo-sync.")) return;
  disconnecting.value = true;
  const { error } = await api.DELETE("/api/v1/integrations/github");
  disconnecting.value = false;
  if (error) {
    toast.push("Couldn't disconnect GitHub", "error");
    return;
  }
  toast.push("GitHub disconnected", "success");
  await load();
}

onMounted(load);

function ghLogin(i: Integration): string {
  return (i.config as { login?: string } | undefined)?.login ?? "—";
}

function connectedOn(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <SettingsNav />
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-[720px] mx-auto px-8 py-8">
        <h1 class="text-display text-fg-primary tracking-tight mb-8">Integrations</h1>

        <div v-if="loading" class="text-fg-muted">
          <p class="mono-label">loading…</p>
        </div>

        <template v-else>
          <SettingsSection title="GitHub" subtitle="Read-only access to repo metadata.">
            <template v-for="i in integrations.filter((x) => x.kind === 'github')" :key="i.id">
              <div class="space-y-3">
                <div class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
                  <span class="mono-label">login</span>
                  <span class="font-mono text-body text-fg-body">{{ ghLogin(i) }}</span>
                </div>
                <div class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
                  <span class="mono-label">connected</span>
                  <span class="font-mono text-small text-fg-subtle">{{ connectedOn(i.connected_at) }}</span>
                </div>
                <div class="flex justify-end pt-2">
                  <button
                    type="button"
                    class="h-10 px-4 rounded-md font-medium text-body transition-colors"
                    :style="{
                      background: 'var(--signal-red-bg)',
                      color: 'var(--signal-red)',
                      border: '1px solid var(--signal-red)',
                    }"
                    :disabled="disconnecting"
                    @click="disconnectGithub"
                  >
                    {{ disconnecting ? "Disconnecting…" : "Disconnect GitHub" }}
                  </button>
                </div>
              </div>
            </template>

            <template v-if="integrations.filter((x) => x.kind === 'github').length === 0">
              <p class="text-fg-muted mb-4">No GitHub integration yet.</p>
              <a
                href="/api/v1/integrations/github/oauth-start"
                class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body"
                :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
              >Connect GitHub</a>
            </template>
          </SettingsSection>

          <SettingsSection title="More integrations" subtitle="Coming in Spec 4+">
            <ul class="space-y-2 text-small text-fg-muted">
              <li>// Stripe — billing + MRR sync</li>
              <li>// Vercel — deploy + build metadata</li>
              <li>// Cloudflare — DNS + domain inventory</li>
              <li>// Linear — task sync to open_questions</li>
            </ul>
          </SettingsSection>
        </template>
      </div>
    </div>
  </div>
</template>
