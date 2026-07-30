<script setup lang="ts">
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

/** Signed-in visitors go to their dashboard, everyone else to sign-in. */
function goSignIn() {
  router.push(auth.isAuthed ? "/p" : "/login");
}
</script>

<template>
<!-- ─── Final CTA ────────────────────────────────────────────────────── -->
<section class="py-20 md:py-32 px-6 text-center relative overflow-hidden"
  style="background: rgb(var(--bg-surface-rgb) / 0.4); border-top: 1px solid rgb(var(--border-rgb) / 0.07)">
  <!-- Background glow -->
  <div class="absolute inset-0 pointer-events-none"
    style="background: radial-gradient(ellipse 60% 60% at 50% 50%, rgb(var(--signal-green-rgb) / 0.05) 0%, transparent 70%)" />

  <div class="relative z-10 max-w-2xl mx-auto">
    <p class="font-mono text-micro uppercase tracking-caps mb-4" style="color: var(--signal-green)">
      Ready to ship smarter?
    </p>
    <h2 class="font-semibold mb-5" style="font-size: clamp(1.8rem, 4vw, 3rem); letter-spacing: -0.04em; color: var(--fg-primary); line-height: 1.1">
      Start shipping smarter.<br>
      <span style="color: var(--signal-green)">Today.</span>
    </h2>
    <p class="mb-10" style="font-size: 14px; color: var(--fg-muted); line-height: 1.65">
      Join the builders who never lose project context again.<br>
      7-day trial. No card to start. €8.99/mo after.
    </p>
    <button
      class="px-10 py-4 rounded-xl font-mono font-semibold text-section transition-all hover:opacity-90 hover:scale-[1.02] active:scale-[0.99]"
      style="background: var(--signal-green); color: var(--on-signal); box-shadow: 0 0 40px rgb(var(--signal-green-rgb) / 0.3), 0 4px 20px rgb(var(--scrim-rgb) / 0.3)"
      @click="goSignIn">
      {{ auth.isAuthed ? 'Open dashboard →' : 'Start 7-day trial →' }}
    </button>
    <p class="mt-4 font-mono" style="font-size: 11px; color: var(--fg-subtle)">
      vibecell.dev · No install · GDPR compliant · Cancel anytime
    </p>
  </div>
</section>
</template>
