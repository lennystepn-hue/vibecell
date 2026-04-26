<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import UserMenu from "@/components/app/UserMenu.vue";
import { useAuthStore } from "@/stores/auth";

const router = useRouter();
const auth = useAuthStore();

function goSignIn() {
  router.push(auth.isAuthed ? "/p" : "/login");
}

function goBilling() {
  router.push(auth.isAuthed ? "/settings/billing" : "/login");
}

const openFaq = ref<number | null>(null);
function toggleFaq(i: number) {
  openFaq.value = openFaq.value === i ? null : i;
}

// Monthly ⇄ Annual toggle. Defaults to annual because the launch offer
// makes annual look noticeably cheaper than monthly.
const billingCycle = ref<"monthly" | "annual">("annual");

interface LaunchStatus {
  active: boolean;
  remaining: number;
  max: number;
}
const launch = ref<LaunchStatus>({ active: false, remaining: 0, max: 100 });

async function loadLaunchStatus() {
  try {
    const r = await fetch("/api/v1/billing/launch-status");
    if (r.ok) launch.value = await r.json();
  } catch {
    /* silent */
  }
}

onMounted(loadLaunchStatus);

// €99.99 standard, €69.99 with launch coupon (€30 off, first 100).
const annualStandardCents = 9999;
const annualLaunchCents = 6999;
const monthlyCents = 899;

const annualEffectiveCents = computed(() =>
  launch.value.active ? annualLaunchCents : annualStandardCents
);

const annualSavingsVsMonthlyCents = computed(
  () => monthlyCents * 12 - annualEffectiveCents.value
);

function formatEur(cents: number) {
  return `€${(cents / 100).toFixed(2)}`;
}

async function startCheckout(plan: "pro" | "pro_annual") {
  if (!auth.isAuthed) {
    router.push("/login");
    return;
  }
  try {
    const r = await fetch("/api/v1/billing/checkout", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_id: plan }),
    });
    if (!r.ok) {
      router.push("/settings/billing");
      return;
    }
    const { url } = await r.json();
    window.location.assign(url);
  } catch {
    router.push("/settings/billing");
  }
}

const features = [
  { text: "Unlimited projects", emphasis: true },
  { text: "AI enrichment from any GitHub repo (pitch + stack + infra in one click)" },
  { text: "MCP server access for Claude / Cursor / Zed / Continue / OpenAI" },
  { text: "Auto-screenshot + commit-sync cron jobs (zero-touch dashboard)" },
  { text: "Workspace-scoped secrets (1Password / Bitwarden / inline AES-256-GCM)" },
  { text: "365-day session retention (every Claude session logged)" },
  { text: "Magic-link + Passkey login" },
  { text: "GDPR-clean: full JSON export + one-click account delete" },
  { text: "EU-VAT handled by Stripe Tax — invoices ready for your accountant" },
];

