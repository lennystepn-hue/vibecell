import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "index",
      component: () => import("@/pages/IndexRedirect.vue"),
      meta: { anonymous: true },
    },
    // Spec 4 — public pages
    {
      path: "/landing",
      name: "landing",
      component: () => import("@/pages/AnonLanding.vue"),
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

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  // Hydrate on first navigation if we don't have state.
  if (auth.user === null && !auth.loading && to.meta.anonymous !== true) {
    await auth.refresh();
  }
  if (!auth.isAuthed && to.meta.anonymous !== true && to.name !== "index") {
    return { name: "login" };
  }
  return true;
});

export default router;
