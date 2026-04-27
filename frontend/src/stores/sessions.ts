import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type SessionOut = components["schemas"]["SessionOut"];
type SessionIn = components["schemas"]["SessionIn"];

// Backend caps `limit` at 200; we page in batches of 100 so the first paint
// stays snappy and the user can `loadMore()` for the rest.
const PAGE_SIZE = 100;

export const useSessionsStore = defineStore("sessions", () => {
  const list = ref<SessionOut[]>([]);
  const loading = ref(false);
  const loadingMore = ref(false);
  const activeSlug = ref<string | null>(null);
  // Cursor returned by the API for the next page; null = no more rows.
  const nextCursor = ref<string | null>(null);

  async function fetchList(slug: string): Promise<void> {
    loading.value = true;
    activeSlug.value = slug;
    nextCursor.value = null;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}/sessions", {
        params: { path: { slug }, query: { limit: PAGE_SIZE } },
      });
      list.value = data?.items ?? [];
      nextCursor.value = data?.next_cursor ?? null;
    } finally {
      loading.value = false;
    }
  }

  async function loadMore(): Promise<void> {
    if (loadingMore.value || !nextCursor.value || !activeSlug.value) return;
    loadingMore.value = true;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}/sessions", {
        params: {
          path: { slug: activeSlug.value },
          query: { limit: PAGE_SIZE, cursor: nextCursor.value },
        },
      });
      list.value = [...list.value, ...(data?.items ?? [])];
      nextCursor.value = data?.next_cursor ?? null;
    } finally {
      loadingMore.value = false;
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
    nextCursor.value = null;
  }

  return {
    list,
    loading,
    loadingMore,
    activeSlug,
    nextCursor,
    fetchList,
    loadMore,
    create,
    reset,
  };
});