const faqs = [
  {
    q: "What's this launch offer?",
    a: "First 100 annual signups pay €69.99 for the first year (instead of €99.99). After that the launch coupon expires automatically and the standard €99.99/year price kicks in. Renewals are at €99.99 either way — the discount applies to the FIRST year only. Stripe enforces the 100-spot limit, so once it's gone, it's gone.",
  },
  {
    q: "Wait, no Free tier?",
    a: "No — we filter tire-kickers via the 7-day trial deadline (on monthly) rather than permanent feature gating. You get the full product for a week with zero friction, then decide if it's worth €8.99/mo or €99.99/year.",
  },
  {
    q: "How do I cancel?",
    a: "Go to Settings → Billing → 'Open Stripe Customer Portal'. Click 'Cancel subscription'. You keep Pro access through the end of the current billing period (no pro-rated refunds, but no early cutoff either). Your data is preserved — re-subscribe any time and pick up exactly where you left off.",
  },
  {
    q: "Annual vs Monthly — what's the catch?",
    a: "Annual is locked in for 12 months — no monthly cancellation. The launch offer makes the first year a clear win (~35% off vs monthly). Standard annual after the launch is ~7% off vs monthly, plus you get price stability. Pick monthly if you want to try-before-commit, annual if you know you're staying.",
  },
  {
    q: "Do I really not need a credit card to start?",
    a: "Correct on monthly: sign up with magic-link, you're immediately on a 7-day Pro trial, no card requested. Stripe asks for payment method only when the trial ends. Annual goes straight through Stripe Checkout (card collected on signup) — but you have 14 days under EU consumer-withdrawal law to back out fully.",
  },
  {
    q: "What is MCP and why does it matter?",
    a: "MCP (Model Context Protocol) is the open protocol for connecting AI assistants to external tools. Vibecell exposes your project state as MCP tools so Claude (and any other MCP-compatible client) can read your context, log decisions, and record ships — without you copy-pasting anything between chat windows.",
  },
  {
    q: "Who owns my data?",
    a: "You do. Vibecell stores everything in a private Postgres in Hetzner Helsinki (EU). We never train AI models on your content. You can export everything as JSON from /settings/account and deleting your account permanently removes all data (cascade through projects, sessions, secrets — the works).",
  },
  {
    q: "Can I cancel any time?",
    a: "Yes, from the Stripe Customer Portal linked in /settings/billing. You keep Pro access until the end of the current billing period. After that you can delete your account or keep it dormant — your data stays exported-able.",
  },
  {
    q: "What about EU VAT?",
    a: "Stripe Tax is enabled — your invoices include the right VAT rate based on your billing address (DE 19%, AT 20%, FR 20%, etc.). Reverse-charge for B2B with valid VAT-IDs is supported automatically.",
  },
  {
    q: "Which AI clients are supported?",
    a: "Anything that speaks MCP: Claude Desktop, Claude Code, Cursor, Zed, Continue, and the OpenAI ChatGPT-with-MCP integration. We test against the first three on every release.",
  },
  {
    q: "Is there a self-host version?",
    a: "Not officially yet, but the stack is plain FastAPI + Postgres + Vue. The full repo is on GitHub. Reach out at hello@vibecell.dev if you want the deploy runbook before we publish it formally.",
  },
];
</script>

