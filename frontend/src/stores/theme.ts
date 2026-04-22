import { defineStore } from "pinia";
import { computed, ref, watch } from "vue";

export type ThemeName = "midnight" | "terminal-green" | "paper";

/** Each theme overrides a handful of CSS variables at :root[data-theme=…]. */
export const THEMES: Record<ThemeName, { label: string; hint: string }> = {
  "midnight": { label: "Midnight", hint: "Deep navy, teal accents (default)" },
  "terminal-green": { label: "Terminal green", hint: "Full phosphor, CRT vibes" },
  "paper": { label: "Paper", hint: "Light mode for daytime demos" },
};

const STORAGE_KEY = "vc:theme";

export const useThemeStore = defineStore("theme", () => {
  const active = ref<ThemeName>(readInitial());

  const options = computed(() => Object.entries(THEMES) as Array<[ThemeName, typeof THEMES[ThemeName]]>);

  function readInitial(): ThemeName {
    if (typeof localStorage === "undefined") return "midnight";
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw && raw in THEMES) return raw as ThemeName;
    return "midnight";
  }

  function apply(name: ThemeName) {
    active.value = name;
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", name);
    }
    if (typeof localStorage !== "undefined") {
      localStorage.setItem(STORAGE_KEY, name);
    }
  }

  // Apply on boot + whenever it changes (for cross-tab sync later if needed).
  watch(active, (v) => {
    if (typeof document !== "undefined") {
      document.documentElement.setAttribute("data-theme", v);
    }
  }, { immediate: true });

  return { active, options, apply };
});
