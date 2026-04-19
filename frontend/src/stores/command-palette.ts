import { defineStore } from "pinia";
import { computed, ref } from "vue";

export const useCommandPaletteStore = defineStore("commandPalette", () => {
  const open = ref(false);
  const query = ref("");
  const selectedIndex = ref(0);

  function toggle(): void {
    open.value = !open.value;
    if (!open.value) {
      query.value = "";
      selectedIndex.value = 0;
    }
  }

  function show(): void {
    open.value = true;
    query.value = "";
    selectedIndex.value = 0;
  }

  function hide(): void {
    open.value = false;
    query.value = "";
    selectedIndex.value = 0;
  }

  const hasQuery = computed(() => query.value.trim().length > 0);

  return { open, query, selectedIndex, hasQuery, toggle, show, hide };
});