<template>
  <div class="min-h-screen text-fg-primary" style="background: #070b10">

    <!-- ─── Nav ──────────────────────────────────────────────────────────── -->
    <header class="flex items-center justify-between px-6 py-4"
      style="border-bottom: 1px solid rgba(138,180,255,0.08)">
      <router-link to="/" class="flex items-center gap-2.5">
        <span class="font-mono" style="font-size: 18px; color: #5cc8a4">◈</span>
        <span class="font-mono text-[11px] tracking-[0.15em] uppercase" style="color: #5e7088">Vibecell</span>
      </router-link>
      <div class="flex items-center gap-3">
        <UserMenu v-if="auth.isAuthed" variant="light" />
        <button
          class="px-4 py-1.5 rounded font-mono text-[12px] hover:opacity-90 transition-opacity"
          style="background: #5cc8a4; color: #070b10"
          @click="goSignIn">
          {{ auth.isAuthed ? 'Open dashboard →' : 'Start free trial →' }}
        </button>
      </div>
    </header>

    <!-- ─── Hero ─────────────────────────────────────────────────────────── -->
    <section class="max-w-3xl mx-auto px-6 pt-24 pb-12 text-center">
      <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-4" style="color: #5cc8a4">
        Pricing
      </p>
      <h1 class="font-semibold mb-4" style="font-size: clamp(2rem, 4vw, 3rem); letter-spacing: -0.04em; color: #ffffff; line-height: 1.1">
        One plan, two cycles.<br>
        <span style="color: #5cc8a4">No funnel games.</span>
      </h1>
      <p style="font-size: 14px; color: #8ba1bd; line-height: 1.65">
        7-day free trial on monthly · annual locks the price · cancel from the Stripe portal any time.
      </p>
    </section>

    <!-- ─── Launch ribbon (only renders when launch coupon is still active) ─ -->
    <section
      v-if="launch.active"
      class="max-w-md mx-auto px-6 mb-6"
    >
      <div
        class="rounded-lg px-4 py-3 text-center font-mono"
        style="background: linear-gradient(90deg, rgba(255,200,80,0.12), rgba(92,200,164,0.12)); border: 1px solid rgba(255,200,80,0.3)"
      >
        <p style="font-size: 11px; color: #ffd66b; letter-spacing: 0.05em">
          🎉 LAUNCH OFFER · {{ launch.remaining }} of {{ launch.max }} spots left
        </p>
        <p class="mt-1" style="font-size: 12px; color: #cfd4dc">
          First 100 annual customers: <strong style="color:#ffd66b">€69.99</strong> first year
          <span style="color: #5e7088">(then €99.99)</span>
        </p>
      </div>
    </section>

    <!-- ─── Cycle toggle ─────────────────────────────────────────────────── -->
    <section class="max-w-md mx-auto px-6 mb-6 flex justify-center">
      <div
        class="inline-flex rounded-full p-1 font-mono"
        style="background: rgba(20,33,50,0.6); border: 1px solid rgba(138,180,255,0.1)"
      >
        <button
          class="px-4 py-1.5 rounded-full text-[11px] uppercase tracking-wider transition-all"
          :style="{
            background: billingCycle === 'monthly' ? '#5cc8a4' : 'transparent',
            color: billingCycle === 'monthly' ? '#070b10' : '#8ba1bd',
            fontWeight: billingCycle === 'monthly' ? 600 : 400,
          }"
          @click="billingCycle = 'monthly'"
        >Monthly</button>
        <button
          class="px-4 py-1.5 rounded-full text-[11px] uppercase tracking-wider transition-all flex items-center gap-2"
          :style="{
            background: billingCycle === 'annual' ? '#5cc8a4' : 'transparent',
            color: billingCycle === 'annual' ? '#070b10' : '#8ba1bd',
            fontWeight: billingCycle === 'annual' ? 600 : 400,
          }"
          @click="billingCycle = 'annual'"
        >
          Annual
          <span
            v-if="annualSavingsVsMonthlyCents > 0"
            class="px-1.5 rounded text-[9px] font-bold"
            :style="{
              background: billingCycle === 'annual' ? 'rgba(7,11,16,0.18)' : 'rgba(255,214,107,0.2)',
              color: billingCycle === 'annual' ? '#070b10' : '#ffd66b',
            }"
          >save {{ formatEur(annualSavingsVsMonthlyCents) }}</span>
        </button>
      </div>
    </section>

    <!-- ─── Plan card (single, centered) ─────────────────────────────────── -->
    <section class="max-w-md mx-auto px-6 pb-24">
      <div class="rounded-xl p-8 flex flex-col relative overflow-hidden"
        style="background: rgba(92,200,164,0.04); border: 1px solid rgba(92,200,164,0.28); box-shadow: 0 0 64px rgba(92,200,164,0.08), inset 0 1px 0 rgba(92,200,164,0.12)">

        <p class="font-mono text-[11px] uppercase tracking-[0.12em] mb-3" style="color: #5cc8a4">Pro</p>

        <!-- Monthly price block -->
        <template v-if="billingCycle === 'monthly'">
          <div class="flex items-end gap-2 mb-1">
            <span class="font-bold" style="font-size: 4rem; color: #ffffff; letter-spacing: -0.05em; line-height: 1">€8.99</span>
            <span class="mb-3" style="font-size: 14px; color: #8ba1bd">/ month</span>
          </div>
          <p class="mb-8" style="font-size: 12px; color: #5e7088">
            7-day free trial · no credit card to start · cancel anytime
          </p>
        </template>

        <!-- Annual price block (dynamic — shows €69.99 launch or €99.99 standard) -->
        <template v-else>
          <div class="flex items-end gap-3 mb-1 flex-wrap">
            <!-- When launch is active: show €99.99 struck-through next to €69.99 -->
            <span v-if="launch.active" class="font-bold" style="font-size: 2rem; color: #5e7088; text-decoration: line-through; text-decoration-thickness: 2px; line-height: 1; letter-spacing: -0.04em">€99.99</span>
            <span class="font-bold" :style="{
              fontSize: '4rem',
              color: launch.active ? '#ffd66b' : '#ffffff',
              letterSpacing: '-0.05em',
              lineHeight: 1,
            }">{{ formatEur(annualEffectiveCents) }}</span>
            <span class="mb-3" style="font-size: 14px; color: #8ba1bd">/ year</span>
          </div>
          <p v-if="launch.active" class="mb-1 font-mono" style="font-size: 11px; color: #ffd66b; letter-spacing: 0.03em">
            🎉 LAUNCH PRICE — first {{ launch.max }} customers · {{ launch.remaining }} spots left
          </p>
          <p class="mb-8" style="font-size: 12px; color: #5e7088">
            <span v-if="launch.active">Saves <strong style="color:#ffd66b">{{ formatEur(annualSavingsVsMonthlyCents) }}</strong> vs monthly · renews at €99.99/year · </span>
            <span>cancel from Stripe portal · billed yearly</span>
          </p>
        </template>

        <ul class="space-y-3 mb-10">
          <li v-for="f in features" :key="f.text" class="flex items-start gap-3" style="font-size: 13px; color: #8ba1bd">
            <svg viewBox="0 0 16 16" fill="none" style="width:14px;height:14px;flex-shrink:0;margin-top:2px">
              <circle cx="8" cy="8" r="7" stroke="rgba(92,200,164,0.5)" stroke-width="1"/>
              <path d="M5 8l2 2 4-4" stroke="#5cc8a4" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <span>
              <strong v-if="f.emphasis" style="color: #ffffff">{{ f.text }}</strong>
              <template v-else>{{ f.text }}</template>
            </span>
          </li>
        </ul>

        <button
          class="w-full py-3 rounded-lg font-mono font-semibold text-[13px] transition-all hover:opacity-90"
          style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 24px rgba(92,200,164,0.25)"
          @click="startCheckout(billingCycle === 'annual' ? 'pro_annual' : 'pro')">
          {{ auth.isAuthed
            ? (billingCycle === 'annual' ? `Get annual ${formatEur(annualEffectiveCents)} →` : 'Start 7-day trial →')
            : (billingCycle === 'annual' ? `Get annual ${formatEur(annualEffectiveCents)} →` : 'Start 7-day trial →')
          }}
        </button>
        <p class="text-center mt-2.5 font-mono" style="font-size: 10px; color: #5e7088">
          {{ billingCycle === 'monthly'
            ? 'We ask for a card only when the trial ends'
            : 'Stripe Checkout · card collected on signup · 14-day Widerruf applies'
          }}
        </p>
      </div>

      <!-- Secondary line under the card -->
      <p class="text-center mt-6 font-mono" style="font-size: 11px; color: #5e7088">
        // VAT applies based on your billing address (Stripe Tax handles it)
      </p>
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
        Ready when you are.
      </h2>
      <p class="mb-8" style="font-size: 14px; color: #8ba1bd">
        Magic-link signup, 30-second setup, 7 days to decide.
      </p>
      <button
        class="px-8 py-3 rounded-xl font-mono font-semibold text-[13px] transition-all hover:opacity-90"
        style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 24px rgba(92,200,164,0.2)"
        @click="goSignIn">
        {{ auth.isAuthed ? 'Open dashboard →' : 'Start 7-day trial →' }}
      </button>
    </section>

    <!-- ─── Footer ───────────────────────────────────────────────────────── -->
    <footer class="px-6 py-8" style="border-top: 1px solid rgba(138,180,255,0.08)">
      <div class="max-w-5xl mx-auto flex items-center justify-between" style="font-size: 12px; color: #5e7088">
        <router-link to="/" class="font-mono hover:text-fg-muted transition-colors flex items-center gap-2">
          <span style="color: #5cc8a4">◈</span> Vibecell
        </router-link>
        <div class="flex gap-6">
          <button @click="goBilling" class="hover:text-fg-muted transition-colors font-mono">
            Billing
          </button>
          <router-link to="/legal" class="hover:text-fg-muted transition-colors">Privacy &amp; Terms</router-link>
        </div>
      </div>
    </footer>
  </div>
</template>
