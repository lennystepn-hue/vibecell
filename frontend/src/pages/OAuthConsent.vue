<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";

interface ConsentContext {
  client_id: string;
  client_name: string | null;
  redirect_uri: string;
  scope: string;
  state: string;
  workspaces: { id: string; slug: string; name: string }[];
}

const route = useRoute();
const consent = ref<ConsentContext | null>(null);
const error = ref<string | null>(null);
const pickedWs = ref<string>("");
const submitting = ref(false);

onMounted(async () => {
  const state = (route.query.state as string) || "";
  if (!state) {
    error.value = "Missing state — open this page via the OAuth authorize URL.";
    return;
  }
  try {
    const resp = await fetch(`/oauth/consent-context?state=${encodeURIComponent(state)}`, {
      credentials: "include",
      headers: { Accept: "application/json" },
    });
    if (!resp.ok) {
      throw new Error(`Status ${resp.status}`);
    }
    consent.value = await resp.json();
    pickedWs.value = consent.value?.workspaces[0]?.id ?? "";
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Failed to load consent context";
  }
});

const clientIcon = computed(() => {
  const n = (consent.value?.client_name ?? "").toLowerCase();
  if (n.includes("claude")) return "🔷";
  if (n.includes("cursor")) return "📐";
  if (n.includes("zed")) return "⚡";
  if (n.includes("windsurf")) return "🪂";
  return "🔌";
});

async function allow() {
  if (!consent.value || !pickedWs.value) return;
  submitting.value = true;
  try {
    const resp = await fetch("/oauth/grant", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ state: consent.value.state, workspace_id: pickedWs.value }),
    });
    if (!resp.ok) {
      error.value = `Grant failed (${resp.status})`;
      return;
    }
    const data = await resp.json();
    if (data.redirect) {
      window.location.href = data.redirect;
    } else {
      error.value = "Grant succeeded but no redirect URL returned.";
    }
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Grant request failed";
  } finally {
    submitting.value = false;
  }
}

async function deny() {
  if (!consent.value) return;
  try {
    const resp = await fetch("/oauth/deny", {
      method: "POST",
      credentials: "include",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ state: consent.value.state, workspace_id: "" }),
    });
    if (resp.ok) {
      const data = await resp.json();
      if (data.redirect) {
        window.location.href = data.redirect;
        return;
      }
    }
    error.value = `Deny failed (${resp.status})`;
  } catch (e: unknown) {
    error.value = e instanceof Error ? e.message : "Deny request failed";
  }
}
</script>

<template>
  <div class="max-w-[560px] mx-auto px-6 py-12">
    <header class="mb-6">
      <h1 class="text-display text-fg-primary tracking-tight">Connect to Vibecell</h1>
      <p class="text-body text-fg-muted mt-1" v-if="consent">
        {{ consent.client_name || "An MCP client" }} wants to connect
      </p>
    </header>

    <div v-if="error" class="glass rounded-lg p-4 border border-signal-red/40 text-signal-red">
      {{ error }}
    </div>

    <div v-else-if="!consent" class="text-fg-muted mono-label">loading consent context…</div>

    <div v-else class="space-y-5">
      <div class="glass rounded-lg p-4 flex items-start gap-3">
        <div class="w-10 h-10 rounded-md bg-bg-surface-hi flex items-center justify-center text-xl shrink-0">
          {{ clientIcon }}
        </div>
        <div class="min-w-0">
          <div class="text-body text-fg-primary font-medium">
            {{ consent.client_name || "Unnamed MCP Client" }}
          </div>
          <div class="text-small text-fg-muted mt-0.5">
            Client ID: <span class="font-mono">{{ consent.client_id.slice(0, 24) }}…</span>
          </div>
          <div class="text-small text-fg-muted mt-0.5 break-all">
            Redirects to: <span class="font-mono">{{ consent.redirect_uri }}</span>
          </div>
        </div>
      </div>

      <section>
        <h2 class="text-small mono-label text-fg-muted mb-2">It will be able to:</h2>
        <ul class="text-body text-fg-body space-y-1">
          <li>✓ Read your projects, sessions, decisions, ideas, notes</li>
          <li>✓ Log sessions, create decisions, capture ideas</li>
          <li>✓ Append to project notes, record ships</li>
          <li>✓ Update project context (focus, next step, open questions)</li>
          <li class="text-fg-muted">✗ Cannot run local commands (CLI-only)</li>
          <li class="text-fg-muted">✗ Cannot access other workspaces</li>
        </ul>
      </section>

      <section>
        <label class="text-small mono-label text-fg-muted block mb-2">Connect to workspace</label>
        <select
          v-model="pickedWs"
          class="w-full h-11 px-3 rounded-md bg-bg-surface border border-border text-fg-body"
        >
          <option v-for="w in consent.workspaces" :key="w.id" :value="w.id">
            {{ w.name }} ({{ w.slug }})
          </option>
        </select>
      </section>

      <div class="flex justify-end gap-2 pt-4">
        <button class="px-3 py-2 text-body text-fg-muted hover:text-fg-body" @click="deny">
          Deny
        </button>
        <PrimaryButton :disabled="submitting" @click="allow">
          {{ submitting ? "Connecting…" : "Allow & Connect" }}
        </PrimaryButton>
      </div>

      <p class="text-small text-fg-muted pt-4 border-t border-border">
        You can revoke this connection anytime at
        <RouterLink to="/settings/connections" class="text-fg-body underline">
          vibecell.dev/settings/connections
        </RouterLink>
      </p>
    </div>
  </div>
</template>
