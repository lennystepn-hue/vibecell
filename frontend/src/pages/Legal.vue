<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import UserMenu from "@/components/app/UserMenu.vue";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const router = useRouter();
const auth = useAuthStore();

type Tab = "imprint" | "privacy" | "terms";
const activeTab = ref<Tab>("imprint");

function setTab(t: Tab) {
  activeTab.value = t;
  router.replace({ query: { ...route.query, tab: t } });
}

onMounted(() => {
  const q = String(route.query.tab ?? "imprint");
  if (q === "imprint" || q === "privacy" || q === "terms") {
    activeTab.value = q;
  }
});

function goSignIn() {
  router.push(auth.isAuthed ? "/p" : "/login");
}

const TAB_LABELS: Record<Tab, string> = {
  imprint: "// imprint",
  privacy: "// privacy",
  terms: "// terms",
};

// One last-updated date for all three documents — bumped together when
// any of them changes substantively.
const LAST_UPDATED = "2026-04-26";

const ADDRESS_LINES = [
  "Lenny David Enderle",
  "Rua Padre Manuel Bernardes 16",
  "2825-359 Costa da Caparica",
  "Portugal",
];

const CONTACT_EMAIL = "hello@vibecell.dev";
const VAT = "PT297035770";
const CAE = "62010 — Atividades de programação informática";

interface Section {
  heading: string;
  body: string[];
  list?: string[];
}

// ── Imprint / Aviso Legal ────────────────────────────────────────────────
// Required disclosures per DL 7/2004 (Portuguese e-Commerce Law,
// transposing EU Directive 2000/31/EC), art. 10.
const imprintSections = computed<Section[]>(() => [
  {
    heading: "Service provider",
    body: [
      "Vibecell is a service operated by Lenny David Enderle, sole proprietor (trabalhador independente) registered in Portugal.",
    ],
    list: ADDRESS_LINES,
  },
  {
    heading: "Tax / commercial identification",
    body: [],
    list: [
      `VAT (NIF): ${VAT}`,
      `CAE: ${CAE}`,
      "Form: Sole proprietorship (PT trabalhador independente)",
    ],
  },
  {
    heading: "Contact",
    body: [],
    list: [
      `Email: ${CONTACT_EMAIL}`,
      "Mail: see address above",
    ],
  },
  {
    heading: "Responsible for content",
    body: [
      "Lenny David Enderle is responsible for the content of this site, the Vibecell service, and the data processed therein, in accordance with art. 11 of DL 7/2004.",
    ],
  },
  {
    heading: "Hosting",
    body: [
      "Vibecell runs on Hetzner Cloud (Hetzner Online GmbH, Industriestr. 25, 91710 Gunzenhausen, Germany — within the EU). The marketing-site CDN edge is operated by Cloudflare, Inc. — visitor traffic flows through their EU points of presence by default.",
    ],
  },
  {
    heading: "Out-of-court dispute resolution",
    body: [
      "EU consumers may use the European Commission's Online Dispute Resolution platform at https://ec.europa.eu/consumers/odr. We are not currently obliged or willing to participate in dispute-resolution proceedings before a consumer arbitration board.",
    ],
  },
]);

