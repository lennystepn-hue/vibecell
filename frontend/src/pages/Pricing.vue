<script setup lang="ts">
import { useRouter } from "vue-router";

const router = useRouter();

function goSignIn() {
  router.push("/login");
}
</script>

<template>
  <div class="min-h-screen bg-bg-base text-fg-primary">
    <!-- Nav -->
    <header class="flex items-center justify-between px-6 py-4 border-b border-border-subtle">
      <router-link to="/" class="flex items-center gap-2">
        <span class="text-signal-green font-mono text-section">◈</span>
        <span class="font-mono text-small tracking-[0.08em] uppercase text-fg-subtle">Vibecell</span>
      </router-link>
      <button
        class="px-4 py-1.5 rounded text-small font-mono bg-signal-green text-bg-base hover:opacity-90 transition-opacity"
        @click="goSignIn"
      >
        Sign in →
      </button>
    </header>

    <!-- Hero -->
    <section class="max-w-3xl mx-auto px-6 pt-20 pb-10 text-center">
      <h1 class="text-display text-fg-primary mb-4">Pricing</h1>
      <p class="text-fg-muted text-title">Simple, honest pricing. Start free. Pay when you grow.</p>
    </section>

    <!-- Plans -->
    <section class="max-w-4xl mx-auto px-6 pb-20 grid md:grid-cols-2 gap-8">
      <!-- Free -->
      <div class="glass rounded-xl p-8 border border-border-subtle flex flex-col">
        <div>
          <p class="font-mono text-small text-fg-subtle uppercase tracking-widest mb-3">Free</p>
          <div class="flex items-end gap-1 mb-2">
            <span class="text-[3rem] font-bold text-fg-primary leading-none">$0</span>
          </div>
          <p class="text-small text-fg-muted mb-8">Forever free, no credit card needed</p>

          <ul class="space-y-3 text-small text-fg-muted mb-8">
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> 3 active projects</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> 500 MCP calls / month</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> Magic link sign-in</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> GitHub integration</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> Ship loop (ships, sessions, decisions)</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> CLI + MCP access</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> 1 workspace seat</li>
          </ul>
        </div>

        <button
          class="w-full py-2.5 rounded border border-border-subtle text-small font-mono text-fg-muted hover:text-fg-body hover:border-border-default transition-colors mt-auto"
          @click="goSignIn"
        >
          Get started free
        </button>
      </div>

      <!-- Pro -->
      <div class="glass rounded-xl p-8 border border-signal-green/40 flex flex-col relative overflow-hidden">
        <div class="absolute top-0 right-0 px-3 py-1 bg-signal-green text-bg-base font-mono text-[10px] uppercase tracking-widest rounded-bl">
          Popular
        </div>
        <div>
          <p class="font-mono text-small text-signal-green uppercase tracking-widest mb-3">Pro</p>
          <div class="flex items-end gap-1 mb-2">
            <span class="text-[3rem] font-bold text-fg-primary leading-none">$12</span>
            <span class="text-fg-muted mb-2">/ month</span>
          </div>
          <p class="text-small text-fg-muted mb-8">Per workspace · cancel any time</p>

          <ul class="space-y-3 text-small text-fg-muted mb-8">
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> <strong class="text-fg-primary">Unlimited</strong> projects</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> 10,000 MCP calls / month</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> Passkey login (Touch ID / Face ID)</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> Up to 5 workspace seats</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> Auto-signals (health, uptime)</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> Portfolio Intel (activity heatmap)</li>
            <li class="flex gap-3"><span class="text-signal-green mt-0.5">✓</span> Priority support</li>
          </ul>
        </div>

        <button
          class="w-full py-2.5 rounded bg-signal-green text-bg-base font-mono text-small hover:opacity-90 transition-opacity mt-auto"
          @click="goSignIn"
        >
          Start free trial →
        </button>
        <p class="text-[11px] text-fg-subtle text-center mt-2">14-day free trial, no credit card</p>
      </div>
    </section>

    <!-- FAQ -->
    <section class="max-w-2xl mx-auto px-6 pb-24">
      <h2 class="text-title text-fg-primary mb-8 text-center">Common questions</h2>
      <div class="space-y-6">
        <div>
          <h3 class="text-section text-fg-primary mb-1">Can I use Vibecell without paying?</h3>
          <p class="text-small text-fg-muted">Yes. The Free plan includes everything you need to get started — up to 3 projects and full MCP access.</p>
        </div>
        <div>
          <h3 class="text-section text-fg-primary mb-1">What counts as an MCP call?</h3>
          <p class="text-small text-fg-muted">Any tool invocation via the MCP protocol — reading context, logging a decision, fetching project data. Calls from the web UI don't count.</p>
        </div>
        <div>
          <h3 class="text-section text-fg-primary mb-1">Can I cancel any time?</h3>
          <p class="text-small text-fg-muted">Yes. Cancel from your billing settings. You keep Pro access until the end of the billing period.</p>
        </div>
        <div>
          <h3 class="text-section text-fg-primary mb-1">Is my data safe?</h3>
          <p class="text-small text-fg-muted">Your data is stored in a private Postgres instance on Hetzner (EU). We don't sell or share your data. See our <router-link to="/legal" class="text-fg-body underline">privacy policy</router-link>.</p>
        </div>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-border-subtle py-8 px-6">
      <div class="max-w-4xl mx-auto flex items-center justify-between text-small text-fg-subtle">
        <router-link to="/" class="font-mono uppercase tracking-widest hover:text-fg-muted transition-colors">
          ← Vibecell
        </router-link>
        <div class="flex gap-6">
          <router-link to="/legal" class="hover:text-fg-muted transition-colors">Privacy &amp; Terms</router-link>
        </div>
      </div>
    </footer>
  </div>
</template>
