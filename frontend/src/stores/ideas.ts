import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type IdeaOut = components["schemas"]["IdeaOut"];
type IdeaIn = components["schemas"]["IdeaIn"];
type IdeaUpdate = components["schemas"]["IdeaUpdate"];

export type IdeaStatus = "inbox" | "triaged" | "discarded";

export const useIdeasStore = defineStore("ideas", () => {
  const list = ref<IdeaOut[]>([]);
  const loading = ref(false);
  const activeStatus = ref<IdeaStatus>("inbox");

  async function fetchList(status?: IdeaStatus): Promise<void> {
    loading.value = true;
    if (status) activeStatus.value = status;
    try {
      const { data } = await api.GET("/api/v1/ideas", {
        params: {
          query: { status: status ?? activeStatus.value },
        },
      });
      list.value = data ?? [];
    } finally {
      loading.value = false;
    }
  }

  async function create(body: IdeaIn): Promise<IdeaOut | null> {
    const { data } = await api.POST("/api/v1/ideas", { body });
    if (data) {
      if (data.status === activeStatus.value) {
        list.value = [data, ...list.value];
      }
      return data;
    }
    return null;
  }

  async function update(id: string, body: IdeaUpdate): Promise<IdeaOut | null> {
    const { data } = await api.PATCH("/api/v1/ideas/{idea_id}", {
      params: { path: { idea_id: id } },
      body,
    });
    if (data) {
      // If the new status no longer matches our filter, drop from list.
      if (data.status !== activeStatus.value) {
        list.value = list.value.filter((i) => i.id !== id);
      } else {
        list.value = list.value.map((i) => (i.id === id ? data : i));
      }
      return data;
    }
    return null;
  }

  async function remove(id: string): Promise<boolean> {
    const { error } = await api.DELETE("/api/v1/ideas/{idea_id}", {
      params: { path: { idea_id: id } },
    });
    if (!error) {
      list.value = list.value.filter((i) => i.id !== id);
      return true;
    }
    return false;
  }

  return { list, loading, activeStatus, fetchList, create, update, remove };
});
