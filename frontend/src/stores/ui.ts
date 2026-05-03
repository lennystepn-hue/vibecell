/**
 * UI shell state — chrome-level toggles that need to be addressed by
 * components that don't share a parent (e.g. TopBar's hamburger button
 * needs to drive SidebarProjects, but those live in different page
 * subtrees).
 *
 * Currently scoped to the mobile sidebar drawer. Add other cross-tree
 * UI flags here (modal stacks, command palette, etc.) only when the
 * existing per-feature stores can't reach them.
 */
import { defineStore } from "pinia";
import { ref } from "vue";

export const useUiStore = defineStore("ui", () => {
  // Whether the mobile sidebar drawer is currently open. Desktop ignores
  // this — the sidebar is always visible at md+.
  const mobileSidebarOpen = ref(false);

  // Set by pages that mount a SidebarProjects so the TopBar's hamburger
  // button knows whether to render. Unset on unmount. Without this guard
  // the hamburger would appear on every authed page including /p where
  // there's no sidebar to toggle.
  const sidebarMounted = ref(false);

  function openSidebar() {
    mobileSidebarOpen.value = true;
  }
  function closeSidebar() {
    mobileSidebarOpen.value = false;
  }
  function toggleSidebar() {
    mobileSidebarOpen.value = !mobileSidebarOpen.value;
  }
  function registerSidebar() {
    sidebarMounted.value = true;
  }
  function unregisterSidebar() {
    sidebarMounted.value = false;
    mobileSidebarOpen.value = false;
  }

  return {
    mobileSidebarOpen,
    sidebarMounted,
    openSidebar,
    closeSidebar,
    toggleSidebar,
    registerSidebar,
    unregisterSidebar,
  };
});
