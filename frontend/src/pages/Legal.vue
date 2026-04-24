<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRoute } from "vue-router";

import UserMenu from "@/components/app/UserMenu.vue";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const auth = useAuthStore();
const activeTab = ref<"privacy" | "terms">("privacy");
const cookieBannerVisible = ref(false);

onMounted(() => {
  if (route.query.tab === "terms") {
    activeTab.value = "terms";
  }
  if (!localStorage.getItem("cookie_consent")) {
    cookieBannerVisible.value = true;
  }
});

function acceptCookies() {
  localStorage.setItem("cookie_consent", "accepted");
  cookieBannerVisible.value = false;
}

interface LegalSection {
  heading: string;
  level: 2 | 3;
  content: string[];
  list?: string[];
}

const privacySections: LegalSection[] = [
  {
    heading: "Privacy Policy",
    level: 2,
    content: ["Last updated: 2026-04-20"],
  },
  {
    heading: "What we collect",
    level: 3,
    content: [],
    list: [
      "Email address — required to create an account.",
      "Project data — names, descriptions, context, decisions, ships, sessions, notes you create.",
      "Session cookie — a signed cookie to keep you logged in. Necessary cookie, no consent required.",
      "Usage logs — server-side logs for debugging (IP address, timestamps). Retained 30 days.",
    ],
  },
  {
    heading: "How we use your data",
    level: 3,
    content: [
      "Your data is used solely to provide the Vibecell service. We do not sell, share, or rent your data to any third party. We do not use third-party analytics, advertising pixels, or tracking cookies.",
    ],
  },
  {
    heading: "Where your data lives",
    level: 3,
    content: [
      "All data is stored on a private Hetzner server in Germany (EU). Backups are encrypted at rest.",
    ],
  },
  {
    heading: "Your rights (GDPR)",
    level: 3,
    content: ["If you are in the EU/EEA, you have the following rights:"],
    list: [
      "Access — use Settings → Export data.",
      "Correct inaccurate data — edit directly in the app.",
      "Delete your account — use Settings → Delete account. All data is permanently deleted.",
      "Portability — data export returns JSON you can download.",
      "Object — contact us at privacy@vibecell.dev.",
    ],
  },
  {
    heading: "Data retention",
    level: 3,
    content: [
      "Account data is retained until you delete your account. Server logs are retained for 30 days.",
    ],
  },
  {
    heading: "Contact",
    level: 3,
    content: ["Questions? Email privacy@vibecell.dev."],
  },
];

