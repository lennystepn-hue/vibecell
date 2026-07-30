<script setup lang="ts">
/**
 * Public landing page — a composition of section components.
 *
 * It was 979 lines in one file: eleven sections, five unrelated data arrays,
 * a count-up animation and a fetch, all sharing a 200-line preamble. Editing
 * the pricing teaser meant scrolling past the MCP catalogue, and 138 of the
 * repo's hardcoded colour literals lived here — the most important page in
 * the product was also the least maintainable.
 *
 * Each section now owns its own markup and its own data. `mcpGroups` belongs
 * to the MCP catalogue, not to a preamble shared by ten sections that never
 * mention it.
 */
import MarketingHeader from "@/components/marketing/MarketingHeader.vue";

import DashboardPreviewSection from "@/components/landing/sections/DashboardPreviewSection.vue";
import FinalCtaSection from "@/components/landing/sections/FinalCtaSection.vue";
import HeroSection from "@/components/landing/sections/HeroSection.vue";
import HowItWorksSection from "@/components/landing/sections/HowItWorksSection.vue";
import LandingFooter from "@/components/landing/sections/LandingFooter.vue";
import McpCatalogSection from "@/components/landing/sections/McpCatalogSection.vue";
import OrbShowcaseSection from "@/components/landing/sections/OrbShowcaseSection.vue";
import PricingTeaserSection from "@/components/landing/sections/PricingTeaserSection.vue";
import SessionMockupSection from "@/components/landing/sections/SessionMockupSection.vue";
import StatsStrip from "@/components/landing/sections/StatsStrip.vue";
import WorksWithStrip from "@/components/landing/sections/WorksWithStrip.vue";

import { useRouteMeta } from "@/composables/useMeta";

useRouteMeta({
  title: "Vibecell — AI project management & MCP-native console for shipping devs",
  description:
    "AI-native project console for indie devs. One source of truth per project — todos, sessions, decisions, ships — plugged straight into Claude Code, Cursor, Zed via MCP. €8.99/mo · 7-day trial.",
  canonical: "https://vibecell.dev/",
});
</script>

<template>
  <div class="min-h-screen text-fg-primary overflow-x-hidden" style="background: var(--bg-body-to)">
    <MarketingHeader cta="Get started →" />

    <HeroSection />
    <WorksWithStrip />
    <DashboardPreviewSection />
    <StatsStrip />
    <McpCatalogSection />
    <OrbShowcaseSection />
    <SessionMockupSection />
    <HowItWorksSection />
    <PricingTeaserSection />
    <FinalCtaSection />
    <LandingFooter />
  </div>
</template>

<style scoped>
/* Aurora text — sweeps a wide gradient through the headline to match the
 * conic-gradient on HeroOrb. 18s linear infinite mirrors the orb's
 * aurora-rotate so headline and orb feel like one breathing organism.
 *
 * Lives on the page rather than in HeroSection because `scoped` styles do
 * not cross component boundaries, and the class is applied inside the hero's
 * markup. Moving it would mean unscoping it.
 */
:deep(.aurora-text) {
  background-image: linear-gradient(
    100deg,
    var(--aurora-1) 0%,
    var(--aurora-2) 25%,
    var(--aurora-3) 50%,
    var(--aurora-4) 75%,
    var(--aurora-1) 100%
  );
  background-size: 300% 100%;
  background-position: 0% 50%;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  -webkit-text-fill-color: transparent;
  animation: aurora-shift 18s linear infinite;
  will-change: background-position;
}

@keyframes aurora-shift {
  from { background-position: 0% 50%; }
  to   { background-position: 300% 50%; }
}

/* Reduced-motion users: snapshot the gradient at a calm position. */
@media (prefers-reduced-motion: reduce) {
  :deep(.aurora-text) {
    animation: none;
    background-position: 50% 50%;
  }
}
</style>
