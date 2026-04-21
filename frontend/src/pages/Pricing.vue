<script setup lang="ts">
import { ref } from "vue";
import { useRouter } from "vue-router";

import UserMenu from "@/components/app/UserMenu.vue";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();
function goSignIn() {
  router.push(auth.isAuthed ? "/p" : "/login");
}

const openFaq = ref<number | null>(null);
function toggleFaq(i: number) {
  openFaq.value = openFaq.value === i ? null : i;
}

const freeFeatures = [
  "3 active projects",
  "500 MCP calls / month",
  "Magic link sign-in",
  "GitHub one-click import",
  "AI enrichment (pitch, tags, stack)",
  "Ship loop — ships, sessions, decisions",
  "Full CLI + MCP server access",
  "1 workspace seat",
];

const proFeatures = [
  { text: "Unlimited projects", bold: true },
  { text: "10,000 MCP calls / month", bold: false },
  { text: "Passkey login (Touch ID / Face ID)", bold: false },
  { text: "Up to 5 workspace seats", bold: false },
  { text: "Auto-signals (health, uptime monitoring)", bold: false },
  { text: "Portfolio Intel (activity heatmap + stagnation detection)", bold: false },
  { text: "Workspace-scoped secrets (1Password / Bitwarden)", bold: false },
  { text: "Priority support", bold: false },
];

const faqs = [
  {
    q: "What is MCP and why does it matter?",
    a: "MCP (Model Context Protocol) is an open protocol for connecting AI assistants to external tools and data. Vibecell exposes your project context as MCP tools, so Claude (and other MCP-compatible clients) can read your project state, log decisions, and record ships — without you copy-pasting anything.",
  },
  {
    q: "Who owns my data?",
    a: "You do. Vibecell stores your data in a private Postgres instance on Hetzner (EU) and never trains AI models on your content. You can export everything as JSON from Settings, and deleting your account permanently removes all data.",
  },
  {
    q: "Can I self-host Vibecell?",
    a: "Not yet officially, but the backend is a standard FastAPI + Postgres stack. We plan to release a self-host guide for Pro subscribers. Reach out at hello@vibecell.dev if you need it now.",
  },
  {
    q: "What counts as an MCP call?",
    a: "Any tool invocation via the MCP protocol — reading project context, logging a decision, fetching status, recording a ship event. Browsing the Vibecell web UI does not count toward your quota.",
  },
  {
    q: "Which AI clients are supported?",
    a: "Claude Desktop, Claude Code (claude.ai/code), Cursor, Zed, and any MCP-compatible client. We test against all five. More clients are being added as MCP adoption grows.",
  },
  {
    q: "Can I cancel my Pro subscription?",
    a: "Yes, any time. You keep Pro access until the end of the current billing period. No questions asked.",
  },
  {
    q: "Is there a free trial for Pro?",
    a: "Yes — 14 days free, no credit card required. You can explore all Pro features and decide after.",
  },
  {
    q: "What happens if I exceed my MCP call limit?",
    a: "On Free, calls above 500/month are soft-blocked until the next cycle. On Pro, we'll notify you and give you the option to upgrade or wait for the next cycle — we won't hard-cut you off mid-session.",
  },
];
</script>

