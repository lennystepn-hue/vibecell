import { afterEach, describe, expect, it, vi } from "vitest";
import { flushPromises, mount } from "@vue/test-utils";

import ProjectAlertBar from "../ProjectAlertBar.vue";

function stubHealth(status: string | null) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue({
      ok: true,
      json: async () => (status ? { last_status: status } : {}),
    }),
  );
}

async function mountBar(context: Record<string, unknown>, health: string | null = "up") {
  stubHealth(health);
  const w = mount(ProjectAlertBar, { props: { project: { slug: "butlr", context } } });
  await flushPromises();
  return w;
}

describe("ProjectAlertBar", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders nothing when nothing is stopping work", async () => {
    const w = await mountBar({});
    expect(w.find("section").exists()).toBe(false);
    expect(w.text()).toBe("");
  });

  it("stays silent for known issues and open questions", async () => {
    // The regression this exists to prevent. A project can carry five known
    // issues for months and be perfectly healthy; showing them as an alarm
    // teaches the user to ignore the bar, and then a real outage looks
    // identical to background noise.
    const w = await mountBar({
      known_issues: ["a", "b", "c", "d", "e"],
      open_questions: ["x", "y"],
    });
    expect(w.find("section").exists()).toBe(false);
  });

  it("surfaces a blocker", async () => {
    const w = await mountBar({ blocked_by: "waiting on Stripe review" });
    expect(w.text()).toContain("Blocked — waiting on Stripe review");
  });

  it("ignores a blocker that is only whitespace", async () => {
    const w = await mountBar({ blocked_by: "   " });
    expect(w.find("section").exists()).toBe(false);
  });

  it("reports a down live URL", async () => {
    const w = await mountBar({}, "down");
    expect(w.text()).toContain("Live URL is down");
  });

  it("distinguishes an erroring healthcheck from a down one", async () => {
    const w = await mountBar({}, "error");
    expect(w.text()).toContain("Healthcheck is erroring");
  });

  it("stays quiet while healthy", async () => {
    const w = await mountBar({}, "up");
    expect(w.find("section").exists()).toBe(false);
  });

  it("puts the blocker first — nothing can move at all", async () => {
    const w = await mountBar({ blocked_by: "legal review" }, "down");
    const rows = w.findAll("li").map((li) => li.text());
    expect(rows[0]).toContain("Blocked");
    expect(rows[1]).toContain("down");
  });

  it("survives a project with no context at all", async () => {
    stubHealth("up");
    const w = mount(ProjectAlertBar, { props: { project: { slug: "x", context: null } } });
    await flushPromises();
    expect(w.find("section").exists()).toBe(false);
  });

  it("stays quiet when the health request fails", async () => {
    // Offline must not invent an outage.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const w = mount(ProjectAlertBar, { props: { project: { slug: "x", context: {} } } });
    await flushPromises();
    expect(w.find("section").exists()).toBe(false);
  });
});
