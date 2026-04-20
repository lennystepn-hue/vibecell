import { defineStore } from "pinia";
import { ref } from "vue";

import {
  listConnections,
  revokeConnection,
  type Connection,
  type ConnectionType,
} from "@/api/connections";

export type { Connection, ConnectionType };

export const useConnectionsStore = defineStore("connections", () => {
  const list = ref<Connection[]>([]);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function refresh() {
    loading.value = true;
    error.value = null;
    try {
      list.value = await listConnections();
    } catch (e: unknown) {
      error.value = e instanceof Error ? e.message : "Failed to load connections";
    } finally {
      loading.value = false;
    }
  }

  async function revoke(id: string, kind: ConnectionType) {
    await revokeConnection(id, kind);
    list.value = list.value.filter((c) => c.id !== id);
  }

  return { list, loading, error, refresh, revoke };
});