<template>
  <div class="min-h-screen text-fg-primary" style="background: #070b10">

    <!-- ─── Nav ──────────────────────────────────────────────────────────── -->
    <header class="flex items-center justify-between px-6 py-4"
      style="border-bottom: 1px solid rgba(138,180,255,0.08)">
      <router-link to="/landing" class="flex items-center gap-2.5">
        <span class="font-mono" style="font-size: 18px; color: #5cc8a4">◈</span>
        <span class="font-mono text-[11px] tracking-[0.15em] uppercase" style="color: #5e7088">Vibecell</span>
      </router-link>
      <div class="flex items-center gap-3">
        <UserMenu v-if="auth.isAuthed" variant="light" />
        <button
          class="px-4 py-1.5 rounded font-mono text-[12px] hover:opacity-90 transition-opacity"
          style="background: #5cc8a4; color: #070b10"
          @click="goSignIn">
          {{ auth.isAuthed ? 'Open dashboard →' : 'Get started →' }}
        </button>
      </div>
    </header>

    <!-- ─── Hero ─────────────────────────────────────────────────────────── -->
    <section class="max-w-3xl mx-auto px-6 pt-24 pb-16 text-center">
      <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-4" style="color: #5cc8a4">
        Pricing
      </p>
      <h1 class="font-semibold mb-4" style="font-size: clamp(2rem, 4vw, 3rem); letter-spacing: -0.04em; color: #ffffff; line-height: 1.1">
        Simple pricing.<br>
        <span style="color: #5cc8a4">Serious tooling.</span>
      </h1>
      <p style="font-size: 14px; color: #8ba1bd; line-height: 1.65">
        Start free and keep shipping. Upgrade when your portfolio demands it.
      </p>
    </section>

    <!-- ─── Plan cards ───────────────────────────────────────────────────── -->
    <section class="max-w-4xl mx-auto px-6 pb-24 grid md:grid-cols-2 gap-8">

      <!-- Free -->
      <div class="rounded-xl p-8 flex flex-col"
        style="background: rgba(20,33,50,0.45); border: 1px solid rgba(138,180,255,0.1)">
        <div>
          <p class="font-mono text-[11px] uppercase tracking-[0.12em] mb-3" style="color: #5e7088">Free</p>
          <div class="flex items-end gap-2 mb-1">
            <span class="font-bold" style="font-size: 3.5rem; color: #ffffff; letter-spacing: -0.05em; line-height: 1">$0</span>
          </div>
          <p class="mb-8" style="font-size: 12px; color: #5e7088">Forever free · no credit card</p>

          <ul class="space-y-3 mb-10">
            <li v-for="f in freeFeatures" :key="f" class="flex items-start gap-3" style="font-size: 13px; color: #8ba1bd">
              <!-- Checkmark SVG -->
              <svg viewBox="0 0 16 16" fill="none" style="width:14px;height:14px;flex-shrink:0;margin-top:2px">
                <circle cx="8" cy="8" r="7" stroke="rgba(92,200,164,0.3)" stroke-width="1"/>
                <path d="M5 8l2 2 4-4" stroke="#5cc8a4" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              {{ f }}
            </li>
          </ul>
        </div>

        <button
          class="w-full py-3 rounded-lg font-mono text-[13px] transition-all hover:opacity-80 mt-auto"
          style="border: 1px solid rgba(138,180,255,0.18); color: #cfd4dc"
          @click="goSignIn">
          Get started free
        </button>
      </div>

      <!-- Pro -->
      <div class="rounded-xl p-8 flex flex-col relative overflow-hidden"
        style="background: rgba(92,200,164,0.04); border: 1px solid rgba(92,200,164,0.28); box-shadow: 0 0 48px rgba(92,200,164,0.07), inset 0 1px 0 rgba(92,200,164,0.12)">
        <!-- Ribbon -->
        <div class="absolute top-0 right-0 font-mono text-[10px] uppercase tracking-widest px-4 py-1.5 rounded-bl font-bold"
          style="background: #5cc8a4; color: #070b10">
          Most popular
        </div>

        <div>
          <p class="font-mono text-[11px] uppercase tracking-[0.12em] mb-3" style="color: #5cc8a4">Pro</p>
          <div class="flex items-end gap-2 mb-1">
            <span class="font-bold" style="font-size: 3.5rem; color: #ffffff; letter-spacing: -0.05em; line-height: 1">$12</span>
            <span class="mb-2" style="font-size: 14px; color: #8ba1bd">/ month</span>
          </div>
          <p class="mb-8" style="font-size: 12px; color: #5e7088">Per workspace · cancel any time</p>

          <ul class="space-y-3 mb-10">
            <li v-for="f in proFeatures" :key="f.text" class="flex items-start gap-3" style="font-size: 13px; color: #8ba1bd">
              <svg viewBox="0 0 16 16" fill="none" style="width:14px;height:14px;flex-shrink:0;margin-top:2px">
                <circle cx="8" cy="8" r="7" stroke="rgba(92,200,164,0.5)" stroke-width="1"/>
                <path d="M5 8l2 2 4-4" stroke="#5cc8a4" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
              </svg>
              <span>
                <strong v-if="f.bold" style="color: #ffffff">{{ f.text }}</strong>
                <template v-else>{{ f.text }}</template>
              </span>
            </li>
          </ul>
        </div>

        <button
          class="w-full py-3 rounded-lg font-mono font-semibold text-[13px] transition-all hover:opacity-90 mt-auto"
          style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 24px rgba(92,200,164,0.25)"
          @click="goSignIn">
          Start free 14-day trial →
        </button>
        <p class="text-center mt-2.5 font-mono" style="font-size: 10px; color: #5e7088">
          No credit card · cancel any time
        </p>
      </div>
    </section>

    <!-- ─── Comparison table (compact) ──────────────────────────────────── -->
    <section class="max-w-3xl mx-auto px-6 pb-24">
      <div class="rounded-xl overflow-hidden" style="border: 1px solid rgba(138,180,255,0.1)">
        <table class="w-full" style="font-size: 12px; border-collapse: collapse">
          <thead>
            <tr style="background: rgba(20,33,50,0.6)">
              <th class="text-left px-5 py-3 font-mono text-[11px] uppercase tracking-[0.1em]" style="color: #5e7088; border-bottom: 1px solid rgba(138,180,255,0.08)">Feature</th>
              <th class="text-center px-5 py-3 font-mono text-[11px] uppercase tracking-[0.1em]" style="color: #5e7088; border-bottom: 1px solid rgba(138,180,255,0.08)">Free</th>
              <th class="text-center px-5 py-3 font-mono text-[11px] uppercase tracking-[0.1em]" style="color: #5cc8a4; border-bottom: 1px solid rgba(138,180,255,0.08)">Pro</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, i) in [
              ['Projects', '3', 'Unlimited'],
              ['MCP calls / month', '500', '10,000'],
              ['MCP + CLI access', '✓', '✓'],
              ['GitHub import + AI enrichment', '✓', '✓'],
              ['Magic link login', '✓', '✓'],
              ['Passkey login', '—', '✓'],
              ['Workspace seats', '1', '5'],
              ['Auto-signals', '—', '✓'],
              ['Portfolio Intel', '—', '✓'],
              ['Workspace secrets', '—', '✓'],
              ['Priority support', '—', '✓'],
            ]" :key="row[0]"
              :style="{ background: i % 2 === 0 ? 'rgba(20,33,50,0.3)' : 'transparent' }">
              <td class="px-5 py-3" style="color: #8ba1bd">{{ row[0] }}</td>
              <td class="px-5 py-3 text-center font-mono" style="color: #5e7088">{{ row[1] }}</td>
              <td class="px-5 py-3 text-center font-mono" :style="{ color: row[2] === '✓' ? '#5cc8a4' : (row[2] === '—' ? '#3d4a5c' : '#ffffff') }">{{ row[2] }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <!-- ─── FAQ ──────────────────────────────────────────────────────────── -->
    <section class="max-w-2xl mx-auto px-6 pb-28">
      <div class="text-center mb-12">
        <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">FAQ</p>
        <h2 class="font-semibold" style="font-size: clamp(1.4rem, 2.5vw, 2rem); letter-spacing: -0.03em; color: #ffffff">
          Common questions
        </h2>
      </div>

      <div class="space-y-2">
        <div
          v-for="(faq, i) in faqs"
          :key="faq.q"
          class="rounded-xl overflow-hidden"
          style="border: 1px solid rgba(138,180,255,0.1)">
          <button
            class="w-full flex items-center justify-between px-5 py-4 text-left transition-colors hover:bg-white/[0.02]"
            style="background: rgba(20,33,50,0.35)"
            @click="toggleFaq(i)">
            <span class="font-semibold pr-4" style="font-size: 13px; color: #cfd4dc; letter-spacing: -0.01em">
              {{ faq.q }}
            </span>
            <!-- Chevron -->
            <svg viewBox="0 0 16 16" fill="none" class="flex-shrink-0 transition-transform duration-200"
              :style="{ transform: openFaq === i ? 'rotate(180deg)' : 'none', width: '14px', height: '14px' }">
              <path d="M4 6l4 4 4-4" stroke="#5e7088" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
          </button>
          <div
            v-if="openFaq === i"
            class="px-5 py-4"
            style="background: rgba(20,33,50,0.2); border-top: 1px solid rgba(138,180,255,0.07); font-size: 13px; color: #8ba1bd; line-height: 1.65">
            {{ faq.a }}
          </div>
        </div>
      </div>
    </section>

    <!-- ─── Bottom CTA ───────────────────────────────────────────────────── -->
    <section class="text-center py-20 px-6"
      style="background: rgba(92,200,164,0.03); border-top: 1px solid rgba(92,200,164,0.1)">
      <h2 class="font-semibold mb-4" style="font-size: clamp(1.4rem, 2.5vw, 2rem); letter-spacing: -0.03em; color: #ffffff">
        Still have questions?
      </h2>
      <p class="mb-8" style="font-size: 14px; color: #8ba1bd">
        Reach out at <a href="mailto:hello@vibecell.dev" style="color: #5cc8a4">hello@vibecell.dev</a> — or just start free and explore.
      </p>
      <button
        class="px-8 py-3 rounded-xl font-mono font-semibold text-[13px] transition-all hover:opacity-90"
        style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 24px rgba(92,200,164,0.2)"
        @click="goSignIn">
        {{ auth.isAuthed ? 'Open dashboard →' : 'Get started for free →' }}
      </button>
    </section>

    <!-- ─── Footer ───────────────────────────────────────────────────────── -->
    <footer class="px-6 py-8" style="border-top: 1px solid rgba(138,180,255,0.08)">
      <div class="max-w-5xl mx-auto flex items-center justify-between" style="font-size: 12px; color: #5e7088">
        <router-link to="/landing" class="font-mono hover:text-fg-muted transition-colors flex items-center gap-2">
          <span style="color: #5cc8a4">◈</span> Vibecell
        </router-link>
        <div class="flex gap-6">
          <router-link to="/legal" class="hover:text-fg-muted transition-colors">Privacy &amp; Terms</router-link>
        </div>
      </div>
    </footer>
  </div>
</template>
