<script setup lang="ts">
/**
 * /admin/settings — read-only display of platform-wide settings that
 * are configured server-side via /etc/hangar/hangar.env. Nothing is
 * editable here on purpose — flipping admin emails or trial defaults
 * via UI would weaken the defense-in-depth model. Edit the env file
 * + restart backend to change anything.
 */
</script>

<template>
  <div class="max-w-[900px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
    <header class="mb-6">
      <p class="font-mono text-[11px] uppercase tracking-[0.15em] text-signal-green mb-1">// admin · settings</p>
      <h1 class="text-display text-fg-primary tracking-tight">Settings</h1>
      <p class="text-body text-fg-muted mt-1">
        Platform-wide configuration. Read-only here on purpose — edit
        <code class="font-mono text-fg-body">/etc/hangar/hangar.env</code> on the server +
        restart the backend container to change anything.
      </p>
    </header>

    <section class="glass rounded-lg p-5 mb-6">
      <h3 class="mono-label text-fg-muted mb-3">// admin gate</h3>
      <p class="text-small text-fg-muted leading-relaxed mb-3">
        Two layers must agree before <code class="font-mono">/api/v1/admin/*</code> is reachable.
      </p>
      <ul class="space-y-2 text-small">
        <li class="flex items-start gap-2">
          <span class="font-mono text-signal-green mt-0.5">1.</span>
          <span><code class="font-mono text-fg-body">HANGAR_ADMIN_EMAILS</code> env (comma-separated). Set to <code class="font-mono">lennystepn@gmail.com</code> by default. Edit the env file to add others.</span>
        </li>
        <li class="flex items-start gap-2">
          <span class="font-mono text-signal-green mt-0.5">2.</span>
          <span><code class="font-mono text-fg-body">users.is_admin = true</code> DB flag. Promote/demote via the per-user action panel on /admin/users.</span>
        </li>
        <li class="flex items-start gap-2">
          <span class="font-mono text-signal-green mt-0.5">3.</span>
          <span>Write actions additionally require a fresh <strong>TOTP</strong> code (X-Vibecell-2FA header). Set up on /settings.</span>
        </li>
      </ul>
    </section>

    <section class="glass rounded-lg p-5 mb-6">
      <h3 class="mono-label text-fg-muted mb-3">// trial defaults</h3>
      <ul class="space-y-1.5 text-small font-mono">
        <li class="flex justify-between">
          <span class="text-fg-subtle">trial period</span>
          <span class="text-fg-body">7 days (set on plans.trial_period_days)</span>
        </li>
        <li class="flex justify-between">
          <span class="text-fg-subtle">warning emails</span>
          <span class="text-fg-body">T-3 · T-1 · T-0 (final)</span>
        </li>
        <li class="flex justify-between">
          <span class="text-fg-subtle">lifecycle cron</span>
          <span class="text-fg-body">hourly</span>
        </li>
        <li class="flex justify-between">
          <span class="text-fg-subtle">expired-trial flip</span>
          <span class="text-fg-body">trialing → past_due (status auto-flip on T-0)</span>
        </li>
      </ul>
    </section>

    <section class="glass rounded-lg p-5">
      <h3 class="mono-label text-fg-muted mb-3">// pricing</h3>
      <ul class="space-y-1.5 text-small font-mono">
        <li class="flex justify-between">
          <span class="text-fg-subtle">monthly</span>
          <span class="text-fg-body">€8.99 / month</span>
        </li>
        <li class="flex justify-between">
          <span class="text-fg-subtle">annual</span>
          <span class="text-fg-body">€99.99 / year (~7% off)</span>
        </li>
        <li class="flex justify-between">
          <span class="text-fg-subtle">launch coupon</span>
          <span class="text-fg-body">LAUNCH69 · €69.99/yr · first 100 only</span>
        </li>
      </ul>
      <p class="text-[11px] text-fg-subtle font-mono mt-4 pt-4 border-t border-border-subtle">
        Stripe price IDs live in HANGAR_STRIPE_PRO_PRICE_ID + HANGAR_STRIPE_PRO_ANNUAL_PRICE_ID.
        Coupons live in Stripe directly — manage them on /admin/coupons.
      </p>
    </section>
  </div>
</template>
