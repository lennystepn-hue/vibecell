import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";

import Welcome from "../Welcome.vue";
import { useAuthStore } from "@/stores/auth";
import { useOnboardingStore } from "@/stores/onboarding";

/** jsdom has no EventSource; the screen only needs it not to explode. */
class FakeEventSource {
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {}
  close() {}
}

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/welcome", name: "welcome", component: Welcome },
      { path: "/p", name: "projects", component: { template: "<div/>" } },
      { path: "/p/:slug", name: "project", component: { template: "<div/>" } },
      { path: "/login", name: "login", component: { template: "<div/>" } },
    ],
  });
}

async function mountWelcome(ua: string) {
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("navigator", {
    userAgent: ua,
    clipboard: { writeText: vi.fn().mockResolvedValue(undefined) },
  });
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        code: "AB12CD34",
        expires_in: 600,
        install_sh: "curl -LsSf https://vibecell.dev/i/AB12CD34 | sh",
        install_ps1: "irm https://vibecell.dev/i/AB12CD34 | iex",
      }),
    }),
  );

  const auth = useAuthStore();
  auth.$patch({ user: { id: "u1", email: "a@b.c" } as never });

  const router = makeRouter();
  await router.push("/welcome");
  await router.isReady();
  const wrapper = mount(Welcome, { global: { plugins: [router] } });
  await flushPromises();
  return wrapper;
}

describe("Welcome (onboarding screen)", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers({ shouldAdvanceTime: true });
  });

  afterEach(() => {
    vi.clearAllTimers();
    vi.unstubAllGlobals();
  });

  it("shows the shell one-liner on macOS", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)");
    expect(w.text()).toContain("curl -LsSf https://vibecell.dev/i/AB12CD34 | sh");
    expect(w.text()).toContain("Terminal");
  });

  it("shows the PowerShell one-liner on Windows", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Windows NT 10.0; Win64; x64)");
    expect(w.text()).toContain("irm https://vibecell.dev/i/AB12CD34 | iex");
    expect(w.text()).toContain("PowerShell");
  });

  it("offers exactly one primary action, not six editor tabs", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Macintosh)");
    // The old wizard rendered a tab per editor. Picking from six is a
    // decision a brand-new user cannot make.
    for (const editor of ["Cursor", "Zed", "Windsurf"]) {
      expect(w.text()).not.toContain(editor);
    }
  });

  it("says nothing has happened before the line is run", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Macintosh)");
    expect(w.text()).toContain("Nothing happens here until you paste it");
  });

  it("renders live progress from stream events", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Macintosh)");
    const store = useOnboardingStore();

    store.events.push({ type: "paired", user_id: "u1", at: "", client: "cli" });
    store.events.push({
      type: "client.configured",
      user_id: "u1",
      at: "",
      client: "cursor",
      ok: true,
    });
    store.events.push({ type: "scan.started", user_id: "u1", at: "", repo_count: 14 });
    store.events.push({
      type: "project.created",
      user_id: "u1",
      at: "",
      slug: "butlr",
      name: "Butlr",
    });
    await w.vm.$nextTick();

    expect(w.text()).toContain("device paired");
    expect(w.text()).toContain("cursor configured");
    expect(w.text()).toContain("14 repositories found");
    expect(w.text()).toContain("reading Butlr…");
  });

  it("flips a project from reading to enriched", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Macintosh)");
    const store = useOnboardingStore();
    store.events.push({
      type: "project.created",
      user_id: "u1",
      at: "",
      slug: "butlr",
      name: "Butlr",
    });
    store.events.push({
      type: "project.enriched",
      user_id: "u1",
      at: "",
      slug: "butlr",
      pitch: "Agent VMs on demand",
    });
    await w.vm.$nextTick();

    expect(w.text()).toContain("Butlr — Agent VMs on demand");
    expect(w.text()).not.toContain("reading Butlr…");
  });

  it("reports a client that was not found without calling it a failure", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Macintosh)");
    const store = useOnboardingStore();
    store.events.push({
      type: "client.configured",
      user_id: "u1",
      at: "",
      client: "zed",
      ok: false,
      reason: "not found",
    });
    await w.vm.$nextTick();
    expect(w.text()).toContain("zed — not found");
  });

  it("surfaces done with the count", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Macintosh)");
    const store = useOnboardingStore();
    store.events.push({ type: "done", user_id: "u1", at: "", project_count: 12 });
    await w.vm.$nextTick();
    expect(w.text()).toContain("12 projects are in");
  });

  it("falls through when a deep link finds no protocol handler", async () => {
    // The load-bearing claim of the secondary path. A browser cannot ask "is
    // Claude Desktop installed?" — losing focus is the only available signal,
    // so its absence has to be turned into a message rather than silence.
    const w = await mountWelcome("Mozilla/5.0 (Macintosh)");
    // jsdom refuses to navigate to an unknown protocol; the handler only
    // needs the click to start the timer.
    delete (window as { location?: unknown }).location;
    (window as { location: unknown }).location = { href: "" };

    const buttons = w.findAll("button");
    const deepLinkBtn = buttons.find((b) => b.text().includes("Claude Desktop"));
    expect(deepLinkBtn).toBeTruthy();
    await deepLinkBtn!.trigger("click");

    expect(w.text()).not.toContain("didn't respond");
    vi.advanceTimersByTime(1600);
    await w.vm.$nextTick();
    expect(w.text()).toContain("Claude Desktop didn't respond");
  });

  it("keeps a manual escape hatch for editors we do not automate", async () => {
    const w = await mountWelcome("Mozilla/5.0 (Macintosh)");
    const manual = w.findAll("button").find((b) => b.text().includes("Different editor"));
    expect(manual).toBeTruthy();
    await manual!.trigger("click");
    expect(w.text()).toContain("https://vibecell.dev/mcp");
  });
});
