import { createPinia, setActivePinia } from "pinia";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useOnboardingStore, type OnboardingEvent } from "../onboarding";

/**
 * Minimal EventSource stand-in. jsdom has none, and the point of these tests
 * is the store's reduction of a frame sequence — not the browser's transport.
 */
class FakeEventSource {
  static instances: FakeEventSource[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((e: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  closed = false;

  constructor(public url: string) {
    FakeEventSource.instances.push(this);
  }
  close() {
    this.closed = true;
  }
  emit(event: Partial<OnboardingEvent>) {
    this.onmessage?.({ data: JSON.stringify(event) });
  }
}

function install() {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  const store = useOnboardingStore();
  store.open();
  return { store, es: FakeEventSource.instances[0]! };
}

describe("onboarding store", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.useFakeTimers();
  });

  afterEach(() => {
    // A reissue timer scheduled by one test would otherwise fire inside the
    // next one — against that test's fetch spy, on the previous test's store.
    // Cost me a confusing "expected 1, got 2" before it was pinned down.
    vi.clearAllTimers();
    vi.unstubAllGlobals();
  });

  it("opens the user-scoped stream with credentials", () => {
    const { es } = install();
    expect(es.url).toBe("/api/v1/onboarding/stream");
  });

  it("marks connected on open", () => {
    const { store, es } = install();
    expect(store.connected).toBe(false);
    es.onopen?.();
    expect(store.connected).toBe(true);
  });

  it("keeps frames in arrival order", () => {
    const { store, es } = install();
    es.emit({ type: "paired", client: "claude-code" });
    es.emit({ type: "scan.started", repo_count: 14 });
    expect(store.events.map((e) => e.type)).toEqual(["paired", "scan.started"]);
  });

  it("ignores a malformed frame instead of breaking the log", () => {
    const { store, es } = install();
    es.emit({ type: "paired" });
    es.onmessage?.({ data: "{not json" });
    es.emit({ type: "done", project_count: 1 });
    expect(store.events).toHaveLength(2);
  });

  it("derives paired, repoCount and the final count", () => {
    const { store, es } = install();
    expect(store.paired).toBe(false);
    es.emit({ type: "paired", client: "cursor" });
    es.emit({ type: "scan.started", repo_count: 14 });
    es.emit({ type: "done", project_count: 12 });
    expect(store.paired).toBe(true);
    expect(store.repoCount).toBe(14);
    expect(store.done).toBe(true);
    expect(store.finalProjectCount).toBe(12);
  });

  it("collapses repeated client reports to the latest per client", () => {
    const { store, es } = install();
    es.emit({ type: "client.configured", client: "zed", ok: false, reason: "not found" });
    es.emit({ type: "client.configured", client: "claude-code", ok: true });
    es.emit({ type: "client.configured", client: "zed", ok: true });
    expect(store.clients).toEqual([
      { client: "zed", ok: true, reason: undefined },
      { client: "claude-code", ok: true, reason: undefined },
    ]);
  });

  it("flips a project to enriched without duplicating it", () => {
    const { store, es } = install();
    es.emit({ type: "project.created", slug: "butlr", name: "Butlr" });
    es.emit({ type: "project.created", slug: "giftmakr", name: "Giftmakr" });
    es.emit({ type: "project.enriched", slug: "butlr", pitch: "Agent VMs" });

    expect(store.projects).toEqual([
      { slug: "butlr", name: "Butlr", enriched: true, pitch: "Agent VMs" },
      { slug: "giftmakr", name: "Giftmakr", enriched: false, pitch: undefined },
    ]);
  });

  it("survives a replayed frame after reconnect", () => {
    const { store, es } = install();
    es.emit({ type: "project.created", slug: "butlr", name: "Butlr" });
    es.emit({ type: "project.created", slug: "butlr", name: "Butlr" });
    expect(store.projects).toHaveLength(1);
  });

  it("reconnects with backoff after an error", () => {
    const { es } = install();
    es.onerror?.();
    expect(FakeEventSource.instances).toHaveLength(1);
    vi.advanceTimersByTime(2_000);
    expect(FakeEventSource.instances).toHaveLength(2);
  });

  it("stops reconnecting once done — nothing left to say", () => {
    const { es } = install();
    es.emit({ type: "done", project_count: 3 });
    es.onerror?.();
    vi.advanceTimersByTime(60_000);
    expect(FakeEventSource.instances).toHaveLength(1);
  });

  it("mints a pairing code and re-mints before it expires", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({
        code: "AB12CD34",
        expires_in: 600,
        install_sh: "curl -LsSf https://vibecell.dev/i/AB12CD34 | sh",
        install_ps1: "irm https://vibecell.dev/i/AB12CD34 | iex",
      }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { store } = install();

    await store.mintCode();
    expect(store.pairing?.code).toBe("AB12CD34");
    expect(fetchMock).toHaveBeenCalledTimes(1);

    // 80% of 600s. A dead line on screen looks like a broken product, so the
    // refresh has to land comfortably before expiry.
    await vi.advanceTimersByTimeAsync(480_000);
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("stops re-minting once the machine is paired", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ code: "AB12CD34", expires_in: 600, install_sh: "", install_ps1: "" }),
    });
    vi.stubGlobal("fetch", fetchMock);
    const { store, es } = install();

    es.emit({ type: "paired", client: "claude-code" });
    await store.mintCode();

    await vi.advanceTimersByTimeAsync(600_000);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("keeps the last code when a mint fails", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        json: async () => ({ code: "GOOD1111", expires_in: 600, install_sh: "", install_ps1: "" }),
      })
      .mockRejectedValueOnce(new Error("offline"));
    vi.stubGlobal("fetch", fetchMock);
    const { store } = install();

    await store.mintCode();
    await store.mintCode();
    expect(store.pairing?.code).toBe("GOOD1111");
  });

  it("reset clears frames and closes the connection", () => {
    const { store, es } = install();
    es.emit({ type: "paired", client: "cursor" });
    store.reset();
    expect(store.events).toHaveLength(0);
    expect(es.closed).toBe(true);
    expect(store.connected).toBe(false);
  });
});
