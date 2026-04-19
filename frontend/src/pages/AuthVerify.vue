<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const state = ref<"verifying" | "error">("verifying");

onMounted(() => {
  const token = route.query.token;
  if (typeof token !== "string" || !token) {
    state.value = "error";
    return;
  }
  // Hand off to the backend route which sets the cookie and 303s back to /.
  // Cross-origin fetch can't follow 303+Set-Cookie for session auth, so we
  // redirect the browser itself.
  window.location.replace(`/api/v1/auth/verify?token=${encodeURIComponent(token)}`);
});

function goLogin() {
  router.replace({ name: "login" });
}
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] flex items-center justify-center px-6">
    <div v-if="state === 'verifying'" class="flex flex-col items-center gap-3 text-fg-muted">
      <svg
        class="animate-spin h-6 w-6 text-signal-green"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.3" stroke-width="2" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" />
      </svg>
      <p class="mono-label">// signing in</p>
    </div>
    <div v-else class="flex flex-col items-center gap-5 max-w-sm text-center">
      <h1 class="text-title text-fg-primary">Bad link</h1>
      <p class="text-fg-muted">
        The token is missing or malformed. It may have already been used — try requesting a new magic link.
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
