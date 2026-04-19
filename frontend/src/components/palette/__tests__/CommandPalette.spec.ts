import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import CommandPalette from "../CommandPalette.vue";
import { useCommandPaletteStore } from "@/stores/command-palette";
import { useProjectsStore } from "@/stores/projects";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/p/:slug", name: "project-detail", component: { template: "<div/>" } },
      { path: "/p/new", name: "p-new", component: { template: "<div/>" } },
      { path: "/import/github", name: "import", component: { template: "<div/>" } },
      { path: "/settings", name: "settings", component: { template: "<div/>" } },
    ],
  });
}

function stubProjectsStore(ps = useProjectsStore()) {
  // Prevent unhandled fetch rejections from the palette's open-watcher (no
  // real server in tests; explicit seed() drives what's listed).
  vi.spyOn(ps, "fetchList").mockResolvedValue();
  vi.spyOn(ps, "switchTo").mockResolvedValue(true);
  return ps;
}

function seed(ps = useProjectsStore()) {
  ps.list = [
    { id: "1", slug: "butlr", name: "Butlr", emoji: "🛎️", color: null, pitch: null, status: "building", group_id: null, position: 0 },
    { id: "2", slug: "zapline", name: "Zapline", emoji: "⚡", color: null, pitch: null, status: "live", group_id: null, position: 1 },
  ];
  stubProjectsStore(ps);
}

describe("CommandPalette", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("is hidden by default, visible when store.open=true", async () => {
    stubProjectsStore();
    const wrapper = mount(CommandPalette, { global: { plugins: [makeRouter()] } });
    const cp = useCommandPaletteStore();
    expect(wrapper.find("input").exists()).toBe(false);
    cp.show();
    await flushPromises();
    expect(wrapper.find("input").exists()).toBe(true);
  });

  it("lists projects and actions when open", async () => {
    const ps = useProjectsStore();
    seed(ps);
    const wrapper = mount(CommandPalette, { global: { plugins: [makeRouter()] } });
    const cp = useCommandPaletteStore();
    cp.show();
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain("projects");
    expect(text).toContain("butlr");
    expect(text).toContain("zapline");
    expect(text).toContain("actions");
    expect(text).toContain("New project");
  });

  it("filters via fuzzy match on query", async () => {
    const ps = useProjectsStore();
    seed(ps);
    const wrapper = mount(CommandPalette, { global: { plugins: [makeRouter()] } });
    const cp = useCommandPaletteStore();
    cp.show();
    await flushPromises();
    await wrapper.find("input").setValue("zap");
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain("zapline");
    expect(text).not.toContain("butlr");
  });

  it("closes on Escape", async () => {
    stubProjectsStore();
    const wrapper = mount(CommandPalette, { global: { plugins: [makeRouter()] } });
    const cp = useCommandPaletteStore();
    cp.show();
    await flushPromises();
    await wrapper.find("input").trigger("keydown", { key: "Escape" });
    expect(cp.open).toBe(false);
  });
});
