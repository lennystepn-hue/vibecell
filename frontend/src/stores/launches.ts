import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type LaunchOut = components["schemas"]["LaunchOut"];
type LaunchIn = components["schemas"]["LaunchIn"];
type LaunchUpdate = components["schemas"]["LaunchUpdate"];

export const useLaunchesStore = defineStore("launches", () => {
  const list = ref<LaunchOut[]>([]);
  const loading = ref(false);
  const activeSlug = ref<string | null>(null);

  async function fetchList(slug: string): Promise<void> {
    loading.value = true;
    activeSlug.value = slug;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}/launches", {
        params: { path: { slug } },
      });
      list.value = data ?? [];
    } finally {
      loading.value = false;
    }
  }

  async function create(slug: string, body: LaunchIn): Promise<LaunchOut | null> {
    const { data } = await api.POST("/api/v1/projects/{slug}/launches", {
      params: { path: { slug } },
      body,
    });
    if (data) {
      list.value = [data, ...list.value];
      return data;
    }
    return null;
  }

  async function update(
    slug: string,
    launchId: string,
    body: LaunchUpdate,
  ): Promise<LaunchOut | null> {
    const { data } = await api.PATCH("/api/v1/projects/{slug}/launches/{launch_id}", {
      params: { path: { slug, launch_id: launchId } },
      body,
    });
    if (data) {
      list.value = list.value.map((l) => (l.id === launchId ? data : l));
      return data;
    }
    return null;
  }

  function reset(): void {
    list.value = [];
    activeSlug.value = null;
  }

  return { list, loading, activeSlug, fetchList, create, update, reset };
});
