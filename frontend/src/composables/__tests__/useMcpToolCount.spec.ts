import { afterEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import { flushPromises, mount } from "@vue/test-utils";

import { useMcpToolCount } from "../useMcpToolCount";

/** onMounted only runs inside a component, so give the composable a host. */
function host() {
  return mount(
    defineComponent({
      setup: () => useMcpToolCount(),
      template: "<i>{{ count }}</i>",
    }),
  );
}

function stubStatus(body: unknown, ok = true) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({ ok, json: async () => body }),
  );
}

describe("useMcpToolCount", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("reads the count out of the MCP component message", async () => {
    stubStatus({
      components: [
        { name: "Database", message: null },
        { name: "MCP", message: "50 tools registered" },
      ],
    });
    const w = host();
    await flushPromises();
    expect(w.vm.count).toBe(50);
    expect(w.vm.live).toBe(true);
  });

  it("keeps the fallback when the API is unreachable", async () => {
    // A marketing page has to render when the backend is down. A slightly
    // stale number beats an empty one.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const w = host();
    await flushPromises();
    expect(w.vm.count).toBe(50);
    expect(w.vm.live).toBe(false);
  });

  it("keeps the fallback on a non-ok response", async () => {
    stubStatus({}, false);
    const w = host();
    await flushPromises();
    expect(w.vm.live).toBe(false);
  });

  it("keeps the fallback when no component reports a count", async () => {
    stubStatus({ components: [{ name: "MCP", message: "healthy" }] });
    const w = host();
    await flushPromises();
    expect(w.vm.live).toBe(false);
  });

  it("survives a payload with no components at all", async () => {
    stubStatus({ overall: "ok" });
    const w = host();
    await flushPromises();
    expect(w.vm.count).toBe(50);
  });

  it("handles singular phrasing", async () => {
    stubStatus({ components: [{ name: "MCP", message: "1 tool registered" }] });
    const w = host();
    await flushPromises();
    expect(w.vm.count).toBe(1);
  });
});
