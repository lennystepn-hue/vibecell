import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type User = components["schemas"]["UserOut"];
type Workspace = components["schemas"]["WorkspaceOut"];
type WorkspaceListItem = components["schemas"]["WorkspaceListItem"];

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const activeWorkspace = ref<Workspace | null>(null);
  const workspaces = ref<WorkspaceListItem[]>([]);
  const loading = ref(false);

  const isAuthed = computed(() => user.value !== null);

  async function refresh(): Promise<void> {
    loading.value = true;
    try {
      const { data, error } = await api.GET("/api/v1/me");
      if (error || !data) {
        user.value = null;
        activeWorkspace.value = null;
        workspaces.value = [];
        return;
      }
      user.value = data.user;
      activeWorkspace.value = data.active_workspace;
      workspaces.value = data.workspaces;
    } finally {
      loading.value = false;
    }
  }

  async function requestMagicLink(email: string): Promise<boolean> {
    const { error } = await api.POST("/api/v1/auth/magic-link", {
      body: { email },
    });
    return !error;
  }

  async function logout(): Promise<void> {
    await api.POST("/api/v1/auth/logout", {});
    user.value = null;
    activeWorkspace.value = null;
    workspaces.value = [];
  }

  return {
    user,
    activeWorkspace,
    workspaces,
    isAuthed,
    loading,
    refresh,
    requestMagicLink,
    logout,
  };
});
