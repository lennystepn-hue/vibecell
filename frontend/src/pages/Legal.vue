<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";

const route = useRoute();
const activeTab = ref<"privacy" | "terms">("privacy");
const cookieBannerVisible = ref(false);

onMounted(() => {
  // Allow ?tab=terms to deep-link
  if (route.query.tab === "terms") {
    activeTab.value = "terms";
  }
  // Show cookie banner if not yet consented
  if (!localStorage.getItem("cookie_consent")) {
    cookieBannerVisible.value = true;
  }
});

function acceptCookies() {
  localStorage.setItem("cookie_consent", "accepted");
  cookieBannerVisible.value = false;
}

const PRIVACY_POLICY = `
## Privacy Policy

**Last updated: 2026-04-20**

### What we collect

- **Email address** — required to create an account.
- **Project data** — names, descriptions, context, decisions, ships, sessions, notes you create.
- **Session cookie** — a signed cookie to keep you logged in. Necessary cookie, no consent required.
- **Usage logs** — server-side logs for debugging (IP address, timestamps). Retained 30 days.

We do **not** use third-party analytics, advertising pixels, or tracking cookies.

### How we use your data

Your data is used solely to provide the Vibecell service. We do not sell, share, or rent your data to any third party.

### Where your data lives

All data is stored on a private Hetzner server in Germany (EU). Backups are encrypted at rest.

### Your rights (GDPR)

If you are in the EU/EEA, you have the right to:
- **Access** your data — use Settings → Export data.
- **Correct** inaccurate data — edit directly in the app.
- **Delete** your account — use Settings → Delete account. All data is permanently deleted.
- **Portability** — data export returns JSON you can download.
- **Object** — contact us at privacy@vibecell.dev.

### Data retention

Account data is retained until you delete your account. Server logs are retained for 30 days.

### Contact

Questions? Email privacy@vibecell.dev.
`;

const TERMS_OF_SERVICE = `
## Terms of Service

**Last updated: 2026-04-20**

### Acceptance

By creating an account you agree to these terms. If you don't agree, don't use Vibecell.

### What Vibecell is

Vibecell is a project context management tool for software builders. We provide a web app, CLI, and MCP server for tracking project state.

### Your content

You own your content. We claim no rights over your projects, decisions, or notes. By using the service, you grant us a limited licence to store and serve your content to you.

### Acceptable use

Do not use Vibecell to:
- Store illegal content.
- Attempt to access other users' data.
- Circumvent usage limits dishonestly.
- Scrape or extract data via automated means beyond the official API.

### Service availability

We aim for high availability but make no uptime guarantees on the Free plan. Pro subscribers may contact support for SLA discussions.

### Limitation of liability

Vibecell is provided "as is". We are not liable for loss of data, business interruption, or consequential damages arising from use of the service. Maximum liability is limited to fees paid in the last 3 months.

### Termination

We may suspend accounts that violate these terms with reasonable notice. You may delete your account at any time.

### Changes

We may update these terms. Significant changes will be announced via email with 14 days notice.

### Governing law

These terms are governed by the laws of Germany.

### Contact

legal@vibecell.dev
`;

function renderMarkdown(text: string): string {
  // Minimal markdown: headings, bold, lists, line breaks
  return text
    .replace(/^### (.+)$/gm, '<h3 class="text-section text-fg-primary mt-6 mb-2">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-title text-fg-primary mt-8 mb-3">$1</h2>')
    .replace(/\*\*(.+?)\*\*/g, '<strong class="text-fg-body">$1</strong>')
    .replace(/^- (.+)$/gm, '<li class="ml-4 list-disc text-fg-muted text-small">$1</li>')
    .replace(/\n\n/g, '<br><br>');
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
      <router-link to="/login" class="text-small text-fg-muted hover:text-fg-body transition-colors">
        Sign in →
      </router-link>
    </header>

    <!-- Content -->
    <main class="max-w-2xl mx-auto px-6 py-16">
      <h1 class="text-display text-fg-primary mb-8">Legal</h1>

      <!-- Tabs -->
      <div class="flex gap-1 mb-10 border-b border-border-subtle">
        <button
          class="px-4 py-2 text-small font-mono transition-colors"
          :class="activeTab === 'privacy' ? 'text-fg-primary border-b-2 border-signal-green -mb-px' : 'text-fg-muted hover:text-fg-body'"
          @click="activeTab = 'privacy'"
        >
          Privacy Policy
        </button>
        <button
          class="px-4 py-2 text-small font-mono transition-colors"
          :class="activeTab === 'terms' ? 'text-fg-primary border-b-2 border-signal-green -mb-px' : 'text-fg-muted hover:text-fg-body'"
          @click="activeTab = 'terms'"
        >
          Terms of Service
        </button>
      </div>

      <!-- Privacy Policy -->
      <div
        v-if="activeTab === 'privacy'"
        class="prose-vibecell text-fg-muted leading-relaxed"
        v-html="renderMarkdown(PRIVACY_POLICY)"
      />

      <!-- Terms of Service -->
      <div
        v-if="activeTab === 'terms'"
        class="prose-vibecell text-fg-muted leading-relaxed"
        v-html="renderMarkdown(TERMS_OF_SERVICE)"
      />
    </main>

    <!-- Cookie banner -->
    <transition
      enter-from-class="translate-y-full opacity-0"
      enter-active-class="transition-all duration-300 ease-out"
      leave-to-class="translate-y-full opacity-0"
      leave-active-class="transition-all duration-200 ease-in"
    >
      <div
        v-if="cookieBannerVisible"
        class="fixed bottom-0 left-0 right-0 z-50 bg-bg-elevated border-t border-border-subtle px-6 py-4"
      >
        <div class="max-w-4xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p class="text-small text-fg-muted">
            We use a necessary session cookie to keep you signed in. No tracking or advertising cookies.
            <router-link to="/legal" class="text-fg-body underline ml-1">Learn more</router-link>
          </p>
          <button
            class="shrink-0 px-4 py-1.5 rounded bg-signal-green text-bg-base font-mono text-small hover:opacity-90 transition-opacity"
            @click="acceptCookies"
          >
            Got it
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>
