import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type ProjectListItem = components["schemas"]["ProjectListItem"];
type ProjectFullOut = components["schemas"]["ProjectFullOut"];

export const useProjectsStore = defineStore("projects", () => {
  const list = ref<ProjectListItem[]>([]);
  const active = ref<ProjectFullOut | null>(null);
  const loadingList = ref(false);
  const loadingActive = ref(false);

  async function fetchList(): Promise<void> {
    loadingList.value = true;
    try {
      const { data } = await api.GET("/api/v1/projects", {
        params: { query: { limit: 200 } },
      });
      list.value = data?.items ?? [];
    } finally {
      loadingList.value = false;
    }
  }

  async function fetchProject(slug: string): Promise<void> {
    loadingActive.value = true;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}", {
        params: { path: { slug } },
      });
      active.value = data ?? null;
      // Keep the list item in sync so status pills on cards update reactively
      if (data) {
        const idx = list.value.findIndex((p) => p.slug === slug);
        if (idx !== -1) {
          list.value[idx] = { ...list.value[idx], status: data.status };
        }
      }
    } finally {
      loadingActive.value = false;
    }
  }

  async function switchTo(slug: string): Promise<boolean> {
    const { error } = await api.POST("/api/v1/projects/{slug}/switch", {
      params: { path: { slug } },
    });
    if (!error) {
      await fetchProject(slug);
    }
    return !error;
  }

  /**
   * Optimistically change the active project's status in BOTH the detail
   * aggregate and the matching sidebar list row. Replaces the objects with
   * new shallow copies so every component reading them re-renders. Deep
   * in-place mutation (`active.value.status = 'live'`) sometimes failed to
   * propagate because Vue tracked the refs but not all the consumers.
   */
  function patchActiveStatus(status: string): void {
    if (active.value) {
      const archived_at = status === "archived"
        ? ((active.value as { archived_at?: string | null }).archived_at ?? new Date().toISOString())
        : null;
      active.value = { ...active.value, status, archived_at } as typeof active.value;
    }
    if (active.value) {
      const idx = list.value.findIndex((p) => p.slug === active.value?.slug);
      if (idx !== -1) {
        list.value[idx] = { ...list.value[idx], status };
      }
    }
  }

  return {
    list,
    active,
    loadingList,
    loadingActive,
    fetchList,
    fetchProject,
    switchTo,
    patchActiveStatus,
  };
});
