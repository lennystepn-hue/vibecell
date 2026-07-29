import { describe, expect, it } from "vitest";
import { mount } from "@vue/test-utils";

import Card from "../Card.vue";

describe("Card", () => {
  it("renders the title with the // prefix", () => {
    const w = mount(Card, { props: { title: "sessions" } });
    expect(w.find("h3").text()).toBe("//sessions");
  });

  it("omits the header entirely when there is nothing to put in it", () => {
    const w = mount(Card, { slots: { default: "<p>body</p>" } });
    expect(w.find("header").exists()).toBe(false);
    expect(w.text()).toContain("body");
  });

  it("renders a header for a meta slot even without a title", () => {
    const w = mount(Card, { slots: { meta: "(12)" } });
    expect(w.find("header").exists()).toBe(true);
    expect(w.find("h3").text()).toContain("(12)");
  });

  it("renders a header for an actions slot even without a title", () => {
    const w = mount(Card, { slots: { actions: "<button>+ add</button>" } });
    expect(w.find("header").exists()).toBe(true);
    expect(w.find("button").text()).toBe("+ add");
  });

  it("dims the // prefix", () => {
    const w = mount(Card, { props: { title: "todos" } });
    // Two dimmed spans exist once meta is present, so pin the prefix by
    // position rather than by class alone.
    expect(w.find("h3 span:first-child").text()).toBe("//");
    expect(w.find("h3 span:first-child").classes()).toContain("opacity-60");
  });

  it("puts meta inside the title line, dimmed, after the title", () => {
    const w = mount(Card, { props: { title: "todos" }, slots: { meta: "(3)" } });
    const h3 = w.find("h3");
    expect(h3.text()).toContain("//todos");
    const meta = h3.find("span:last-child");
    expect(meta.text()).toBe("(3)");
    expect(meta.classes()).toContain("opacity-60");
  });

  it("applies the standard inset by default", () => {
    const w = mount(Card, { props: { title: "x" } });
    expect(w.find("section").classes()).toContain("p-5");
  });

  it("hands padding to the caller when padding=none, but keeps the header inset", () => {
    const w = mount(Card, { props: { title: "x", padding: "none" } });
    const section = w.find("section");
    expect(section.classes()).toContain("p-0");
    expect(section.classes()).toContain("overflow-hidden");
    // A full-bleed body still needs its header aligned with everything else.
    expect(w.find("header").classes()).toContain("px-5");
  });

  it("merges layout classes onto the root so grid-filling cards still work", () => {
    const w = mount(Card, {
      props: { title: "primer" },
      attrs: { class: "flex flex-col h-full min-h-0" },
    });
    const classes = w.find("section").classes();
    expect(classes).toContain("glass");
    expect(classes).toContain("flex");
    expect(classes).toContain("min-h-0");
  });
});
