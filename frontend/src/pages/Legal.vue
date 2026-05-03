<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

import MarketingHeader from "@/components/marketing/MarketingHeader.vue";
import { useRouteMeta } from "@/composables/useMeta";
import { denyConsent } from "@/lib/analytics";

function revokeAnalytics() {
  denyConsent();
  // Tiny, native confirmation — no toast plumbing in this page yet.
  alert("Analytics opt-out saved. Reload the page and gtag.js will not load.");
}

const route = useRoute();
const router = useRouter();

type Tab = "imprint" | "privacy" | "terms";

const META_TITLES: Record<Tab, string> = {
  imprint: "Imprint — Vibecell",
  privacy: "Privacy — Vibecell · GDPR / RGPD compliant",
  terms:   "Terms — Vibecell · DL 24/2014",
};
const META_DESCS: Record<Tab, string> = {
  imprint: "Imprint + operator details for Vibecell — Lenny David Enderle, Costa da Caparica, VAT PT297035770.",
  privacy: "How Vibecell handles your data — GDPR Art. 13–14, 17, 20 compliant. EU-hosted, BYOK AI, no third-party analytics.",
  terms:   "Vibecell Terms of Service — DL 24/2014 compliant, 14-day Widerruf, EU-VAT invoicing via Stripe Tax.",
};

useRouteMeta(() => {
  const tab = (typeof route.query.tab === "string" ? route.query.tab : "imprint") as Tab;
  return {
    title: META_TITLES[tab] ?? META_TITLES.imprint,
    description: META_DESCS[tab] ?? META_DESCS.imprint,
    canonical: `https://vibecell.dev/legal?tab=${tab}`,
  };
});
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

const TAB_LABELS: Record<Tab, string> = {
  imprint: "// imprint",
  privacy: "// privacy",
  terms: "// terms",
};

// One last-updated date for all three documents — bumped together when
// any of them changes substantively.
const LAST_UPDATED = "2026-05-03";

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
// transposing EU Directive 2000/31/EC), art. 10. Plus DSGVO Art. 13(1)(a)
// controller-identification disclosure piggy-backed where it overlaps.
const imprintSections = computed<Section[]>(() => [
  {
    heading: "Service provider",
    body: [
      "Vibecell (\"the Service\") is operated by Lenny David Enderle, sole proprietor (Empresário em Nome Individual / trabalhador independente) registered in Portugal. There is no separate legal entity behind Vibecell — the operator is a natural person trading under the Vibecell brand.",
    ],
    list: ADDRESS_LINES,
  },
  {
    heading: "Tax + commercial identification",
    body: [],
    list: [
      `VAT (NIF): ${VAT} — issued under Art. 36 CIVA, valid for intra-EU B2B reverse-charge`,
      `Activity code (CAE): ${CAE}`,
      "Form: Empresário em Nome Individual (PT sole proprietor)",
      "Tax authority of registration: Autoridade Tributária e Aduaneira (AT), Portugal",
      "Professional supervisory authority: not applicable — independent IT service provision is not a regulated profession in Portugal",
      "Professional indemnity insurance: not currently carried; service is offered without warranty as set out in the Terms",
    ],
  },
  {
    heading: "Contact",
    body: [
      "We respond to written enquiries within 3 business days during normal operations. Emergency security or privacy requests are prioritised.",
    ],
    list: [
      `Email (general / billing / privacy): ${CONTACT_EMAIL}`,
      "Postal: see address above",
      "Phone: not published — to limit social-engineering vectors against the founder. Email is the only supported written channel.",
    ],
  },
  {
    heading: "Responsible for content",
    body: [
      "Lenny David Enderle is responsible for the content of this website, the Vibecell service, and the data processed therein, in accordance with art. 11 of DL 7/2004 and § 18(2) of the German Medienstaatsvertrag for any content reachable from Germany.",
    ],
  },
  {
    heading: "Hosting + infrastructure",
    body: [
      "Vibecell runs on Hetzner Cloud (Hetzner Online GmbH, Industriestr. 25, 91710 Gunzenhausen, Germany — EU). The marketing-site CDN edge is operated by Cloudflare, Inc. — visitor traffic flows through their EU points of presence by default. Off-site backups land at Backblaze B2 (Backblaze, Inc., US) under Standard Contractual Clauses with Schrems II safeguards.",
    ],
  },
  {
    heading: "Out-of-court dispute resolution",
    body: [
      "EU consumers may use the European Commission's Online Dispute Resolution platform at https://ec.europa.eu/consumers/odr. We are not currently obliged or willing to participate in dispute-resolution proceedings before a specific consumer arbitration board (under § 36(1)(1) VSBG / Lei 144/2015 art. 18). The right to bring a claim before a competent court remains unaffected.",
    ],
  },
  {
    heading: "Liability for content + links",
    body: [
      "We take reasonable care that the content presented on this site is accurate and current, but provide it without warranty. External links to third-party sites point to content over which we have no control; their operators are solely responsible for their own content. Where we become aware of unlawful content on a linked page, the link is removed without delay.",
    ],
  },
  {
    heading: "Copyright",
    body: [
      "Unless otherwise marked, all content on this website (text, graphics, logos, source code excerpts shown for documentation purposes) is © 2026 Lenny David Enderle, all rights reserved. Reproduction beyond the scope of normal browser caching requires prior written permission. Open-source software components used by the Service retain their respective licences (see github.com/lennystepn-hue/vibecell for the SBOM).",
    ],
  },
]);

