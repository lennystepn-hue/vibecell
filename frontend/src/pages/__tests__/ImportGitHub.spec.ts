import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import ImportGitHub from "../ImportGitHub.vue";
import { api } from "@/api/client";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/import/github", name: "import-github", component: ImportGitHub },
      { path: "/p/:slug", name: "pd", component: { template: "<div/>" } },
    ],
  });
}

describe("ImportGitHub", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  it("shows connect CTA when not connected", async () => {
    vi.spyOn(api, "GET").mockImplementation(((path: string) => {
      if (path === "/api/v1/integrations") {
        return Promise.resolve({ data: [], error: undefined, response: {} });
      }
      return Promise.resolve({ data: [], error: undefined, response: {} });
    }) as unknown as typeof api.GET);

    const router = makeRouter();
    await router.push("/import/github");
    await router.isReady();
    const wrapper = mount(ImportGitHub, { global: { plugins: [router] } });
    await flushPromises();
    expect(wrapper.text()).toContain("Connect your GitHub");
  });

  it("shows repo list when connected", async () => {
    vi.spyOn(api, "GET").mockImplementation(((path: string) => {
      if (path === "/api/v1/integrations") {
        return Promise.resolve({
          data: [{ id: "1", kind: "github", connected_at: "2026-01-01T00:00:00Z", config: { login: "lenny" } }],
          error: undefined,
          response: {},
        });
      }
      if (path === "/api/v1/integrations/github/repos") {
        return Promise.resolve({
          data: [{
            owner: "lenny",
            name: "butlr",
            full_name: "lenny/butlr",
            description: "Openclaw",
            private: false,
            default_branch: "main",
            language: "Python",
            license_spdx: "MIT",
            homepage: null,
            clone_url: "https://github.com/lenny/butlr.git",
            pushed_at: "2026-04-18T10:00:00Z",
          }],
          error: undefined,
          response: {},
        });
      }
      if (path === "/api/v1/projects") {
        return Promise.resolve({ data: { items: [], next_cursor: null }, error: undefined, response: {} });
      }
      return Promise.resolve({ data: [], error: undefined, response: {} });
    }) as unknown as typeof api.GET);

    const router = makeRouter();
    await router.push("/import/github");
    await router.isReady();
    const wrapper = mount(ImportGitHub, { global: { plugins: [router] } });
    await flushPromises();
    await flushPromises();
    const text = wrapper.text();
    expect(text).toContain("lenny/butlr");
    expect(text).toContain("connected as");
    expect(text.toLowerCase()).toContain("lenny");
  });
});
