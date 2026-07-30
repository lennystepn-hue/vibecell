import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";
import { createMemoryHistory, createRouter } from "vue-router";

import SetupSummary from "../SetupSummary.vue";
import { useOnboardingStore, type OnboardingEvent } from "@/stores/onboarding";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    // A root route matters: `isReady()` on a memory history that has never
    // resolved a location never settles, and the whole file times out.
    routes: [
      { path: "/", component: { template: "<div/>" } },
      { path: "/p/:slug", component: { template: "<div/>" } },
    ],
  });
}

async function mountSummary(events: Partial<OnboardingEvent>[]) {
  const store = useOnboardingStore();
  for (const e of events) {
    store.events.push({ user_id: "u1", at: "", ...e } as OnboardingEvent);
  }
  const router = makeRouter();
  await router.push("/");
  await router.isReady();
  return mount(SetupSummary, { global: { plugins: [router] } });
}

const created = (slug: string, name: string) => ({ type: "project.created" as const, slug, name });
const enriched = (slug: string, pitch: string) => ({ type: "project.enriched" as const, slug, pitch });

describe("SetupSummary", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("says what was produced", async () => {
    const w = await mountSummary([
      created("butlr", "Butlr"),
      enriched("butlr", "Agent VMs"),
      { type: "done", project_count: 12 },
    ]);
    expect(w.text()).toContain("12 projects are in");
    expect(w.text()).toContain("You typed nothing");
  });

  it("uses singular grammar for one project", async () => {
    const w = await mountSummary([
      created("butlr", "Butlr"),
      enriched("butlr", "Agent VMs"),
      { type: "done", project_count: 1 },
    ]);
    expect(w.text()).toContain("1 project is in");
  });

  it("names the projects Claude could not describe", async () => {
    // The useful half: a project created but never enriched is an empty
    // shell the user should see now rather than discover cold in three weeks.
    const w = await mountSummary([
      created("butlr", "Butlr"),
      enriched("butlr", "Agent VMs"),
      created("mystery", "Mystery Repo"),
      { type: "done", project_count: 2 },
    ]);
    expect(w.text()).toContain("1 of them Claude couldn't read");
    expect(w.text()).toContain("Mystery Repo");
    expect(w.text()).not.toContain("Butlr —");
  });

  it("says so plainly when everything was readable", async () => {
    const w = await mountSummary([
      created("butlr", "Butlr"),
      enriched("butlr", "Agent VMs"),
      { type: "done", project_count: 1 },
    ]);
    expect(w.text()).toContain("read every one of them");
  });

  it("points at the first project Claude actually understood", async () => {
    // Opening into the one repo it couldn't read would be a poor first move.
    const w = await mountSummary([
      created("mystery", "Mystery Repo"),
      created("butlr", "Butlr"),
      enriched("butlr", "Agent VMs"),
      { type: "done", project_count: 2 },
    ]);
    expect(w.text()).toContain("Open Butlr →");
  });

  it("handles finding nothing without calling it success", async () => {
    // Plenty of people set up a machine before putting code on it. Saying
    // "done" here would be a lie the user discovers later.
    const w = await mountSummary([{ type: "done", project_count: 0 }]);
    expect(w.text()).toContain("No repositories found");
    expect(w.text()).toContain("Nothing went wrong");
    expect(w.text()).not.toContain("You typed nothing");
  });

  it("falls back to the event count when done carries none", async () => {
    const w = await mountSummary([
      created("butlr", "Butlr"),
      enriched("butlr", "x"),
      { type: "done" },
    ]);
    expect(w.text()).toContain("1 project is in");
  });

  it("emits finish when the button is pressed", async () => {
    const w = await mountSummary([
      created("butlr", "Butlr"),
      enriched("butlr", "x"),
      { type: "done", project_count: 1 },
    ]);
    await w.find("button").trigger("click");
    expect(w.emitted("finish")).toHaveLength(1);
  });
});
