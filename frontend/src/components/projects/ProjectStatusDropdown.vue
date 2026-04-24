<script setup lang="ts">
import { onMounted, onUnmounted, ref } from "vue";

import StatusPill from "@/components/ui/StatusPill.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
type Status = "idea" | "building" | "live" | "paused" | "shipped" | "archived" | "dead";

const props = defineProps<{ project: Project }>();
const projects = useProjectsStore();
const toast = useToastStore();
const open = ref(false);
const rootEl = ref<HTMLElement | null>(null);
const options: Status[] = ["idea", "building", "live", "paused", "shipped", "archived", "dead"];

async function pick(status: Status) {
  open.value = false;
  const { error } = await api.PATCH("/api/v1/projects/{slug}", {
    params: { path: { slug: props.project.slug } },
    body: { status },
  });
  if (error) {
    toast.push("Couldn't update status", "error");
    return;
  }
  await projects.fetchProject(props.project.slug);
  toast.push(`Status → ${status}`, "success");
}

// Close when user clicks anywhere outside the dropdown — without this, the
// only way to close was re-clicking the pill. Also close on Escape.
function onDocClick(e: MouseEvent) {
  if (!open.value || !rootEl.value) return;
  if (!rootEl.value.contains(e.target as Node)) open.value = false;
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") open.value = false;
}
onMounted(() => {
  document.addEventListener("click", onDocClick);
  document.addEventListener("keydown", onKey);
});
onUnmounted(() => {
  document.removeEventListener("click", onDocClick);
  document.removeEventListener("keydown", onKey);
});
</script>

<template>
  <div ref="rootEl" class="relative inline-block">
    <button
      type="button"
      class="inline-flex items-center gap-1 transition-transform duration-fast hover:scale-[1.05] group"
      :aria-expanded="open"
      aria-label="Change project status"
      title="Click to change status"
      @click.stop="open = !open"
    >
      <StatusPill :status="project.status as never" />
      <!-- Subtle caret so it's clear this is interactive. -->
      <span
        class="text-[10px] leading-none text-fg-subtle transition-transform duration-fast"
        :class="open ? 'rotate-180' : 'rotate-0 group-hover:text-fg-body'"
        aria-hidden="true"
      >▾</span>
    </button>
    <transition
      enter-active-class="transition-opacity duration-fast ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-fast ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="absolute top-full left-0 mt-1 glass rounded-md overflow-hidden z-20 shadow-lg"
        style="background: rgba(13, 18, 26, 0.95); min-width: 140px"
        @click.stop
      >
        <button
          v-for="s in options"
          :key="s"
          type="button"
          class="w-full px-3 py-1.5 text-left flex items-center hover:bg-bg-surface-hi transition-colors"
          :class="s === project.status ? 'bg-bg-surface-hi/50' : ''"
          @click="pick(s)"
        >
          <StatusPill :status="s" />
          <span v-if="s === project.status" class="ml-auto text-[10px] text-fg-subtle">current</span>
        </button>
      </div>
    </transition>
  </div>
</template>
