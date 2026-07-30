import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

import ConnectModal from "../ConnectModal.vue";
import { useOnboardingStore } from "@/stores/onboarding";

class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  close() {}
}

function stubEnv() {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.stubGlobal("navigator", {
    userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)",
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
}

async function mountModal(open = true) {
  stubEnv();
  const wrapper = mount(ConnectModal, {
    props: { open },
    global: { stubs: { Teleport: true } },
  });
  await flushPromises();
  return wrapper;
}

describe("ConnectModal", () => {
  beforeEach(() => setActivePinia(createPinia()));
  afterEach(() => {
    vi.clearAllTimers();
    vi.unstubAllGlobals();
  });

  it("shows the same one-liner the welcome screen shows", async () => {
    // The point of #29: an existing account reaches this dialog, a brand-new
    // one reaches /welcome, and both must get the current setup path.
    const w = await mountModal();
    expect(w.text()).toContain("curl -LsSf https://vibecell.dev/i/AB12CD34 | sh");
  });

  it("no longer offers six editor tabs", async () => {
    // The old modal listed Claude Desktop / Claude Code / Cursor / Zed /
    // Windsurf / Paste-into-AI and asked a brand-new user to choose. It
    // survived the rewrite of /welcome because it was a second copy; this
    // assertion is what stops that happening again.
    const w = await mountModal();
    for (const tab of ["Claude Code", "Cursor", "Zed", "Windsurf", "Paste into AI"]) {
      expect(w.text()).not.toContain(tab);
    }
  });

  it("mints a pairing code when opened", async () => {
    await mountModal();
    expect(fetch).toHaveBeenCalledWith(
      "/api/v1/onboarding/code",
      expect.objectContaining({ method: "POST" }),
    );
  });

  it("opens the progress stream when opened", async () => {
    await mountModal();
    expect(FakeEventSource.instances[0]?.url).toBe("/api/v1/onboarding/stream");
  });

  it("does not open a stream while closed", async () => {
    await mountModal(false);
    expect(FakeEventSource.instances).toHaveLength(0);
    expect(fetch).not.toHaveBeenCalled();
  });

  it("renders live progress, like the page does", async () => {
    const w = await mountModal();
    const store = useOnboardingStore();
    store.events.push({ type: "paired", user_id: "u1", at: "", client: "cli" });
    store.events.push({
      type: "client.configured",
      user_id: "u1",
      at: "",
      client: "cursor",
      ok: true,
    });
    await w.vm.$nextTick();
    expect(w.text()).toContain("device paired");
    expect(w.text()).toContain("cursor configured");
  });
});
