import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type SessionOut = components["schemas"]["SessionOut"];
type SessionIn = components["schemas"]["SessionIn"];

export const useSessionsStore = defineStore("sessions", () => {
  const list = ref<SessionOut[]>([]);
  const loading = ref(false);
  const activeSlug = ref<string | null>(null);

  async function fetchList(slug: string): Promise<void> {
    loading.value = true;
    activeSlug.value = slug;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}/sessions", {
        params: { path: { slug }, query: { limit: 200 } },
      });
      list.value = data?.items ?? [];
    } finally {
      loading.value = false;
    }
  }

  async function create(slug: string, body: SessionIn): Promise<SessionOut | null> {
    const { data } = await api.POST("/api/v1/projects/{slug}/sessions", {
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
