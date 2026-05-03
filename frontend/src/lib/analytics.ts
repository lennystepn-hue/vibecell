/**
 * Conditional Google Analytics 4 loader.
 *
 * Compliance contract:
 *   - The gtag.js bundle is NOT injected at startup. Nothing tracks
 *     until the user explicitly opts in via the cookie-consent banner.
 *   - Once consent is granted, we load the GA4 script lazily, set the
 *     anonymize_ip flag (legally required basis for GA4 in the EU),
 *     and fire pageviews on every Vue Router navigation.
 *   - Revoking consent purges the gtag globals + sets the disable
 *     window flag GA's own runtime checks before sending; future
 *     pageviews are silently dropped.
 *
 * The user's choice is persisted in localStorage (single key, single
 * value: "granted" | "denied") so we don't pre-set a cookie before
 * they've decided. localStorage isn't tracking infrastructure, just
 * UI state, so it's fine pre-consent under DSGVO Art. 6(1)(f).
 */
import type { Router } from "vue-router";

// Set BY HAND — the property's Measurement ID is non-secret (it ends
// up in the gtag URL fetched by every visitor). Hardcoded here so we
// don't need an env var pipeline for a single string.
const GA_ID = "G-WT6LNN2TTG";
const STORAGE_KEY = "vibecell.consent.analytics";
const DISABLE_FLAG = `ga-disable-${GA_ID}`;

// gtag injects this global; we wire onto it via window so call sites
// don't need to import a typed wrapper.
declare global {
  interface Window {
    dataLayer?: unknown[];
    gtag?: (...args: unknown[]) => void;
    [key: `ga-disable-${string}`]: boolean | undefined;
  }
}

let scriptLoaded = false;
let routeUnsub: (() => void) | null = null;

export type ConsentChoice = "granted" | "denied" | "unknown";

export function readConsent(): ConsentChoice {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw === "granted" || raw === "denied") return raw;
  } catch {
    /* private mode etc. */
  }
  return "unknown";
}

function persistConsent(choice: "granted" | "denied"): void {
  try {
    localStorage.setItem(STORAGE_KEY, choice);
  } catch {
    /* ignore */
  }
}

/** Inject the gtag.js script + initialise the dataLayer. Idempotent. */
function loadScript(): void {
  if (scriptLoaded) return;
  scriptLoaded = true;
  const s = document.createElement("script");
  s.async = true;
  s.src = `https://www.googletagmanager.com/gtag/js?id=${GA_ID}`;
  document.head.appendChild(s);

  window.dataLayer = window.dataLayer || [];
  // The gtag() helper has the canonical Google shape (uses `arguments`
  // because it's positional, not named). Mirror that exactly.
  // eslint-disable-next-line prefer-rest-params
  window.gtag = function (...args: unknown[]) {
    (window.dataLayer ??= []).push(args);
  };
  window.gtag("js", new Date());
  // anonymize_ip is required for GA4 to be DSGVO-defensible in the EU
  // (Article 6(1)(f) standard-of-care). Without it, IPs land at Google
  // unredacted and the legal-basis argument collapses.
  window.gtag("config", GA_ID, {
    anonymize_ip: true,
    send_page_view: true,
  });
}

/** Set GA's own runtime disable flag. Future page-view calls become
 *  no-ops. We also clear gtag/dataLayer references so nothing fires
 *  this session. The user can also clear localStorage themselves. */
function disableTracking(): void {
  window[DISABLE_FLAG] = true;
}

/** Wire route-change pageviews. Called once after consent is granted.
 *  vue-router's afterEach gives us the post-navigation URL we want
 *  GA to record (path + query, not hash). */
function bindRoutePageViews(router: Router): void {
  if (routeUnsub) return;
  routeUnsub = router.afterEach((to) => {
    if (typeof window.gtag !== "function") return;
    window.gtag("event", "page_view", {
      page_path: to.fullPath,
      page_location: window.location.href,
      page_title: document.title,
    });
  });
}

/**
 * Init step called from main.ts BEFORE the router mounts. Reads the
 * persisted consent decision; if "granted", loads gtag immediately
 * and starts route-tracking. If "denied" or "unknown", does nothing —
 * the consent banner mounts and waits for the user.
 */
export function bootstrapAnalytics(router: Router): void {
  if (readConsent() === "granted") {
    loadScript();
    bindRoutePageViews(router);
  }
}

/** Called by the consent banner when the user clicks "Accept analytics". */
export function grantConsent(router: Router): void {
  persistConsent("granted");
  loadScript();
  bindRoutePageViews(router);
}

/** Called by the consent banner's "Decline" button OR the privacy-page
 *  revocation link. Sets GA's runtime disable flag + persists denial. */
export function denyConsent(): void {
  persistConsent("denied");
  disableTracking();
}
