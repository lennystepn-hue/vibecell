<template>
<!-- ─── Footer ───────────────────────────────────────────────────────── -->
<footer class="px-6 py-10" style="border-top: 1px solid var(--border-subtle)">
  <div class="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
    <!-- Logo -->
    <div class="flex items-center gap-2.5">
      <span class="font-mono" style="font-size: 20px; color: var(--signal-green)">◈</span>
      <span class="font-mono text-micro tracking-caps uppercase" style="color: var(--fg-subtle)">Vibecell</span>
    </div>
    <!-- Links -->
    <nav class="flex flex-wrap justify-center gap-6" style="font-size: 12px; color: var(--fg-subtle)">
      <router-link to="/pricing" class="hover:text-fg-muted transition-colors">Pricing</router-link>
      <router-link to="/legal?tab=imprint" class="hover:text-fg-muted transition-colors">Imprint</router-link>
      <router-link to="/legal?tab=privacy" class="hover:text-fg-muted transition-colors">Privacy</router-link>
      <router-link to="/legal?tab=terms" class="hover:text-fg-muted transition-colors">Terms</router-link>
      <a href="https://github.com/lennystepn-hue/vibecell" target="_blank" rel="noopener" class="hover:text-fg-muted transition-colors">GitHub</a>
      <a href="mailto:hello@vibecell.dev" class="hover:text-fg-muted transition-colors">Contact</a>
    </nav>
    <!-- Copyright -->
    <p class="font-mono" style="font-size: 11px; color: var(--fg-subtle)">© 2026 Vibecell</p>
  </div>
</footer>
</template>
