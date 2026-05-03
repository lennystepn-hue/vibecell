<script setup lang="ts">
/**
 * MarketingHeader — single source of truth for the public-marketing header
 * (Landing, Pricing, Legal, Status, Install).
 *
 * Why this exists: each marketing page used to roll its own header — they
 * drifted apart on mobile (some had backdrop blur + nav, others were plain),
 * which made the brand feel inconsistent when bouncing between pages on a
 * phone. This component locks one identical header across all of them.
 *
 * Behaviour:
 * - Fixed at top with the smoked-glass blur, so the logo + CTA stay visible
 *   while scrolling long legal/pricing copy.
 * - Mobile: logo only on the left, UserMenu (if authed) + primary CTA on the
 *   right. Center nav links are hidden on phones to keep the bar uncluttered.
 * - Desktop (sm+): center nav adds Pricing · Legal · GitHub.
 * - The CTA label flips to "Open dashboard →" when signed in, otherwise
 *   "Start trial →" (override via the cta prop if a page wants different copy).
 *
 * Usage: drop <MarketingHeader /> at the top of the page template. The page
 * also needs a `pt-[60px]` (or similar) spacer on its first section because
 * the header floats on top of content with position: fixed.
 */
import { useRouter } from "vue-router";

import UserMenu from "@/components/app/UserMenu.vue";
import { useAuthStore } from "@/stores/auth";

interface Props {
  /** Override the right-side CTA label when not authed. Defaults to "Start trial →". */
  cta?: string;
}
const props = withDefaults(defineProps<Props>(), {
  cta: "Start trial →",
});

const router = useRouter();
const auth = useAuthStore();

function go() {
  router.push(auth.isAuthed ? "/p" : "/login");
}
</script>

<template>
  <header
    class="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-4 sm:px-6 py-3"
    style="background: rgba(7,11,16,0.75); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(138,180,255,0.08)"
  >
    <router-link to="/" class="flex items-center gap-2.5">
      <span class="text-signal-green font-mono text-[18px] leading-none select-none">◈</span>
      <span class="font-mono text-[11px] tracking-[0.15em] uppercase text-fg-subtle">Vibecell</span>
    </router-link>
    <nav class="hidden sm:flex items-center gap-6">
      <router-link
        to="/pricing"
        class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150"
      >Pricing</router-link>
      <router-link
        to="/legal"
        class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150"
      >Legal</router-link>
      <a
        href="https://github.com/lennystepn-hue/vibecell"
        target="_blank"
        rel="noopener"
        class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150"
      >GitHub</a>
    </nav>
    <div class="flex items-center gap-3">
      <UserMenu v-if="auth.isAuthed" variant="light" />
      <!-- Mobile-authed: dashboard link is already in UserMenu, so we hide the
           CTA pill on phones to keep the header from wrapping. Desktop keeps
           both visible (more breathing room). -->
      <button
        v-if="auth.isAuthed"
        class="hidden sm:inline-flex px-4 py-1.5 rounded text-small font-mono bg-signal-green hover:opacity-90 transition-opacity"
        style="color: #070b10"
        @click="go"
      >Open dashboard →</button>
      <button
        v-else
        class="px-4 py-1.5 rounded text-small font-mono bg-signal-green hover:opacity-90 transition-opacity"
        style="color: #070b10"
        @click="go"
      >{{ props.cta }}</button>
    </div>
  </header>
</template>