// ── Privacy Policy / Política de Privacidade ─────────────────────────────
// Drafted to satisfy RGPD/GDPR Art. 13–14 disclosure requirements.
const privacySections = computed<Section[]>(() => [
  {
    heading: "Controller",
    body: [
      "The data controller for the personal data processed via Vibecell is Lenny David Enderle, contactable at the address and email shown in the Imprint tab.",
    ],
  },
  {
    heading: "What we collect",
    body: [],
    list: [
      "Account data — email address (required), display name and handle if you set one, optional WebAuthn passkey credential metadata (public key + counter, never your biometric).",
      "Project data — every project, session, decision, ship, idea, todo, note, secret label, and tag you create. Inline-encrypted secret values are stored AES-256-GCM-encrypted with your workspace data-encryption key.",
      "Usage logs — request timestamps, IP address (via the proxy, retained 30 days), MCP tool-call audit (which tool, when, success/failure — never the arguments).",
      "Billing data — Stripe customer ID, subscription state, invoice references. We never store card numbers; Stripe holds them under PCI DSS Level 1 certification.",
      "Cookies — one signed httpOnly session cookie. No third-party analytics, no advertising pixels, no cross-site tracking. The session cookie is strictly necessary under Art. 6(1)(b) and ePrivacy Directive Art. 5(3) — no consent banner required.",
    ],
  },
  {
    heading: "Legal basis (RGPD Art. 6)",
    body: [],
    list: [
      "Art. 6(1)(b) — performance of the contract: most processing happens to deliver the service you signed up for.",
      "Art. 6(1)(c) — legal obligation: invoice retention (10 years under Portuguese tax law), VAT reporting.",
      "Art. 6(1)(f) — legitimate interest: anti-abuse rate-limits, security logging, error monitoring (Sentry).",
    ],
  },
  {
    heading: "Sub-processors",
    body: [
      "We use the following processors. Each runs under a Data Processing Agreement and SCCs where applicable:",
    ],
    list: [
      "Hetzner Online GmbH (DE / EU) — primary hosting, all customer data at rest.",
      "Stripe Payments Europe Ltd. (IE / EU) — subscription billing + payment processing.",
      "Cloudflare, Inc. (US, with EU points of presence) — marketing-site CDN + DDoS mitigation under SCCs.",
      "Resend Inc. (US) — transactional email (sign-in links, billing notices) under SCCs.",
      "Anthropic PBC (US) — AI enrichment for opt-in features that summarise your project content. Routed through your own Anthropic key when you set one. SCCs apply.",
      "Functional Software, Inc. d/b/a Sentry (US) — error monitoring with PII scrubbing enabled (we set send_default_pii=False).",
      "Backblaze, Inc. (US) — encrypted off-site backup of the Postgres dump under SCCs. Data is also held primarily in Hetzner DE.",
    ],
  },
  {
    heading: "International transfers",
    body: [
      "Data may be transferred to the US (Anthropic, Sentry, Backblaze, Resend) and the UK (Stripe) under the EU Standard Contractual Clauses (Implementing Decision 2021/914) and supplementary measures where required (Schrems II safeguards).",
    ],
  },
  {
    heading: "Retention",
    body: [],
    list: [
      "Account + project data — for the lifetime of your account. On account deletion, data is purged within 24 hours, except as legally required to retain.",
      "Invoice metadata — 10 years from issue (Portuguese tax-law obligation, art. 123 CIVA / 16 RGCC).",
      "Server access logs — 30 days rolling.",
      "MCP audit log — for the lifetime of the workspace; deleted on account deletion.",
      "Free-account session log — 7 days rolling. Pro-account session log — 365 days rolling.",
    ],
  },
  {
    heading: "Your rights (RGPD Art. 15–22)",
    body: [
      "You have the right to:",
    ],
    list: [
      "Access — download a JSON copy of every row we hold about you via /settings/account → Download my data.",
      "Rectification — edit any project / session / decision / etc. inline in the dashboard.",
      "Erasure — delete your account at /settings/account → Danger zone. All data is purged within 24 hours.",
      "Portability — same JSON export covers Art. 20 portability.",
      "Object — opt out of future feature emails by replying STOP; transactional emails are required for the service.",
      "Restrict processing — contact us at " + CONTACT_EMAIL + " and we'll freeze your account pending resolution.",
      "Lodge a complaint — with the Comissão Nacional de Proteção de Dados (CNPD), https://www.cnpd.pt, Av. D. Carlos I 134, 1200-651 Lisboa.",
    ],
  },
  {
    heading: "No automated decision-making",
    body: [
      "Vibecell does not engage in automated decision-making producing legal effects on you within the meaning of Art. 22 RGPD. AI-based features (enrichment, retro generation) only produce text suggestions you can accept, reject, or edit.",
    ],
  },
  {
    heading: "Security",
    body: [
      "We use TLS 1.2+ for all transport. Account secrets are AES-256-GCM-encrypted at rest using a per-workspace key wrapped by a master key kept outside the database. Backups are encrypted in transit to Backblaze. We follow the principle of least privilege internally.",
    ],
  },
  {
    heading: "Changes to this policy",
    body: [
      "Material changes are announced by email to all account holders at least 14 days before they take effect. The current revision is dated above.",
    ],
  },
]);

