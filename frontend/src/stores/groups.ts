import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type Group = components["schemas"]["GroupOut"];

export const useGroupsStore = defineStore("groups", () => {
  const list = ref<Group[]>([]);
  const loading = ref(false);

  const byId = computed(() => {
    const m = new Map<string, Group>();
    for (const g of list.value) m.set(g.id, g);
    return m;
  });

  async function fetchList(): Promise<void> {
    loading.value = true;
    try {
      const { data } = await api.GET("/api/v1/groups");
      list.value = data ?? [];
    } finally {
      loading.value = false;
    }
  }

  async function create(name: string, color?: string | null): Promise<Group | null> {
    const { data } = await api.POST("/api/v1/groups", {
      body: { name, color: color ?? null },
    });
    if (data) {
      list.value = [...list.value, data];
      return data;
    }
    return null;
  }

  async function remove(id: string): Promise<void> {
    await api.DELETE("/api/v1/groups/{group_id}", {
      params: { path: { group_id: id } },
    });
    list.value = list.value.filter((g) => g.id !== id);
  }

  async function reorderProjects(
    items: { slug: string; group_id: string | null; position: number }[],
  ): Promise<void> {
    await api.POST("/api/v1/projects/reorder", { body: { items } });
  }

  return { list, loading, byId, fetchList, create, remove, reorderProjects };
});
