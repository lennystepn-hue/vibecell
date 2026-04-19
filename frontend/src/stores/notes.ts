import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type NoteOut = components["schemas"]["NoteOut"];

export const useNotesStore = defineStore("notes", () => {
  const bySlug = ref<Record<string, NoteOut>>({});
  const loading = ref(false);
  const saving = ref(false);

  async function fetch(slug: string): Promise<NoteOut | null> {
    loading.value = true;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}/notes", {
        params: { path: { slug } },
      });
      if (data) {
        bySlug.value = { ...bySlug.value, [slug]: data };
        return data;
      }
      return null;
    } finally {
      loading.value = false;
    }
  }

  async function save(slug: string, markdown: string): Promise<NoteOut | null> {
    saving.value = true;
    try {
      const { data } = await api.PUT("/api/v1/projects/{slug}/notes", {
        params: { path: { slug } },
        body: { markdown },
      });
      if (data) {
        bySlug.value = { ...bySlug.value, [slug]: data };
        return data;
      }
      return null;
    } finally {
      saving.value = false;
    }
  }

  return { bySlug, loading, saving, fetch, save };
});
