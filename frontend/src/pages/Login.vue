<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import InputField from "@/components/ui/InputField.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

// Google login button only renders when the backend says it's configured —
// keeps the form clean on local dev / installs that haven't wired up
// HANGAR_GOOGLE_CLIENT_ID yet.
const googleConfigured = ref(false);

// Surface ?err= from the OAuth callback so the user knows why they bounced
// back to /login (eg "google_failed" / "google_access_denied"). Maps known
// codes to plain English; unknown codes show as-is.
const oauthError = ref<string | null>(null);
const ERROR_MESSAGES: Record<string, string> = {
  google_failed: "Google sign-in didn't complete — try again or use the magic link.",
  google_no_code: "Google didn't send back a code — try again.",
  google_not_configured: "Google sign-in isn't configured on this server yet.",
  google_access_denied: "You didn't approve the Google sign-in. No worries — try again or use the magic link.",
};

// If the user is already signed in (session cookie still valid), the login
// form is pointless — bounce straight to the dashboard. Covers the case
// where someone bookmarks /login or clicks "Sign in →" on a stale tab.
onMounted(async () => {
  if (auth.isAuthed) {
    router.replace("/p");
    return;
  }
  // Pick up ?err= from a previous OAuth bounce.
  const errParam = typeof route.query.err === "string" ? route.query.err : null;
  if (errParam) {
    oauthError.value = ERROR_MESSAGES[errParam] ?? errParam.replace(/_/g, " ");
  }
  // Probe backend for Google availability (cheap unauth GET).
  try {
    const res = await fetch("/api/v1/auth/google/configured");
    if (res.ok) {
      const data = (await res.json()) as { configured: boolean };
      googleConfigured.value = !!data.configured;
    }
  } catch {
    /* network error — leave button hidden */
  }
});

function googleSignIn() {
  // Server-side route handles state + PKCE + redirect to Google. We just
  // hand off the browser; no fetch / fetch-redirect dance because Google
  // would CORS-block the consent UI.
  const next = typeof route.query.next === "string" ? route.query.next : "/p";
  window.location.href = `/api/v1/auth/google/start?next=${encodeURIComponent(next)}`;
}

const email = ref("");
const submitting = ref(false);
const submitted = ref(false);
const error = ref<string | null>(null);

function isValidEmail(value: string): boolean {
  // Minimal syntactic check; server is authoritative.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

async function onSubmit() {
  error.value = null;
  if (!isValidEmail(email.value)) {
    error.value = "That doesn't look like an email.";
    return;
  }
  submitting.value = true;
  try {
    const ok = await auth.requestMagicLink(email.value);
    if (ok) {
      submitted.value = true;
    } else {
      error.value = "Couldn't send the link. Try again in a minute.";
    }
  } finally {
    submitting.value = false;
  }
}

function reset() {
  submitted.value = false;
  email.value = "";
  error.value = null;
}
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] flex items-center justify-center px-6">
    <div class="w-full max-w-[380px]">
      <div class="flex items-center gap-2 mb-10 text-fg-subtle">
        <span class="text-signal-green font-mono text-section">◈</span>
        <span class="font-mono text-small tracking-[0.08em] uppercase">Vibecell</span>
      </div>

      <transition
        enter-from-class="opacity-0 translate-y-1"
        enter-active-class="transition-all duration-med ease-out"
        enter-to-class="opacity-100 translate-y-0"
        leave-from-class="opacity-100"
        leave-active-class="transition-all duration-fast ease-in"
        leave-to-class="opacity-0"
        mode="out-in"
      >
        <form
          v-if="!submitted"
          key="form"
          class="flex flex-col gap-6"
          @submit.prevent="onSubmit"
        >
          <div>
            <h1 class="text-display text-fg-primary mb-2">Sign in</h1>
            <p class="text-fg-muted text-body">
              Pick your poison: Google, or a magic link by email.
            </p>
          </div>

          <!-- Surface OAuth-callback errors (state expired, user denied,
               server not configured) so the user knows why they're back
               here instead of in /p. -->
          <div
            v-if="oauthError"
            class="rounded-md p-3 text-small"
            :style="{
              background: 'var(--signal-amber-bg, rgba(245,158,11,0.08))',
              border: '1px solid rgba(245,158,11,0.3)',
              color: 'var(--fg-body)',
            }"
          >
            {{ oauthError }}
          </div>

          <!-- Google button — hidden when the backend hasn't been
               configured (HANGAR_GOOGLE_CLIENT_ID empty). When shown, it's
               the primary path for new users (one click vs check-your-
               inbox for the magic link). -->
          <button
            v-if="googleConfigured"
            type="button"
            class="h-11 px-4 rounded-md font-sans text-body inline-flex items-center justify-center gap-3 border border-border bg-bg-surface text-fg-primary hover:bg-bg-surface-hi transition-colors"
            @click="googleSignIn"
          >
            <!-- Inline SVG of Google's "G" logo. Static colors so it
                 stays on-brand across light/dark themes. -->
            <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.25-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z"/>
              <path fill="#FBBC05" d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332Z"/>
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.167 6.656 3.58 9 3.58Z"/>
            </svg>
            <span>Continue with Google</span>
          </button>

          <!-- Visual separator only when Google is on; without the button
               the divider has nothing to divide. -->
          <div
            v-if="googleConfigured"
            class="flex items-center gap-3 text-fg-subtle"
          >
            <span class="flex-1 h-px bg-border" />
            <span class="font-mono text-[10px] uppercase tracking-[0.12em]">or</span>
            <span class="flex-1 h-px bg-border" />
          </div>

          <InputField
            v-model="email"
            label="email"
            type="email"
            placeholder="you@example.com"
            autocomplete="email"
            :autofocus="true"
            :error="error"
            :disabled="submitting"
          />

          <PrimaryButton
            type="submit"
            size="lg"
            :loading="submitting"
            :disabled="submitting"
          >
            <span>Send magic link</span>
            <span
              v-if="!submitting"
              class="font-mono text-small opacity-70"
              aria-hidden="true"
            >⏎</span>
          </PrimaryButton>

          <p class="text-small text-fg-subtle text-center">
            By continuing, you agree to our terms — which don't exist yet.
          </p>
        </form>

        <div v-else key="sent" class="flex flex-col gap-5 text-center">
          <div
            class="mx-auto w-10 h-10 rounded-full flex items-center justify-center"
            :style="{ background: 'var(--signal-green-bg)', color: 'var(--signal-green)' }"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 6l-10 7L2 6" />
              <rect x="2" y="4" width="20" height="16" rx="2" />
            </svg>
          </div>
          <div>
            <h1 class="text-title text-fg-primary">Check your email</h1>
            <p class="text-fg-muted mt-2">
              We sent a link to <span class="font-mono text-fg-body">{{ email }}</span>.
              Click it from the same browser and you're in.
            </p>
          </div>
          <p class="text-small text-fg-subtle">
            The link expires in 15 minutes. Can only be used once.
          </p>
          <button
            type="button"
            class="text-small text-fg-muted hover:text-fg-body transition-colors"
            @click="reset"
          >
            ← use a different email
          </button>
        </div>
      </transition>
    </div>
  </div>
</template>