// ── Terms of Service / Termos de Serviço ─────────────────────────────────
const termsSections = computed<Section[]>(() => [
  {
    heading: "Parties",
    body: [
      "These terms govern your use of Vibecell, a service operated by Lenny David Enderle, sole proprietor, VAT PT297035770, with address as shown in the Imprint tab (\"the Service\", \"we\", \"our\"). \"You\" / \"User\" means the natural or legal person creating an account.",
    ],
  },
  {
    heading: "Account",
    body: [
      "You create an account by signing in with a magic-link to your email or with a passkey. You are responsible for keeping your sign-in method secure and for all activity under your account. You may delete your account at any time from /settings/account.",
    ],
  },
  {
    heading: "Service description",
    body: [
      "Vibecell is a project-management dashboard with an MCP (Model Context Protocol) server that lets your AI client read and write your project state. Available features and limits are described on the Pricing page (https://vibecell.dev/pricing).",
    ],
  },
  {
    heading: "Subscription, billing, renewal",
    body: [],
    list: [
      "Pro Monthly: €8.99 per month. Includes a 7-day free trial. No credit card required to start the trial. After the trial, you must add a payment method to keep using paid features.",
      "Pro Annual: €99.99 per year, billed once. Launch promotion (first 100 customers via Stripe coupon LAUNCH69): €69.99 for the first year only — renewal is at the standard €99.99/year.",
      "All prices are net of VAT. EU customers are charged the local VAT rate by Stripe Tax based on the billing address you provide at checkout. Reverse-charge applies to verified EU B2B customers with a valid VAT-ID.",
      "Subscriptions auto-renew at the end of each billing period unless you cancel from the Stripe Customer Portal at /settings/billing → Manage subscription. Cancellation takes effect at the end of the current period; access is preserved until then.",
    ],
  },
  {
    heading: "Right of withdrawal (Direito de Livre Resolução)",
    body: [
      "Under DL 24/2014 (transposing EU Consumer Rights Directive 2011/83/EU), as a consumer you have a 14-day period to withdraw from a distance contract without giving any reason. The period starts on the day the contract is concluded.",
      "For Vibecell, the contract is concluded when you complete payment in Stripe Checkout. By clicking the Pay button, you expressly request that performance of the service begin immediately, and you acknowledge that you will lose the right of withdrawal once the service is fully performed (DL 24/2014 art. 17 nº 2 al. m).",
      "If you wish to withdraw within the 14-day window, email " + CONTACT_EMAIL + " before the period expires. We will refund the full amount paid (less any value of services already consumed during the trial / subscription period, calculated pro-rata) within 14 days using the same payment method.",
    ],
  },
  {
    heading: "Acceptable use",
    body: [
      "You agree not to use the Service to (a) violate any law, (b) infringe intellectual-property or privacy rights of third parties, (c) attempt to bypass billing or rate limits, (d) reverse-engineer or stress-test the platform without our written permission, (e) store data subject to special category protection (RGPD Art. 9) — Vibecell is not designed for healthcare, financial, or biometric special-category data.",
    ],
  },
  {
    heading: "Read-only mode on lapsed subscription",
    body: [
      "When your subscription becomes inactive (canceled, unpaid, or trial expired without payment method), the Service moves into read-only mode: you keep access to read all your existing data, export it, and delete your account, but cannot create new sessions, decisions, ships, or projects until you re-subscribe. Data is preserved indefinitely for re-subscribe.",
    ],
  },
  {
    heading: "Service availability",
    body: [
      "We aim for high availability but do not commit to a formal SLA. We perform planned maintenance with reasonable notice via email and the in-app status banner. Emergency security maintenance may proceed without prior notice.",
    ],
  },
  {
    heading: "Liability",
    body: [
      "To the maximum extent permitted by law, our total liability under or in connection with the Service is limited to the amount you paid us in the twelve (12) months preceding the event giving rise to the claim, but in no event less than €20 nor more than €1,000.",
      "We exclude liability for indirect, consequential, special, or punitive damages, including loss of profits, business, or data — except where such exclusion is prohibited (e.g., consumer mandatory rights, gross negligence, intentional misconduct, death/personal injury, art. 6 of DL 67/2003).",
    ],
  },
  {
    heading: "Termination",
    body: [
      "You may terminate by deleting your account at any time. We may suspend or terminate your account immediately if you breach these terms, fail to pay for two consecutive billing cycles, or are required to do so by law. Sections that by their nature should survive termination (Liability, Governing law, Tax retention) survive.",
    ],
  },
  {
    heading: "Changes to these terms",
    body: [
      "We may update these terms from time to time. Material changes are announced by email to all account holders at least 14 days before they take effect. Continued use after the effective date constitutes acceptance.",
    ],
  },
  {
    heading: "Governing law and forum",
    body: [
      "These terms are governed by the laws of Portugal, excluding choice-of-law rules. Mandatory consumer-protection rules of your country of habitual residence remain available to you.",
      "Any dispute is subject to the exclusive jurisdiction of the Tribunais Judiciais de Lisboa, Portugal — without prejudice to your right as a consumer to bring the dispute before the courts of your country of habitual residence under Reg. (EU) 1215/2012.",
    ],
  },
  {
    heading: "Contact",
    body: [
      `For any question about these terms, write to ${CONTACT_EMAIL}. We typically respond within 3 business days.`,
    ],
  },
]);

