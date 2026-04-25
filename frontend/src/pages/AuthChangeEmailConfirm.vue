<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

type State =
  | { kind: "confirming" }
  | { kind: "ok"; newEmail: string }
  | { kind: "error"; detail: string };

const state = ref<State>({ kind: "confirming" });

onMounted(async () => {
  const token = route.params.token;
  if (typeof token !== "string" || !token) {
    state.value = { kind: "error", detail: "missing token" };
    return;
  }
  try {
    const r = await fetch("/api/v1/me/change-email/confirm", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
    });
    if (r.ok) {
      const body = await r.json();
      state.value = { kind: "ok", newEmail: body.email };
      // Refresh /me so the navbar + Settings show the new address.
      try {
        await auth.refresh();
      } catch {
        /* non-fatal — UI will reload itself when user navigates */
      }
    } else {
      let detail = `confirm failed (HTTP ${r.status})`;
      try {
        const body = await r.json();
        if (body?.detail) {
          detail =
            typeof body.detail === "string"
              ? body.detail
              : JSON.stringify(body.detail);
        }
      } catch {
        /* keep generic */
      }
      state.value = { kind: "error", detail };
    }
  } catch (e) {
    state.value = {
      kind: "error",
      detail: `network error: ${e instanceof Error ? e.message : String(e)}`,
    };
  }
});

function goSettings() {
  router.replace({ name: "settings" });
}

function goLogin() {
  router.replace({ name: "login" });
}
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] flex items-center justify-center px-6">
    <div v-if="state.kind === 'confirming'" class="flex flex-col items-center gap-3 text-fg-muted">
      <svg
        class="animate-spin h-6 w-6 text-signal-green"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.3" stroke-width="2" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" />
      </svg>
      <p class="mono-label">// confirming change</p>
    </div>

    <div v-else-if="state.kind === 'ok'" class="flex flex-col items-center gap-5 max-w-sm text-center">
      <h1 class="text-title text-fg-primary">Email updated</h1>
      <p class="text-fg-muted">
        Your account is now associated with <span class="font-mono text-fg-body">{{ state.newEmail }}</span>.
      </p>
      <button
        type="button"
        class="text-body text-signal-blue link"
        @click="goSettings"
      >
        → back to settings
      </button>
    </div>

    <div v-else class="flex flex-col items-center gap-5 max-w-sm text-center">
      <h1 class="text-title text-fg-primary">Bad link</h1>
      <p class="text-fg-muted font-mono text-small">{{ state.detail }}</p>
      <p class="text-fg-muted">
        The link may have expired (24h limit), already been used, or the destination email is now taken by another account.
      </p>
      <button
        type="button"
        class="text-body text-signal-blue link"
        @click="goLogin"
      >
        ← back to sign in
      </button>
    </div>
  </div>
</template>
