<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import InputField from "@/components/ui/InputField.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

// If the user is already signed in (session cookie still valid), the login
// form is pointless — bounce straight to the dashboard. Covers the case
// where someone bookmarks /login or clicks "Sign in →" on a stale tab.
onMounted(() => {
  if (auth.isAuthed) router.replace("/p");
});

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
              We'll email you a one-time link. No passwords, nothing to forget.
            </p>
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