// ── Privacy Policy / Política de Privacidade ─────────────────────────────
// Drafted to satisfy RGPD/GDPR Art. 13–14 disclosure requirements + the
// transparency-of-processing principles in Art. 5(1)(a). We deliberately
// over-document so a CNPD inquiry can be answered with "see section X"
// rather than improvised explanations.
const privacySections = computed<Section[]>(() => [
  {
    heading: "Controller",
    body: [
      "The data controller for the personal data processed via Vibecell is Lenny David Enderle, contactable at the address and email shown in the Imprint tab. As a sole proprietor below the Art. 37 RGPD threshold (no large-scale special-category processing, no large-scale monitoring of public spaces), no Data Protection Officer is appointed. Privacy enquiries are handled directly by the controller at the contact email.",
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
      "Cookies — one signed httpOnly session cookie (strictly necessary under ePrivacy Art. 5(3); no consent required) + opt-in Google Analytics cookies (only set after you click \"Accept analytics\" on the consent banner; never pre-enabled).",
      "Analytics — Google Analytics 4 with anonymise_ip enabled. Only loaded after explicit opt-in via the consent banner. To revoke: clear localStorage key \"vibecell.consent.analytics\" or click the \"Decline analytics\" button below; both stop further tracking immediately.",
    ],
  },
  {
    heading: "Analytics opt-out",
    body: [
      "Google Analytics is opt-in via the consent banner that appears on your first visit. If you accepted earlier and want to revoke that decision, click below — we'll set the opt-out flag, drop any analytics cookies on your next reload, and never load gtag.js again from this browser.",
    ],
    list: [],
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
    heading: "Cookies + local storage we use",
    body: [
      "The full inventory of state we keep on your device:",
    ],
    list: [
      "hangar (httpOnly, Secure, SameSite=Lax, 30 days) — your signed authentication session. Strictly necessary under ePrivacy Directive Art. 5(3) — set without consent, cannot be disabled while you are signed in.",
      "_ga (host-only, 2 years) — Google Analytics 4 visitor identifier. Set ONLY after you click \"Accept analytics\" on the consent banner. Removed on opt-out.",
      "_ga_WT6LNN2TTG (host-only, 2 years) — Google Analytics 4 session state. Same opt-in gate as _ga.",
      "vibecell.consent.analytics (localStorage, until cleared) — your stored consent decision (granted / denied). UI state only — never sent to any server. Lawful under Art. 6(1)(f) RGPD.",
      "vibecell.theme + vibecell.sidebar.* (localStorage) — UI preferences (dark/light theme, sidebar collapse state). Never leave the browser.",
      "hangar.dashboard.layout.<slug> (localStorage) — your per-project dashboard arrangement. Never leave the browser.",
    ],
  },
  {
    heading: "Sub-processors",
    body: [
      "We use the following processors. Each runs under a Data Processing Agreement (DPA) and the EU Standard Contractual Clauses where applicable. The list reflects the deployment as of the \"Last updated\" date above; we will notify account holders by email at least 14 days before adding any new sub-processor.",
    ],
    list: [
      "Hetzner Online GmbH (Industriestr. 25, 91710 Gunzenhausen, Germany / EU) — primary hosting; all customer data at rest, primary database, application servers.",
      "Stripe Payments Europe Ltd. (1 Grand Canal Street Lower, Dublin 2, Ireland / EU) — subscription billing + payment processing. Card numbers are tokenised by Stripe and never reach our servers.",
      "Cloudflare, Inc. (101 Townsend St., San Francisco, CA 94107, USA, with EU points of presence) — marketing-site CDN + DDoS mitigation under SCCs.",
      "Resend Inc. (Wilmington, DE 19801, USA) — transactional email (sign-in links, billing notices) under SCCs.",
      "Google Ireland Ltd. (Gordon House, Barrow Street, Dublin 4, D04 E5W5, Ireland — entity for EEA Google Analytics) — opt-in usage analytics with anonymise_ip enabled; data flow to Google LLC (US) under SCCs.",
      "Anthropic PBC (548 Market Street, San Francisco, CA 94104, USA) — AI enrichment for opt-in features that summarise your project content. Routed through your own Anthropic key when you set one. SCCs apply.",
      "Functional Software, Inc. d/b/a Sentry (45 Fremont Street, San Francisco, CA 94105, USA) — error monitoring with PII scrubbing enabled (send_default_pii=False).",
      "Backblaze, Inc. (500 Ben Franklin Ct., San Mateo, CA 94401, USA) — encrypted off-site backup of the Postgres dump under SCCs. Data is also held primarily at Hetzner DE.",
    ],
  },
  {
    heading: "Children",
    body: [
      "Vibecell is not directed at minors. The Service is intended for use by persons of full legal capacity (≥ 18 years in most jurisdictions, ≥ 16 years in line with art. 8(1) RGPD where the local age of digital consent is lowered). If you become aware that a minor has created an account, please contact us so we can purge the account.",
    ],
  },
  {
    heading: "Breach notification",
    body: [
      "In the event of a personal-data breach posing risk to your rights and freedoms, we will notify the Comissão Nacional de Proteção de Dados (CNPD) within 72 hours of becoming aware of it (RGPD Art. 33), and notify affected account holders without undue delay where the breach is likely to result in high risk (RGPD Art. 34). We maintain a written breach response procedure internally.",
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
      "You agree not to use the Service, and not to permit any user under your account to use it, to:",
    ],
    list: [
      "Violate any applicable law, regulation, court order, or right of any third party (including intellectual-property, publicity, privacy, or contractual rights).",
      "Upload, store, or transmit data classified as special-category under RGPD Art. 9 (health, biometric, racial, religious, political, sexual, trade-union data) — Vibecell is not designed for those uses and we do not assume the additional safeguards required.",
      "Upload payment-card data (PAN/CVV) outside of Stripe Checkout, or any data subject to PCI DSS, HIPAA, or comparable special regimes.",
      "Attempt to circumvent billing controls, rate limits, plan-gate restrictions, or the read-only-on-lapse mode.",
      "Reverse-engineer, decompile, scrape, stress-test, or probe the Service for vulnerabilities without our prior written permission. Coordinated security disclosure to the contact email is welcome and will not be pursued legally.",
      "Misuse the MCP API to enumerate accounts, exfiltrate other workspaces' data, or amplify attacks against third parties.",
      "Use the Service to generate or store CSAM, terrorist content, malware, phishing infrastructure, or material designed to harass or defame a natural or legal person.",
      "Resell, sub-licence, white-label, or otherwise repackage the Service to third parties without prior written agreement.",
    ],
  },
  {
    heading: "User content + your responsibilities",
    body: [
      "You retain all ownership of the project data, sessions, decisions, ships, ideas, todos, notes, and secrets you upload (\"Your Content\"). You grant us a limited, non-exclusive, worldwide, royalty-free licence to host, process, transmit, display, and back up Your Content for the sole purpose of operating the Service for you. We do not read, train on, or share Your Content beyond that purpose.",
      "You warrant that you own or have the necessary rights to all of Your Content, and that uploading it to Vibecell does not violate any law or third-party right. You are solely responsible for the accuracy, legality, and consequences of Your Content. You shall maintain your own backups for content you cannot tolerate losing — we maintain backups (Backblaze B2) but do not guarantee zero data loss.",
    ],
  },
  {
    heading: "Read-only mode on lapsed subscription",
    body: [
      "When your subscription becomes inactive (canceled, unpaid, or trial expired without a payment method), the Service moves into read-only mode: you keep access to read all your existing data, export it via the GDPR portability endpoint, and delete your account, but cannot create new sessions, decisions, ships, or projects, and MCP write tools return a 402 error until you re-subscribe. Data is preserved while the account exists; subject to the retention schedule in the Privacy notice on account deletion.",
    ],
  },
  {
    heading: "Service availability + \"as-is\"",
    body: [
      "The Service is provided \"AS IS\" and \"AS AVAILABLE\" without warranties of any kind, whether express, implied, or statutory, including without limitation the implied warranties of merchantability, fitness for a particular purpose, title, accuracy of data, or non-infringement, except for warranties that cannot be lawfully excluded. We do not warrant that the Service will be uninterrupted, error-free, or that defects will be corrected. The above limitations apply to the maximum extent permitted by law and do not affect mandatory consumer rights you may have under your local law.",
      "We aim for high availability but do not commit to a formal SLA. We perform planned maintenance with reasonable notice via email and the in-app status banner. Emergency security maintenance may proceed without prior notice. Public component-level health is shown at https://status.vibecell.dev.",
    ],
  },
  {
    heading: "Third-party integrations + AI output disclaimer",
    body: [
      "Vibecell integrates with third-party services that we do not control: Anthropic Claude (via Bring-Your-Own-Key), GitHub, Stripe, the various MCP clients (Claude Code, Claude Desktop, Cursor, Zed, Continue, etc.). The behaviour, output, availability, and pricing of those third-party services are governed by their respective terms — not by us. We are not liable for outages, data loss, billing changes, or output quality on the third-party side.",
      "AI-generated content (resume briefs, retros, plan-todos, primer drafts, launch copy) is produced by the AI provider you have selected. We make no warranty as to its accuracy, completeness, fitness for purpose, or freedom from infringement. You are responsible for reviewing AI output before relying on it for any business or legal decision.",
    ],
  },
  {
    heading: "Beta features",
    body: [
      "Features explicitly marked as \"Beta\", \"Preview\", \"Experimental\", or similar are provided on a best-efforts basis, may change incompatibly, and may be discontinued without notice. Beta features are excluded from the warranty + service-availability commitments above. Use them at your own risk and do not build production dependencies on them.",
    ],
  },
  {
    heading: "Limitation of liability",
    body: [
      "To the maximum extent permitted by applicable law, our total aggregate liability under or in connection with the Service — whether in contract, tort (including negligence), breach of statutory duty, or otherwise — is limited to the GREATER of (a) the amount you paid us in the twelve (12) months preceding the event giving rise to the claim, or (b) one hundred euro (€100). Liability shall not, in any case, exceed five thousand euro (€5,000) per account.",
      "We exclude liability for any indirect, consequential, special, incidental, or punitive damages, including without limitation loss of profits, loss of revenue, loss of business, loss of data, loss of goodwill, or cost of substitute services — even if we have been advised of the possibility of such damages.",
      "Nothing in these terms limits or excludes liability for: (i) death or personal injury caused by negligence; (ii) intentional misconduct or gross negligence; (iii) liability under Art. 6 of DL 67/2003 (consumer-rights regime) where you act as a consumer; (iv) any other liability that cannot be lawfully limited or excluded.",
    ],
  },
  {
    heading: "Indemnification",
    body: [
      "You agree to indemnify, defend, and hold harmless the operator, affiliated developers, and any individual contractors of the Service from and against any third-party claims, damages, losses, costs, and expenses (including reasonable legal fees) arising out of or related to: (a) Your Content, (b) your use of the Service in breach of these Terms or applicable law, (c) your infringement of any third-party right via the Service, or (d) your violation of the Acceptable Use clause. We will notify you of any such claim and cooperate reasonably in your defence at your expense.",
    ],
  },
  {
    heading: "Force majeure",
    body: [
      "Neither party is liable for any delay or failure to perform any obligation under these Terms (other than payment) where the delay or failure results from causes beyond reasonable control, including without limitation acts of God, war, terrorism, riots, embargoes, civil or military authority, fire, flood, accidents, network outages, denial-of-service attacks, electrical or telecommunications failures, or shortages of equipment, materials, or transportation.",
    ],
  },
  {
    heading: "Suspension",
    body: [
      "We reserve the right to suspend access to the Service immediately without notice if (a) we reasonably believe such suspension is necessary to protect the Service or other users from imminent harm (e.g. ongoing attack from your account), (b) we are required to do so by law, court order, or competent authority, or (c) your account is more than 14 days past due. Suspension does not waive amounts due. We will inform you of the reason for suspension as soon as it is operationally reasonable.",
    ],
  },
  {
    heading: "Termination",
    body: [
      "You may terminate by deleting your account at any time at /settings/account → Danger zone. We may terminate your account on 14 days' notice for convenience, or immediately if you breach these Terms materially, fail to pay for two consecutive billing cycles, or we are required to do so by law. Sections that by their nature should survive termination (User Content, Limitation of Liability, Indemnification, Governing Law, Tax retention) survive.",
    ],
  },
  {
    heading: "Assignment",
    body: [
      "You may not assign these Terms or transfer your account to another person without our prior written consent. We may assign these Terms in connection with a merger, acquisition, or sale of substantially all assets of the Service, or to an affiliate, by giving you 30 days' written notice. You may terminate within those 30 days if you do not consent to the assignment.",
    ],
  },
  {
    heading: "Notices",
    body: [
      "Notices to you are valid when sent to the email address on file for your account. Notices to us are valid when sent to the email shown in the Imprint tab. We may also publish service-wide notices via the in-app banner or the public status page.",
    ],
  },
  {
    heading: "Severability + entire agreement + no waiver",
    body: [
      "If any provision of these Terms is held unenforceable, that provision will be modified to the minimum extent necessary to make it enforceable, and the rest of the Terms will remain in effect. These Terms together with the Privacy notice and Pricing page constitute the entire agreement between you and us regarding the Service, and supersede any prior or contemporaneous understanding. Failure to enforce any right under these Terms is not a waiver of that right.",
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
    <MarketingHeader />

    <!-- Hero — pt-[88px] floor compensates for the fixed header overlay. -->
    <section class="max-w-3xl mx-auto px-4 sm:px-6 pt-[88px] sm:pt-[104px] pb-8 sm:pb-10 text-center">
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
        <!-- Inline opt-out button when the privacy "Analytics opt-out"
             section renders. Single-purpose UI affordance for the
             revocation right we promised in the body above. -->
        <button
          v-if="activeTab === 'privacy' && s.heading === 'Analytics opt-out'"
          type="button"
          class="mt-3 px-4 py-2 rounded-md font-mono text-small transition-colors hover:opacity-90"
          style="background: rgba(255,107,107,0.1); color: #ff7e6c; border: 1px solid rgba(255,126,108,0.4)"
          @click="revokeAnalytics"
        >Decline analytics</button>
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
