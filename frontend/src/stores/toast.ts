import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastKind = "info" | "success" | "warning" | "error";

export interface Toast {
  id: string;
  kind: ToastKind;
  message: string;
  expiresAt: number;
}

export const useToastStore = defineStore("toast", () => {
  const items = ref<Toast[]>([]);

  function push(message: string, kind: ToastKind = "info", ttlMs = 4000) {
    const id = crypto.randomUUID();
    const expiresAt = Date.now() + ttlMs;
    items.value = [...items.value, { id, kind, message, expiresAt }];
    setTimeout(() => dismiss(id), ttlMs);
  }

  function dismiss(id: string) {
    items.value = items.value.filter((t) => t.id !== id);
  }

  function clear() {
    items.value = [];
  }

  return { items, push, dismiss, clear };
});
