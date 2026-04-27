import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    // Public marketing landing lives at the root so vibecell.dev serves it
    // directly. /landing is kept as an alias for old links/bookmarks.
    {
      path: "/",
      name: "landing",
      component: () => import("@/pages/AnonLanding.vue"),
      alias: "/landing",
      meta: { anonymous: true },
    },
    {
      path: "/pricing",
      name: "pricing",
      component: () => import("@/pages/Pricing.vue"),
      meta: { anonymous: true },
    },
    {
      path: "/legal",
      name: "legal",
      component: () => import("@/pages/Legal.vue"),
      meta: { anonymous: true },
    },
    {
      // Spec-6 C4 — public status page. Anonymous so external uptime monitors
      // can hit it directly. Mirrors /api/v1/status.
      path: "/status",
      name: "status",
      component: () => import("@/pages/Status.vue"),
      meta: { anonymous: true },
    },
    // Spec 5B — Portfolio-Intel
    {
      path: "/portfolio",
      name: "portfolio",
      component: () => import("@/pages/Portfolio.vue"),
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/Login.vue"),
      meta: { anonymous: true },
    },
    {
      path: "/auth/verify",
      name: "auth-verify",
      component: () => import("@/pages/AuthVerify.vue"),
      meta: { anonymous: true },
    },
    {
      path: "/auth/change-email/:token",
      name: "auth-change-email-confirm",
      component: () => import("@/pages/AuthChangeEmailConfirm.vue"),
      // Anonymous-allowed: user might click the link in a different browser
      // than they're signed in on; the token itself is the proof.
      meta: { anonymous: true },
    },
    {
      path: "/settings/billing",
      name: "settings-billing",
      component: () => import("@/pages/SettingsBilling.vue"),
    },
    {
      // Spec-6 C3 — onboarding wizard. ProjectsIndex auto-redirects new users
      // here when their dashboard is empty AND localStorage hasn't seen the
      // completion flag yet. Direct hits (eg. /welcome bookmark) just render.
      path: "/welcome",
      name: "welcome",
      component: () => import("@/pages/Welcome.vue"),
    },
    {
      path: "/p",
      name: "projects-index",
      component: () => import("@/pages/ProjectsIndex.vue"),
    },
    {
      path: "/p/:slug",
      name: "project-detail",
      component: () => import("@/pages/ProjectDetail.vue"),
    },
    {
      path: "/p/:slug/sessions/:id",
      name: "session-detail",
      component: () => import("@/pages/SessionDetail.vue"),
    },
    {
      path: "/p/:slug/decisions/:id",
      name: "decision-detail",
      component: () => import("@/pages/DecisionDetail.vue"),
    },
    {
      path: "/import/github",
      name: "import-github",
      component: () => import("@/pages/ImportGitHub.vue"),
    },
    {
      path: "/ideas",
      name: "ideas",
      component: () => import("@/pages/Ideas.vue"),
    },
    {
      path: "/search",
      name: "search",
      component: () => import("@/pages/Search.vue"),
    },
    {
      path: "/settings",
      name: "settings",
      component: () => import("@/pages/Settings.vue"),
    },
    {
      path: "/settings/integrations",
      name: "settings-integrations",
      component: () => import("@/pages/SettingsIntegrations.vue"),
    },
    {
      path: "/settings/connections",
      name: "settings-connections",
      component: () => import("@/pages/Connections.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/cli/pair",
      name: "cli-pair",
      component: () => import("@/pages/CliPair.vue"),
    },
    {
      path: "/oauth/consent",
      name: "oauth-consent",
      component: () => import("@/pages/OAuthConsent.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/:catchAll(.*)*",
      name: "not-found",
      component: () => import("@/pages/NotFound.vue"),
    },
  ],
});

// Hydrate on the first navigation of the tab so public routes (landing,
// pricing, legal) can render logged-in UI (avatar, "Open dashboard" CTAs)
// when the session cookie is already valid. Prior to this, a refresh on
// /landing left the auth store empty forever and the page looked anonymous
// even though /api/v1/me would have succeeded.
let _hydrated = false;

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  if (!_hydrated && !auth.loading) {
    _hydrated = true;
    await auth.refresh();
  }
  if (!auth.isAuthed && to.meta.anonymous !== true) {
    return { name: "login", query: { next: to.fullPath } };
  }
  return true;
});

export default router;
