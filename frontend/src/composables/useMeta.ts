/**
 * Per-route document meta updater. Vue Router doesn't manage <head>
 * out of the box and adding vue-meta / unhead just for this is
 * overkill — pages call useRouteMeta(...) in setup() and we mutate
 * document.title + the relevant meta tags directly.
 *
 * Crawlers worth caring about (Googlebot, Bingbot, ChatGPT-User) all
 * execute JS and pick up the runtime-set tags. Slack / LinkedIn / X
 * pre-render via their own bots that DON'T execute JS — for those
 * the index.html static defaults carry the load (good enough; the
 * static defaults already match the Landing page since that's the
 * highest-traffic share target).
 */
import { onMounted, watch } from "vue";

export interface RouteMeta {
  /** Document title (browser tab + Google search result heading). */
  title: string;
  /** ~150-160 chars; appears as the search-result snippet. */
  description: string;
  /** Canonical URL for this page (absolute, no trailing slash unless root). */
  canonical?: string;
  /** Open Graph image (absolute URL). Falls back to landing screenshot. */
  ogImage?: string;
}

const DEFAULT_OG = "https://vibecell.dev/landing-dashboard.png";

function setOrCreateMeta(selector: string, attr: string, value: string) {
  let el = document.head.querySelector<HTMLMetaElement>(selector);
  if (!el) {
    el = document.createElement("meta");
    const [k, v] = selector.replace(/^meta\[|]$/g, "").split("=");
    if (k && v) el.setAttribute(k, v.replace(/^"|"$/g, ""));
    document.head.appendChild(el);
  }
  el.setAttribute(attr, value);
}

function setLink(rel: string, href: string) {
  let el = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!el) {
    el = document.createElement("link");
    el.setAttribute("rel", rel);
    document.head.appendChild(el);
  }
  el.setAttribute("href", href);
}

export function useRouteMeta(meta: RouteMeta | (() => RouteMeta)) {
  const apply = () => {
    const m = typeof meta === "function" ? meta() : meta;
    document.title = m.title;
    setOrCreateMeta('meta[name="description"]', "content", m.description);
    setOrCreateMeta('meta[property="og:title"]', "content", m.title);
    setOrCreateMeta('meta[property="og:description"]', "content", m.description);
    setOrCreateMeta('meta[name="twitter:title"]', "content", m.title);
    setOrCreateMeta('meta[name="twitter:description"]', "content", m.description);
    if (m.canonical) {
      setLink("canonical", m.canonical);
      setOrCreateMeta('meta[property="og:url"]', "content", m.canonical);
    }
    const og = m.ogImage ?? DEFAULT_OG;
    setOrCreateMeta('meta[property="og:image"]', "content", og);
    setOrCreateMeta('meta[name="twitter:image"]', "content", og);
  };

  onMounted(apply);
  // Re-apply if the page passes a function (computed-style meta) — Vue
  // tracks the dependencies and re-runs on change.
  if (typeof meta === "function") {
    watch(meta, apply, { flush: "post" });
  }
}
