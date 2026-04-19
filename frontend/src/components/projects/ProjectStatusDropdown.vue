<script setup lang="ts">
import { ref } from "vue";

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
</script>

<template>
  <div class="relative inline-block">
    <button
      type="button"
      class="transition-transform duration-fast hover:scale-[1.05]"
      @click="open = !open"
    >
      <StatusPill :status="project.status as never" />
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
        class="absolute top-full left-0 mt-1 glass rounded-md overflow-hidden z-20"
        style="background: rgba(13, 18, 26, 0.95); min-width: 140px"
        @click.stop
      >
        <button
          v-for="s in options"
          :key="s"
          type="button"
          class="w-full px-3 py-1.5 text-left flex items-center hover:bg-bg-surface-hi transition-colors"
          @click="pick(s)"
        >
          <StatusPill :status="s" />
        </button>
      </div>
    </transition>
  </div>
</template>
