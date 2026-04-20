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
      <div class="flex items-center gap-2">
        <span class="text-signal-green font-mono text-section">◈</span>
        <span class="font-mono text-small tracking-[0.08em] uppercase text-fg-subtle">Vibecell</span>
      </div>
      <nav class="flex items-center gap-6">
        <router-link to="/pricing" class="text-small text-fg-muted hover:text-fg-body transition-colors">
          Pricing
        </router-link>
        <router-link to="/legal" class="text-small text-fg-muted hover:text-fg-body transition-colors">
          Legal
        </router-link>
        <button
          class="px-4 py-1.5 rounded text-small font-mono bg-signal-green text-bg-base hover:opacity-90 transition-opacity"
          @click="goSignIn"
        >
          Sign in →
        </button>
      </nav>
    </header>

    <!-- Hero -->
    <section class="flex flex-col items-center text-center px-6 pt-24 pb-16 max-w-3xl mx-auto">
      <div class="inline-flex items-center gap-2 px-3 py-1 rounded-full border border-border-subtle text-small text-fg-muted mb-8 font-mono">
        <span class="text-signal-green">●</span> Now in early access
      </div>

      <h1 class="text-display text-fg-primary mb-6 leading-tight">
        Remember every project<br>you ship.
      </h1>

      <p class="text-title text-fg-muted mb-10 max-w-lg leading-relaxed">
        Vibecell is the project context layer for solo builders.
        Your AI assistant always knows where you left off.
      </p>

      <button
        class="px-8 py-3 rounded-md bg-signal-green text-bg-base font-mono text-section hover:opacity-90 transition-opacity mb-4"
        @click="goSignIn"
      >
        Sign in free →
      </button>

      <p class="text-small text-fg-subtle">No credit card required. Free plan included.</p>
    </section>

    <!-- Value props -->
    <section class="max-w-4xl mx-auto px-6 pb-24 grid md:grid-cols-3 gap-6">
      <div class="glass rounded-lg p-6">
        <div class="text-2xl mb-4">🗂</div>
        <h3 class="text-section text-fg-primary mb-2">Context, not chaos</h3>
        <p class="text-small text-fg-muted leading-relaxed">
          Every project keeps its own focus, next step, and open questions.
          Never lose the thread across sessions, tools, or AI assistants.
        </p>
      </div>

      <div class="glass rounded-lg p-6">
        <div class="text-2xl mb-4">⚡</div>
        <h3 class="text-section text-fg-primary mb-2">MCP-native</h3>
        <p class="text-small text-fg-muted leading-relaxed">
          Connect Claude or any MCP client directly. Your projects become
          first-class tools — no copy-paste, no blown context windows.
        </p>
      </div>

      <div class="glass rounded-lg p-6">
        <div class="text-2xl mb-4">📊</div>
        <h3 class="text-section text-fg-primary mb-2">One workspace, many projects</h3>
        <p class="text-small text-fg-muted leading-relaxed">
          Track decisions, ship events, sessions, and ideas across your
          whole portfolio. See what's stagnant. Ship more.
        </p>
      </div>
    </section>

    <!-- Pricing teaser -->
    <section class="border-t border-border-subtle py-20 px-6">
      <div class="max-w-2xl mx-auto text-center">
        <h2 class="text-title text-fg-primary mb-4">Simple pricing</h2>
        <p class="text-fg-muted mb-10">Start free. Upgrade when you need more.</p>

        <div class="grid md:grid-cols-2 gap-6 text-left">
          <div class="glass rounded-lg p-6 border border-border-subtle">
            <p class="font-mono text-small text-fg-subtle mb-2 uppercase tracking-widest">Free</p>
            <p class="text-display text-fg-primary mb-1">$0</p>
            <p class="text-small text-fg-muted mb-6">forever</p>
            <ul class="space-y-2 text-small text-fg-muted">
              <li class="flex gap-2"><span class="text-signal-green">✓</span> 3 projects</li>
              <li class="flex gap-2"><span class="text-signal-green">✓</span> 500 MCP calls / month</li>
              <li class="flex gap-2"><span class="text-signal-green">✓</span> Magic link login</li>
              <li class="flex gap-2"><span class="text-signal-green">✓</span> GitHub integration</li>
            </ul>
          </div>

          <div class="glass rounded-lg p-6 border border-signal-green/30">
            <p class="font-mono text-small text-signal-green mb-2 uppercase tracking-widest">Pro</p>
            <p class="text-display text-fg-primary mb-1">$12</p>
            <p class="text-small text-fg-muted mb-6">per month</p>
            <ul class="space-y-2 text-small text-fg-muted">
              <li class="flex gap-2"><span class="text-signal-green">✓</span> Unlimited projects</li>
              <li class="flex gap-2"><span class="text-signal-green">✓</span> 10,000 MCP calls / month</li>
              <li class="flex gap-2"><span class="text-signal-green">✓</span> Passkey login</li>
              <li class="flex gap-2"><span class="text-signal-green">✓</span> Up to 5 seats</li>
            </ul>
          </div>
        </div>

        <router-link to="/pricing" class="inline-block mt-8 text-small text-fg-muted hover:text-fg-body transition-colors">
          See full pricing details →
        </router-link>
      </div>
    </section>

    <!-- Footer -->
    <footer class="border-t border-border-subtle py-8 px-6">
      <div class="max-w-4xl mx-auto flex flex-col md:flex-row items-center justify-between gap-4 text-small text-fg-subtle">
        <div class="flex items-center gap-2">
          <span class="text-signal-green font-mono">◈</span>
          <span class="font-mono uppercase tracking-widest">Vibecell</span>
        </div>
        <div class="flex gap-6">
          <router-link to="/pricing" class="hover:text-fg-muted transition-colors">Pricing</router-link>
          <router-link to="/legal" class="hover:text-fg-muted transition-colors">Privacy</router-link>
          <router-link to="/legal?tab=terms" class="hover:text-fg-muted transition-colors">Terms</router-link>
        </div>
        <p class="font-mono">© 2026 Vibecell</p>
      </div>
    </footer>
  </div>
</template>
