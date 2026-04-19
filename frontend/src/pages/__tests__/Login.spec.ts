import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import Login from "../Login.vue";
import { useAuthStore } from "@/stores/auth";

describe("Login page", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  function makeRouter() {
    return createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/", name: "index", component: { template: "<div/>" } },
        { path: "/login", name: "login", component: Login },
      ],
    });
  }

  it("shows the email form initially", async () => {
    const router = makeRouter();
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(Login, { global: { plugins: [router] } });
    expect(wrapper.text()).toContain("Sign in");
    expect(wrapper.find("input[type=email]").exists()).toBe(true);
  });

  it("rejects malformed email client-side", async () => {
    const router = makeRouter();
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(Login, { global: { plugins: [router] } });
    const input = wrapper.find("input[type=email]");
    await input.setValue("not-an-email");
    await wrapper.find("form").trigger("submit.prevent");
    expect(wrapper.text()).toContain("doesn't look like an email");
  });

  it("shows the sent-confirmation after a successful request", async () => {
    const router = makeRouter();
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(Login, { global: { plugins: [router] } });
    const auth = useAuthStore();
    vi.spyOn(auth, "requestMagicLink").mockResolvedValue(true);
    await wrapper.find("input[type=email]").setValue("user@example.com");
    await wrapper.find("form").trigger("submit.prevent");
    // Let the transition settle
    await new Promise((r) => setTimeout(r, 20));
    expect(wrapper.text()).toContain("Check your email");
    expect(wrapper.text()).toContain("user@example.com");
  });
});