const visibleSections = computed<Section[]>(() => {
  if (activeTab.value === "imprint") return imprintSections.value;
  if (activeTab.value === "privacy") return privacySections.value;
  return termsSections.value;
});
</script>

<template>
  <div class="min-h-screen text-fg-primary" style="background: #070b10">
    <!-- Header -->
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
          {{ auth.isAuthed ? 'Open dashboard →' : 'Start trial →' }}
        </button>
      </div>
    </header>

    <!-- Hero -->
    <section class="max-w-3xl mx-auto px-4 sm:px-6 pt-16 sm:pt-20 pb-8 sm:pb-10 text-center">
      <p class="font-mono text-[10px] uppercase tracking-[0.18em] mb-3" style="color: #5cc8a4">
        // legal
      </p>
      <h1 class="font-semibold mb-3" style="font-size: clamp(1.8rem, 3.5vw, 2.6rem); letter-spacing: -0.04em; color: #ffffff">
        Imprint, Privacy, Terms.
      </h1>
      <p style="color: #8ba1bd; font-size: 13px">
        Last updated <span class="font-mono">{{ LAST_UPDATED }}</span> · operated under Portuguese law from Costa da Caparica
      </p>
    </section>

    <!-- Tabs -->
    <div class="max-w-3xl mx-auto px-4 sm:px-6 mb-6 sm:mb-8">
      <div class="inline-flex rounded-md p-1 font-mono"
        style="background: rgba(20,33,50,0.6); border: 1px solid rgba(138,180,255,0.1)">
        <button
          v-for="t in (['imprint', 'privacy', 'terms'] as const)"
          :key="t"
          class="px-4 py-1.5 rounded text-[11px] uppercase tracking-wider transition-all"
          :style="{
            background: activeTab === t ? '#5cc8a4' : 'transparent',
            color: activeTab === t ? '#070b10' : '#8ba1bd',
            fontWeight: activeTab === t ? 600 : 400,
          }"
          @click="setTab(t)"
        >{{ TAB_LABELS[t] }}</button>
      </div>
    </div>

    <!-- Body -->
    <article class="max-w-3xl mx-auto px-4 sm:px-6 pb-20 sm:pb-32">
      <div
        v-for="(s, i) in visibleSections"
        :key="`${activeTab}-${i}`"
        class="mb-9"
      >
        <h2 class="font-semibold mb-3" style="font-size: 18px; color: #ffffff; letter-spacing: -0.01em">
          {{ s.heading }}
        </h2>
        <p
          v-for="(p, j) in s.body"
          :key="j"
          class="mb-3"
          style="font-size: 14px; color: #cfd4dc; line-height: 1.7"
        >
          {{ p }}
        </p>
        <ul v-if="s.list && s.list.length > 0" class="space-y-2 mt-3">
          <li
            v-for="(item, j) in s.list"
            :key="j"
            class="flex gap-3 items-start"
            style="font-size: 13px; color: #8ba1bd; line-height: 1.65"
          >
            <span style="color:#5cc8a4; flex-shrink: 0">·</span>
            <span>{{ item }}</span>
          </li>
        </ul>
      </div>
    </article>

    <!-- Footer -->
    <footer class="px-6 py-8" style="border-top: 1px solid rgba(138,180,255,0.08)">
      <div class="max-w-5xl mx-auto flex items-center justify-between" style="font-size: 11px; color: #5e7088">
        <router-link to="/" class="font-mono hover:text-fg-muted transition-colors flex items-center gap-2">
          <span style="color: #5cc8a4">◈</span> Vibecell
        </router-link>
        <div class="flex gap-6 font-mono">
          <router-link to="/pricing" class="hover:text-fg-muted transition-colors">pricing</router-link>
          <a href="mailto:hello@vibecell.dev" class="hover:text-fg-muted transition-colors">{{ CONTACT_EMAIL }}</a>
        </div>
      </div>
    </footer>
  </div>
</template>
