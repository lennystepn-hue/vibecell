// frontend/src/main.ts
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import { bootstrapAnalytics } from "./lib/analytics";
import router from "./router";

import "./assets/base.css";

// Re-attach Google Analytics on hot reload only if the user has previously
// granted consent. First-visit users see no GA traffic until they click
// "Accept analytics" on the consent banner mounted in App.vue.
bootstrapAnalytics(router);

const app = createApp(App);

// Sentry — initialised only if VITE_SENTRY_DSN_FRONTEND is baked into the
// build. Without that env var, the import doesn't even happen, so the bundle
// size stays unchanged for self-hosted setups that don't use Sentry.
if (import.meta.env.VITE_SENTRY_DSN_FRONTEND) {
  import("@sentry/vue")
    .then((Sentry) => {
      Sentry.init({
        app,
        dsn: import.meta.env.VITE_SENTRY_DSN_FRONTEND as string,
        tracesSampleRate: 0.1,
        environment: import.meta.env.MODE,
        release: (import.meta.env.VITE_GIT_SHA as string | undefined) ?? "unknown",
      });
    })
    .catch((e) => {
      // Sentry SDK install missing — log but don't break the app.
      console.warn("Sentry init failed:", e);
    });
}

app.use(createPinia());
app.use(router);
app.mount("#app");
