<script setup lang="ts">
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

/** Signed-in visitors go to their dashboard, everyone else to sign-in. */
function goSignIn() {
  router.push(auth.isAuthed ? "/p" : "/login");
}

import HeroOrb from "@/components/landing/HeroOrb.vue";
import { useMcpToolCount } from "@/composables/useMcpToolCount";

const { count: toolCount } = useMcpToolCount();

function scrollToDemo() {
  document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
}
</script>

<template>
<!-- ─── Hero ─────────────────────────────────────────────────────────── -->
<!-- Mobile note: min-h drops on small viewports so the section sizes to
     its content (copy + orb stack) instead of forcing 88vh and leaving
     the orb floating below the fold with awkward whitespace.
     pb-0 on mobile so the next section's bg-bloom flows in cleanly
     without a visible cutoff between hero and "Works with" strip. -->
<section class="relative flex items-center overflow-hidden pt-20 pb-8 md:pb-12 md:min-h-[88vh]">
  <!-- Subtle grid background -->
  <div class="absolute inset-0 pointer-events-none"
    style="background-image: linear-gradient(rgb(var(--border-rgb) / 0.03) 1px, transparent 1px), linear-gradient(90deg, rgb(var(--border-rgb) / 0.03) 1px, transparent 1px); background-size: 60px 60px" />
  <!-- Orb-palette gradient blooms — soft violet + mint + pink washes that
       tie the hero bg into the orb's own colors. Sized in vmax so they
       shrink on mobile instead of overflowing the viewport sideways. -->
  <div class="absolute -top-40 -left-40 rounded-full pointer-events-none"
    style="width: 60vmax; height: 60vmax; max-width: 780px; max-height: 780px; background: radial-gradient(circle, rgb(var(--signal-violet-rgb) / 0.10) 0%, transparent 65%); filter: blur(20px)" />
  <div class="absolute top-1/3 right-[-20%] rounded-full pointer-events-none"
    style="width: 55vmax; height: 55vmax; max-width: 700px; max-height: 700px; background: radial-gradient(circle, rgb(var(--signal-green-rgb) / 0.09) 0%, transparent 65%); filter: blur(20px)" />
  <div class="absolute bottom-0 left-1/2 -translate-x-1/2 rounded-full pointer-events-none"
    style="width: 80vmax; height: 32vmax; max-width: 900px; max-height: 400px; background: radial-gradient(ellipse, rgb(var(--signal-violet-rgb) / 0.06) 0%, transparent 70%); filter: blur(30px)" />

  <!-- Mobile: gap-8 instead of gap-12 (stacked layout doubles vertical
       cost). py-12 instead of py-20 — the outer pt-20 already gave us
       room under the fixed nav. -->
  <div class="relative z-10 w-full max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-8 lg:gap-12 items-center py-12 md:py-20">

    <!-- Left: copy — ruthlessly trimmed. H1 + one-line subhead + CTAs. -->
    <div>
      <!-- clamp shrinks safely on narrow viewports (2.1rem = 33.6px on
           iPhone SE) and tops out at 4.4rem on widescreens. -->
      <h1 class="font-sans font-semibold mb-6 leading-[1.04] tracking-tight"
        style="font-size: clamp(2.1rem, 5.5vw, 4.4rem); letter-spacing: -0.04em; color: var(--fg-primary)">
        The project console<br>
        for
        <!-- Same color band as the orb (mint → violet → mint → pink) —
             sweeps across the text on the same 18s cadence as the orb's
             aurora-rotate, so the headline and the orb feel sourced
             from the same animated palette. -->
        <span class="aurora-text">shipping devs.</span>
      </h1>

      <p class="mb-9 leading-relaxed max-w-md"
        style="font-size: 1.05rem; color: var(--fg-body); line-height: 1.55">
        One source of truth for every weekend hack, side-project,
        and full app — with an MCP server your AI already speaks.
      </p>

      <div class="flex flex-wrap gap-3 mb-3">
        <button
          class="px-5 py-2.5 rounded-md font-mono font-semibold text-small transition-opacity hover:opacity-90 tracking-wider uppercase"
          style="background: var(--signal-green); color: var(--on-signal); box-shadow: 0 0 20px rgb(var(--signal-green-rgb) / 0.18)"
          @click="goSignIn">
          {{ auth.isAuthed ? 'Open dashboard →' : 'Start 7-day trial →' }}
        </button>
        <button
          class="px-5 py-2.5 rounded-md font-mono text-small transition-opacity hover:opacity-100 tracking-wider uppercase"
          style="border: 1px solid rgb(var(--border-rgb) / 0.2); color: var(--fg-body); background: transparent; opacity: 0.85"
          @click="scrollToDemo">
          See how it works ↓
        </button>
      </div>

      <!-- Two friction-free shortcut paths below the primary trial CTA:
           1. the one-line installer, for users who already have an editor.
           2. Google one-click sign-in for everyone else.
           Both are inline links rather than buttons — keeps the primary
           accent on the green "Start 7-day trial" button per the
           .impeccable.md "single accent per surface" rule.

           Copy note: this used to say "Paste one prompt — AI installs
           itself", which described the old manual path. One line now
           configures every MCP client on the machine, so the promise is
           bigger and the sentence had to say so. -->
      <p class="mb-2 font-mono text-micro" style="color: var(--fg-body); letter-spacing: 0.02em">
        <span aria-hidden="true" style="color: var(--signal-green)">✦</span>
        Claude, Cursor, Windsurf, Zed already installed?
        <RouterLink
          to="/install"
          class="underline-offset-2 hover:underline"
          style="color: var(--signal-green)"
        >One line wires up all of them →</RouterLink>
      </p>
      <a
        v-if="!auth.isAuthed"
        href="/api/v1/auth/google/start?next=%2Fp"
        class="mb-7 inline-flex items-center gap-2 font-mono text-micro hover:underline underline-offset-2"
        style="color: var(--fg-body); letter-spacing: 0.02em"
      >
        <svg width="12" height="12" viewBox="0 0 18 18" aria-hidden="true">
          <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.25-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.716v2.259h2.908c1.702-1.567 2.684-3.875 2.684-6.615Z"/>
          <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.259c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18Z"/>
          <path fill="#FBBC05" d="M3.964 10.706A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.706V4.962H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.038l3.007-2.332Z"/>
          <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.962L3.964 7.294C4.672 5.167 6.656 3.58 9 3.58Z"/>
        </svg>
        <span>Or sign up with Google — one click →</span>
      </a>
      <div v-else class="mb-7" />


      <!-- Feature signal — surfaces the actual product surface
           (dashboard + MCP tools + cron + secrets + history) rather
           than infrastructure. Mono-label cadence, no marketing copy. -->
      <p class="font-mono text-micro" style="color: var(--fg-subtle); letter-spacing: 0.04em">
        dashboard · {{ toolCount }} MCP tools · auto-cron · session log · workspace secrets
      </p>
    </div>

    <!-- Right: Hero orb — slowly-rotating aurora-glass sphere. Desktop
         only. On mobile/tablet the headline + CTAs already carry the
         page and the orb's halo + heavy drop-shadows fight the section
         edges in ways that read as visual noise. Hidden below lg so
         the stacked mobile layout stays tight (copy + buttons, no
         400px sphere consuming half the viewport). -->
    <div class="relative hidden lg:flex items-center justify-center">
      <div
        class="relative w-full"
        style="aspect-ratio: 1; max-width: 520px; margin: auto"
      >
        <HeroOrb class="w-full h-full" />
      </div>
    </div>
  </div>
</section>
</template>
