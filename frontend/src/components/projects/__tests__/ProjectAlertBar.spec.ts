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
  const w = mount(ProjectAlertBar, {
    props: { project: { slug: "butlr", context } },
  });
  await flushPromises();
  return w;
}

describe("ProjectAlertBar", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("renders nothing when the project is fine", async () => {
    // A permanent "all good" banner is chrome, and chrome is what this cuts.
    const w = await mountBar({ known_issues: [], open_questions: [] });
    expect(w.find("section").exists()).toBe(false);
    expect(w.text()).toBe("");
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

  it("counts issues and questions, with singular grammar", async () => {
    const w = await mountBar({ known_issues: ["a"], open_questions: ["x", "y"] });
    expect(w.text()).toContain("1 known issue");
    expect(w.text()).not.toContain("1 known issues");
    expect(w.text()).toContain("2 open questions");
  });

  it("puts what stops work soonest first", async () => {
    // A blocker means nothing on this project can move, so it outranks a
    // dead URL, which outranks a backlog of questions.
    const w = await mountBar(
      { blocked_by: "legal review", known_issues: ["a"], open_questions: ["x"] },
      "down",
    );
    const rows = w.findAll("li").map((li) => li.text());
    expect(rows[0]).toContain("Blocked");
    expect(rows[1]).toContain("down");
    expect(rows[2]).toContain("known issue");
    expect(rows[3]).toContain("open question");
  });

  it("turns critical when anything critical is present", async () => {
    const warn = await mountBar({ open_questions: ["x"] });
    const crit = await mountBar({ blocked_by: "x" });
    expect(warn.find("section").attributes("style")).toContain("--signal-amber");
    expect(crit.find("section").attributes("style")).toContain("--signal-red");
  });

  it("survives a project with no context at all", async () => {
    stubHealth("up");
    const w = mount(ProjectAlertBar, { props: { project: { slug: "x", context: null } } });
    await flushPromises();
    expect(w.find("section").exists()).toBe(false);
  });

  it("stays quiet when the health request fails", async () => {
    // Offline should not invent an outage.
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    const w = mount(ProjectAlertBar, { props: { project: { slug: "x", context: {} } } });
    await flushPromises();
    expect(w.find("section").exists()).toBe(false);
  });
});
