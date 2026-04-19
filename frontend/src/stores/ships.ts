import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type ShipOut = components["schemas"]["ShipOut"];
type ShipIn = components["schemas"]["ShipIn"];

export const useShipsStore = defineStore("ships", () => {
  const list = ref<ShipOut[]>([]);
  const loading = ref(false);
  const activeSlug = ref<string | null>(null);

  async function fetchList(slug: string): Promise<void> {
    loading.value = true;
    activeSlug.value = slug;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}/ships", {
        params: { path: { slug } },
      });
      list.value = data ?? [];
    } finally {
      loading.value = false;
    }
  }

  async function create(slug: string, body: ShipIn): Promise<ShipOut | null> {
    const { data } = await api.POST("/api/v1/projects/{slug}/ships", {
      params: { path: { slug } },
      body,
    });
    if (data) {
      list.value = [data, ...list.value];
      return data;
    }
    return null;
  }

  function reset(): void {
    list.value = [];
    activeSlug.value = null;
  }

  return { list, loading, activeSlug, fetchList, create, reset };
});
