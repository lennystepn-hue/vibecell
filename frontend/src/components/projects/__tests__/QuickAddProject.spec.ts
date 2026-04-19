import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import QuickAddProject from "../QuickAddProject.vue";
import { useProjectsStore } from "@/stores/projects";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/p", name: "p", component: { template: "<div/>" } },
      { path: "/p/:slug", name: "pd", component: { template: "<div/>" } },
    ],
  });
}

describe("QuickAddProject", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("renders when open and auto-slugs from name", async () => {
    const wrapper = mount(QuickAddProject, {
      props: { open: true },
      global: { plugins: [makeRouter()] },
    });
    await flushPromises();
    const nameInput = wrapper.find<HTMLInputElement>('input[placeholder="Butlr"]');
    await nameInput.setValue("My Shiny Project");
    // slug should auto-fill
    const slugInput = wrapper.find<HTMLInputElement>('input[placeholder="butlr"]');
    expect(slugInput.element.value).toBe("my-shiny-project");
  });

  it("emits close on cancel", async () => {
    const wrapper = mount(QuickAddProject, {
      props: { open: true },
      global: { plugins: [makeRouter()] },
    });
    await flushPromises();
    const ps = useProjectsStore();
    vi.spyOn(ps, "fetchList").mockResolvedValue();
    const cancel = wrapper.findAll("button").find((b) => b.text() === "Cancel");
    expect(cancel).toBeTruthy();
    await cancel!.trigger("click");
    expect(wrapper.emitted("close")).toBeTruthy();
  });
});