const termsSections: LegalSection[] = [
  {
    heading: "Terms of Service",
    level: 2,
    content: ["Last updated: 2026-04-20"],
  },
  {
    heading: "Acceptance",
    level: 3,
    content: [
      "By creating an account you agree to these terms. If you don't agree, please don't use Vibecell.",
    ],
  },
  {
    heading: "What Vibecell is",
    level: 3,
    content: [
      "Vibecell is a project context management tool for software builders. We provide a web app, CLI, and MCP server for tracking project state across sessions and AI clients.",
    ],
  },
  {
    heading: "Your content",
    level: 3,
    content: [
      "You own your content. We claim no rights over your projects, decisions, or notes. By using the service, you grant us a limited licence to store and serve your content to you.",
    ],
  },
  {
    heading: "Acceptable use",
    level: 3,
    content: ["You agree not to:"],
    list: [
      "Store illegal content.",
      "Attempt to access other users' data.",
      "Circumvent usage limits dishonestly.",
      "Scrape or extract data via automated means beyond the official API.",
    ],
  },
  {
    heading: "Service availability",
    level: 3,
    content: [
      "We aim for high availability but make no uptime guarantees on the Free plan. Pro subscribers may contact support for SLA discussions.",
    ],
  },
  {
    heading: "Limitation of liability",
    level: 3,
    content: [
      "Vibecell is provided \"as is\". We are not liable for loss of data, business interruption, or consequential damages arising from use of the service. Maximum liability is limited to fees paid in the last 3 months.",
    ],
  },
  {
    heading: "Termination",
    level: 3,
    content: [
      "We may suspend accounts that violate these terms with reasonable notice. You may delete your account at any time.",
    ],
  },
  {
    heading: "Changes",
    level: 3,
    content: [
      "We may update these terms. Significant changes will be announced via email with 14 days notice.",
    ],
  },
  {
    heading: "Governing law",
    level: 3,
    content: ["These terms are governed by the laws of Germany."],
  },
  {
    heading: "Contact",
    level: 3,
    content: ["legal@vibecell.dev"],
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
        <router-link v-else to="/login"
          class="font-mono transition-colors hover:text-fg-primary"
          style="font-size: 12px; color: #5e7088">
          Sign in →
        </router-link>
      </div>
    </header>

    <!-- ─── Page hero ─────────────────────────────────────────────────────── -->
    <section class="max-w-3xl mx-auto px-6 pt-16 pb-10">
      <div class="flex items-center gap-3 mb-6">
        <!-- Lock icon -->
        <div class="w-10 h-10 rounded-lg flex items-center justify-center"
          style="background: rgba(92,200,164,0.08); border: 1px solid rgba(92,200,164,0.2)">
          <svg viewBox="0 0 20 20" fill="none" style="width:16px;height:16px">
            <rect x="4" y="9" width="12" height="9" rx="2" stroke="#5cc8a4" stroke-width="1.5"/>
            <path d="M7 9V7a3 3 0 116 0v2" stroke="#5cc8a4" stroke-width="1.5" stroke-linecap="round"/>
          </svg>
        </div>
        <div>
          <h1 class="font-semibold" style="font-size: 1.6rem; color: #ffffff; letter-spacing: -0.03em">Legal</h1>
          <p class="font-mono" style="font-size: 11px; color: #5e7088">Last updated: April 20, 2026</p>
        </div>
      </div>

      <!-- ─── Tabs ──────────────────────────────────────────────────────── -->
      <div class="flex gap-1 p-1 rounded-xl w-fit" style="background: rgba(20,33,50,0.6); border: 1px solid rgba(138,180,255,0.1)">
        <button
          class="px-5 py-2 rounded-lg font-mono text-[12px] transition-all duration-150"
          :style="activeTab === 'privacy'
            ? 'background: rgba(92,200,164,0.12); color: #5cc8a4; border: 1px solid rgba(92,200,164,0.2)'
            : 'color: #5e7088; border: 1px solid transparent'"
          @click="activeTab = 'privacy'">
          Privacy Policy
        </button>
        <button
          class="px-5 py-2 rounded-lg font-mono text-[12px] transition-all duration-150"
          :style="activeTab === 'terms'
            ? 'background: rgba(92,200,164,0.12); color: #5cc8a4; border: 1px solid rgba(92,200,164,0.2)'
            : 'color: #5e7088; border: 1px solid transparent'"
          @click="activeTab = 'terms'">
          Terms of Service
        </button>
      </div>
    </section>

    <!-- ─── Content ──────────────────────────────────────────────────────── -->
    <main class="max-w-3xl mx-auto px-6 pb-28">
      <div class="rounded-xl p-8 md:p-10"
        style="background: rgba(20,33,50,0.35); border: 1px solid rgba(138,180,255,0.09)">
        <template v-for="(s, i) in (activeTab === 'privacy' ? privacySections : termsSections)" :key="s.heading + i">
          <!-- H2 -->
          <div v-if="s.level === 2" :class="i > 0 ? 'mt-10' : ''">
            <h2 class="font-semibold" style="font-size: 1.3rem; color: #ffffff; letter-spacing: -0.025em; margin-bottom: 4px">
              {{ s.heading }}
            </h2>
            <p v-if="s.content[0]" class="font-mono" style="font-size: 11px; color: #5e7088; margin-top: 4px; margin-bottom: 12px">
              {{ s.content[0] }}
            </p>
            <div style="height: 1px; background: rgba(138,180,255,0.08); margin: 16px 0 24px" />
          </div>

          <!-- H3 section -->
          <div v-else class="mb-8">
            <h3 class="font-semibold mb-3" style="font-size: 0.875rem; color: #cfd4dc; letter-spacing: -0.01em; text-transform: uppercase; font-size: 11px; letter-spacing: 0.06em; font-family: 'Geist Mono', monospace; color: #5cc8a4">
              {{ s.heading }}
            </h3>
            <p v-for="para in s.content" :key="para"
              style="font-size: 14px; color: #8ba1bd; line-height: 1.75; margin-bottom: 8px">
              {{ para }}
            </p>
            <ul v-if="s.list" class="mt-3 space-y-2">
              <li v-for="item in s.list" :key="item"
                class="flex gap-3"
                style="font-size: 14px; color: #8ba1bd; line-height: 1.65">
                <span style="color: #5cc8a4; flex-shrink: 0; margin-top: 2px">·</span>
                {{ item }}
              </li>
            </ul>
          </div>
        </template>
      </div>

      <!-- Switch tab nudge -->
      <p class="mt-6 text-center font-mono" style="font-size: 12px; color: #5e7088">
        <template v-if="activeTab === 'privacy'">
          Also read our
          <button class="hover:text-fg-muted transition-colors" style="color: #5cc8a4" @click="activeTab = 'terms'">
            Terms of Service →
          </button>
        </template>
        <template v-else>
          ← Back to
          <button class="hover:text-fg-muted transition-colors" style="color: #5cc8a4" @click="activeTab = 'privacy'">
            Privacy Policy
          </button>
        </template>
      </p>
    </main>

    <!-- ─── Footer ───────────────────────────────────────────────────────── -->
    <footer class="px-6 py-8" style="border-top: 1px solid rgba(138,180,255,0.08)">
      <div class="max-w-5xl mx-auto flex items-center justify-between" style="font-size: 12px; color: #5e7088">
        <router-link to="/" class="font-mono hover:text-fg-muted transition-colors flex items-center gap-2">
          <span style="color: #5cc8a4">◈</span> Vibecell
        </router-link>
        <p class="font-mono" style="font-size: 11px">© 2026 Vibecell</p>
      </div>
    </footer>

    <!-- ─── Cookie banner ─────────────────────────────────────────────────── -->
    <transition
      enter-from-class="translate-y-full opacity-0"
      enter-active-class="transition-all duration-300 ease-out"
      leave-to-class="translate-y-full opacity-0"
      leave-active-class="transition-all duration-200 ease-in">
      <div v-if="cookieBannerVisible"
        class="fixed bottom-0 left-0 right-0 z-50 px-6 py-4"
        style="background: var(--bg-chrome); backdrop-filter: blur(12px); border-top: 1px solid var(--border-subtle)">
        <div class="max-w-4xl mx-auto flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
          <p style="font-size: 12px; color: #8ba1bd">
            We use a single necessary session cookie to keep you signed in. No analytics, no tracking.
            <router-link to="/legal" style="color: #5cc8a4" class="ml-1 hover:opacity-80 transition-opacity">Learn more →</router-link>
          </p>
          <button
            class="shrink-0 px-5 py-2 rounded-lg font-mono text-[12px] hover:opacity-90 transition-opacity"
            style="background: #5cc8a4; color: #070b10"
            @click="acceptCookies">
            Got it
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>
