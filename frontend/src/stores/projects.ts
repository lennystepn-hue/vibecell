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

  return {
    list,
    active,
    loadingList,
    loadingActive,
    fetchList,
    fetchProject,
    switchTo,
  };
});
