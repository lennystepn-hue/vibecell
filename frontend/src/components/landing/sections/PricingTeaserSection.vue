<script setup lang="ts">
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

/** Signed-in visitors go to their dashboard, everyone else to sign-in. */
function goSignIn() {
  router.push(auth.isAuthed ? "/p" : "/login");
}

import { onMounted, ref } from "vue";

interface LaunchStatus { active: boolean; remaining: number; max: number }

const launch = ref<LaunchStatus>({ active: false, remaining: 0, max: 100 });

onMounted(async () => {
  try {
    const r = await fetch("/api/v1/billing/launch-status");
    if (r.ok) launch.value = await r.json();
  } catch {
    /* silent — the teaser reads fine without the counter */
  }
});
</script>

<template>
<!-- ─── Pricing teaser ───────────────────────────────────────────────── -->
<section class="py-16 md:py-28 px-6">
  <div class="max-w-2xl mx-auto">
    <div class="text-center mb-10">
      <p class="font-mono text-nano uppercase tracking-wide mb-3" style="color: var(--signal-green)">
        // pricing
      </p>
      <h2 class="font-semibold mb-3" style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: var(--fg-primary)">
        One plan, two cycles.
      </h2>
      <p style="color: var(--fg-muted); font-size: 13px; line-height: 1.6">
        7-day trial on monthly · annual locks the price · cancel from the Stripe portal.
      </p>
    </div>

    <!-- Launch marker — thin amber strip, mono-label tradition,
         no emoji, no multi-stop gradient. Mirrors /pricing exactly. -->
    <div
      v-if="launch.active"
      class="rounded-md px-4 py-2.5 mb-5 font-mono flex items-baseline justify-between gap-3"
      style="background: rgb(var(--signal-amber-rgb) / 0.06); border: 1px solid rgb(var(--signal-amber-rgb) / 0.22)"
    >
      <span style="font-size: 10px; color: var(--signal-amber); letter-spacing: 0.12em; text-transform: uppercase">
        // launch · {{ String(launch.max - launch.remaining).padStart(3, '0') }}/{{ launch.max }}
      </span>
      <span style="font-size: 11px; color: var(--fg-muted)">
        first {{ launch.remaining }} get <strong style="color:var(--signal-amber); font-weight: 600">€69.99</strong> · then €99.99
      </span>
    </div>

    <div class="grid md:grid-cols-2 gap-5">
      <!-- Monthly -->
      <div class="rounded-lg p-7 flex flex-col"
        style="background: var(--bg-surface); border: 1px solid rgb(var(--border-rgb) / 0.1)">
        <p class="font-mono text-nano uppercase tracking-caps mb-4" style="color: var(--fg-subtle)">// pro · monthly</p>
        <div class="flex items-baseline gap-1.5 mb-1">
          <p class="font-bold" style="font-size: 2.6rem; color: var(--fg-primary); letter-spacing: -0.04em; line-height: 1">€8.99</p>
          <p style="color: var(--fg-muted); font-size: 12px">/ month</p>
        </div>
        <p class="mb-6 font-mono" style="font-size: 11px; color: var(--fg-subtle)">7-day trial · no card to start</p>
        <ul class="space-y-1.5 mb-7 flex-1" style="font-size: 12px; color: var(--fg-muted)">
          <li class="flex gap-2 items-start"><span style="color:var(--signal-green)">·</span> Unlimited projects</li>
          <li class="flex gap-2 items-start"><span style="color:var(--signal-green)">·</span> AI enrichment from any GitHub repo</li>
          <li class="flex gap-2 items-start"><span style="color:var(--signal-green)">·</span> MCP server access</li>
          <li class="flex gap-2 items-start"><span style="color:var(--signal-green)">·</span> Auto-cron + workspace secrets</li>
        </ul>
        <button
          class="w-full py-2.5 rounded-md font-mono text-micro tracking-wider uppercase transition-opacity hover:opacity-100"
          style="border: 1px solid var(--border-strong); color: var(--fg-body); opacity: 0.85"
          @click="goSignIn">
          Start trial →
        </button>
      </div>

      <!-- Annual / Launch — single accent (amber if launch, mint if standard) -->
      <div class="rounded-lg p-7 flex flex-col relative"
        :style="{
          background: launch.active ? 'rgb(var(--signal-amber-rgb) / 0.04)' : 'rgb(var(--signal-green-rgb) / 0.04)',
          border: '1px solid ' + (launch.active ? 'rgb(var(--signal-amber-rgb) / 0.28)' : 'rgb(var(--signal-green-rgb) / 0.28)'),
        }">
        <p class="font-mono text-nano uppercase tracking-caps mb-4"
          :style="{ color: launch.active ? 'var(--signal-amber)' : 'var(--signal-green)' }">
          // pro · annual
        </p>
        <div class="flex items-baseline gap-2 mb-1 flex-wrap">
          <p class="font-bold" :style="{
            fontSize: '2.6rem',
            color: launch.active ? 'var(--signal-amber)' : 'var(--fg-primary)',
            letterSpacing: '-0.04em',
            lineHeight: 1,
          }">{{ launch.active ? '€69.99' : '€99.99' }}</p>
          <p style="color: var(--fg-muted); font-size: 12px">/ year</p>
          <!-- Strikethrough €99.99 as a typographic footnote, not a sibling -->
          <p v-if="launch.active" class="font-mono ml-1" style="font-size: 11px; color: var(--fg-subtle); text-decoration: line-through; text-decoration-thickness: 1px">
            €99.99
          </p>
        </div>
        <p v-if="launch.active" class="mb-6 font-mono" style="font-size: 10px; color: var(--signal-amber); letter-spacing: 0.12em; text-transform: uppercase">
          // first 100 only · renews €99.99
        </p>
        <p v-else class="mb-6 font-mono" style="font-size: 11px; color: var(--fg-subtle)">
          ~7% off vs monthly · billed yearly
        </p>
        <ul class="space-y-1.5 mb-7 flex-1" style="font-size: 12px; color: var(--fg-muted)">
          <li class="flex gap-2 items-start"><span style="color:var(--signal-green)">·</span> Everything in monthly</li>
          <li class="flex gap-2 items-start"><span style="color:var(--signal-green)">·</span> Price locked for 12 months</li>
          <li class="flex gap-2 items-start"><span style="color:var(--signal-green)">·</span> Stripe Tax — EU-VAT invoicing</li>
          <li class="flex gap-2 items-start"><span style="color:var(--signal-green)">·</span> 14-day Widerruf, then committed</li>
        </ul>
        <button
          class="w-full py-2.5 rounded-md font-mono font-semibold text-micro tracking-wider uppercase transition-opacity hover:opacity-90"
          :style="{
            background: launch.active ? 'var(--signal-amber)' : 'var(--signal-green)',
            color: 'var(--on-signal)',
          }"
          @click="goSignIn">
          {{ launch.active ? 'Take launch price →' : 'Get annual →' }}
        </button>
      </div>
    </div>

    <div class="text-center mt-8">
      <router-link to="/pricing"
        class="font-mono transition-colors hover:text-fg-primary"
        style="font-size: 11px; color: var(--fg-subtle); letter-spacing: 0.04em">
        full pricing details + FAQ →
      </router-link>
    </div>
  </div>
</section>
</template>
