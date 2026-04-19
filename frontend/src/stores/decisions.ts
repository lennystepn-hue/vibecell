import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type DecisionOut = components["schemas"]["DecisionOut"];
type DecisionIn = components["schemas"]["DecisionIn"];

export const useDecisionsStore = defineStore("decisions", () => {
  const list = ref<DecisionOut[]>([]);
  const loading = ref(false);
  const activeSlug = ref<string | null>(null);

  async function fetchList(slug: string): Promise<void> {
    loading.value = true;
    activeSlug.value = slug;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}/decisions", {
        params: { path: { slug } },
      });
      list.value = data ?? [];
    } finally {
      loading.value = false;
    }
  }

  async function create(slug: string, body: DecisionIn): Promise<DecisionOut | null> {
    const { data } = await api.POST("/api/v1/projects/{slug}/decisions", {
      params: { path: { slug } },
      body,
    });
    if (data) {
      list.value = [data, ...list.value];
      return data;
    }
    return null;
  }

  async function remove(slug: string, decisionId: string): Promise<boolean> {
    const { error } = await api.DELETE("/api/v1/projects/{slug}/decisions/{decision_id}", {
      params: { path: { slug, decision_id: decisionId } },
    });
    if (!error) {
      list.value = list.value.filter((d) => d.id !== decisionId);
      return true;
    }
    return false;
  }

  function reset(): void {
    list.value = [];
    activeSlug.value = null;
  }

  return { list, loading, activeSlug, fetchList, create, remove, reset };
});
