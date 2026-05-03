<script setup lang="ts">
/**
 * GDPR/RGPD-conforming cookie consent banner. Shown until the user
 * clicks Accept OR Decline; their choice is persisted in localStorage
 * so they don't see it again.
 *
 * Compliance points:
 *   - "Decline" must be as easy/visible as "Accept" — no dark patterns.
 *   - Banner doesn't pre-tick anything. Refusal == default until consent.
 *   - Until consent is granted, NO analytics script is loaded. We only
 *     write a single localStorage key (UI state, not tracking).
 *   - Privacy-policy link is one click away in the banner itself.
 *   - Revocation is documented + linkable from the privacy page.
 */
import { onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { denyConsent, grantConsent, readConsent } from "@/lib/analytics";

const router = useRouter();
const visible = ref(false);

onMounted(() => {
  // Show only if the user hasn't decided yet. Once decided either
  // way, banner stays hidden until they explicitly revoke + reload.
  visible.value = readConsent() === "unknown";
});

function accept() {
  grantConsent(router);
  visible.value = false;
}

function decline() {
  denyConsent();
  visible.value = false;
}
</script>

<template>
  <transition
    enter-active-class="transition-all duration-200 ease-out"
    enter-from-class="opacity-0 translate-y-4"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-150 ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0 translate-y-2"
  >
    <div
      v-if="visible"
      class="fixed bottom-4 left-4 right-4 sm:left-auto sm:right-6 sm:bottom-6 sm:max-w-md z-50 rounded-lg p-5 shadow-2xl"
      style="background: rgba(13,18,24,0.96); border: 1px solid rgba(138,180,255,0.2); backdrop-filter: blur(12px)"
      role="dialog"
      aria-labelledby="consent-title"
    >
      <p
        id="consent-title"
        class="font-mono text-[11px] uppercase tracking-[0.12em] mb-2"
        style="color: #5cc8a4"
      >// privacy</p>
      <p class="text-small text-fg-body leading-relaxed mb-4">
        Vibecell uses Google Analytics to count anonymous pageviews. IP
        addresses are anonymised before they reach Google. No tracking
        runs until you say so —
        <RouterLink to="/legal?tab=privacy" class="link">read the full privacy notice</RouterLink>.
      </p>
      <div class="flex flex-wrap items-center gap-3">
        <button
          type="button"
          class="px-4 py-2 rounded-md font-mono text-small font-semibold transition-opacity hover:opacity-90"
          style="background: #5cc8a4; color: #070b10"
          @click="accept"
        >Accept analytics</button>
        <button
          type="button"
          class="px-4 py-2 rounded-md font-mono text-small transition-colors hover:text-fg-primary"
          style="color: #cfd4dc; border: 1px solid rgba(138,180,255,0.2); background: transparent"
          @click="decline"
        >Decline</button>
      </div>
    </div>
  </transition>
</template>
