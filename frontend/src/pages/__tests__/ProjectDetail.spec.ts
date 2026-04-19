import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import ProjectDetail from "../ProjectDetail.vue";
import { useProjectsStore } from "@/stores/projects";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];

function fakeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: "01FAKE",
    slug: "butlr",
    name: "Butlr",
    emoji: "🛎️",
    color: null,
    pitch: "OpenClaw-as-a-Service",
    status: "building",
    is_public: 0,
    archived_at: null,
    context: {
      current_focus: "Stripe webhook",
      next_step: "Handle subscription.deleted",
      user_wants: null,
      open_questions: [],
      known_issues: [],
      blocked_by: null,
    },
    infra: null,
    repos: [],
    environments: [],
    links: [],
    commands: [],
    stack: [],
    tags: [],
    ...overrides,
  };
}

describe("ProjectDetail", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  async function mountAt(slug: string, preload?: Project) {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/p", name: "projects-index", component: { template: "<div/>" } },
        { path: "/p/:slug", name: "project-detail", component: ProjectDetail },
      ],
    });
    const store = useProjectsStore();
    // Prevent unhandled fetch rejections from the component's onMounted/watch hooks
    // (no real server in tests; preload drives what's rendered).
    vi.spyOn(store, "fetchProject").mockResolvedValue(undefined);
    vi.spyOn(store, "fetchList").mockResolvedValue(undefined);
    if (preload) {
      store.active = preload;
    }
    await router.push(`/p/${slug}`);
    await router.isReady();
    const wrapper = mount(ProjectDetail, { global: { plugins: [router] } });
    await flushPromises();
    return { wrapper, store, router };
  }

  it("renders name, pitch, and status pill from active project", async () => {
    const { wrapper } = await mountAt("butlr", fakeProject());
    expect(wrapper.text()).toContain("Butlr");
    expect(wrapper.text()).toContain("OpenClaw-as-a-Service");
    expect(wrapper.text()).toContain("building");
  });

  it("renders current focus and next step", async () => {
    const { wrapper } = await mountAt("butlr", fakeProject());
    expect(wrapper.text()).toContain("current focus");
    expect(wrapper.text()).toContain("Stripe webhook");
    expect(wrapper.text()).toContain("Handle subscription.deleted");
  });

  it("shows blocked banner when blocked_by is set", async () => {
    const { wrapper } = await mountAt(
      "butlr",
      fakeProject({
        context: {
          current_focus: "f",
          next_step: null,
          user_wants: null,
          open_questions: [],
          known_issues: [],
          blocked_by: "Waiting on Stripe API access",
        },
      }),
    );
    expect(wrapper.text().toLowerCase()).toContain("blocked");
    expect(wrapper.text()).toContain("Waiting on Stripe API access");
  });

  it("shows 'Project not found' when store.active stays null", async () => {
    const { wrapper, store } = await mountAt("nonexistent");
    store.active = null;
    await flushPromises();
    expect(wrapper.text()).toContain("Project not found");
  });
});
