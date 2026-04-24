<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref } from "vue";

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
const triggerEl = ref<HTMLElement | null>(null);
const menuEl = ref<HTMLElement | null>(null);
const menuStyle = ref<Record<string, string>>({});
const options: Status[] = ["idea", "building", "live", "paused", "shipped", "archived", "dead"];

async function toggle() {
  open.value = !open.value;
  if (open.value) {
    // Position the teleported menu relative to the trigger's current bounding
    // box. Teleporting to <body> puts it outside any stacking context so the
    // sticky dashboard toolbar can't paint over it, but we lose CSS anchoring
    // — compute it manually.
    await nextTick();
    position();
  }
}

function position() {
  if (!triggerEl.value) return;
  const rect = triggerEl.value.getBoundingClientRect();
  menuStyle.value = {
    position: "fixed",
    top: `${rect.bottom + 4}px`,
    left: `${rect.left}px`,
    minWidth: "160px",
    zIndex: "70",  // above sticky toolbars (z-20) and modal overlays (z-50)
  };
}

async function pick(status: Status) {
  open.value = false;
  // Optimistic update: flip the pill immediately so the UI feels instant.
  // Stash the old value so we can roll back on failure.
  const prev = props.project.status;
  (props.project as { status: string }).status = status;
  if (projects.active && projects.active.slug === props.project.slug) {
    (projects.active as { status: string }).status = status;
  }

  const { error } = await api.PATCH("/api/v1/projects/{slug}", {
    params: { path: { slug: props.project.slug } },
    body: { status },
  });
  if (error) {
    // Roll back the optimistic change.
    (props.project as { status: string }).status = prev;
    if (projects.active && projects.active.slug === props.project.slug) {
      (projects.active as { status: string }).status = prev;
    }
    toast.push("Couldn't update status", "error");
    return;
  }
  // Refresh in the background so any derived fields (e.g. archived_at on
  // status=archived) are pulled in too. The pill already shows the right
  // value from the optimistic update, so this is silent.
  void projects.fetchProject(props.project.slug);
  toast.push(`Status → ${status}`, "success");
}

// Close when user clicks outside. Both the trigger and the teleported menu
// count as "inside" — hit-testing uses the two refs.
function onDocClick(e: MouseEvent) {
  if (!open.value) return;
  const target = e.target as Node;
  if (triggerEl.value?.contains(target)) return;
  if (menuEl.value?.contains(target)) return;
  open.value = false;
}
function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") open.value = false;
}
// Re-position on scroll/resize so the menu tracks the trigger.
function onReflow() {
  if (open.value) position();
}
onMounted(() => {
  document.addEventListener("click", onDocClick);
  document.addEventListener("keydown", onKey);
  window.addEventListener("scroll", onReflow, true);
  window.addEventListener("resize", onReflow);
});
onUnmounted(() => {
  document.removeEventListener("click", onDocClick);
  document.removeEventListener("keydown", onKey);
  window.removeEventListener("scroll", onReflow, true);
  window.removeEventListener("resize", onReflow);
});
</script>

<template>
  <div class="relative inline-block">
    <button
      ref="triggerEl"
      type="button"
      class="inline-flex items-center gap-1 transition-transform duration-fast hover:scale-[1.05] group"
      :aria-expanded="open"
      aria-label="Change project status"
      title="Click to change status"
      @click.stop="toggle"
    >
      <StatusPill :status="project.status as never" />
      <span
        class="text-[10px] leading-none text-fg-subtle transition-transform duration-fast"
        :class="open ? 'rotate-180' : 'rotate-0 group-hover:text-fg-body'"
        aria-hidden="true"
      >▾</span>
    </button>

    <!-- Teleport to body so the menu escapes the sticky-toolbar stacking
         context. Without this, the dashboard toolbar (z-20, sticky) paints
         over the dropdown and clicks on 'shipped' / 'archived' / 'dead' land
         on the toolbar instead of the menu item. -->
    <Teleport to="body">
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
          ref="menuEl"
          class="glass rounded-md overflow-hidden shadow-modal border border-border"
          :style="{ ...menuStyle, background: 'var(--bg-chrome)' }"
          @click.stop
        >
          <button
            v-for="s in options"
            :key="s"
            type="button"
            class="w-full px-3 py-1.5 text-left flex items-center gap-2 hover:bg-bg-surface-hi transition-colors"
            :class="s === project.status ? 'bg-bg-surface-hi/70' : ''"
            @click="pick(s)"
          >
            <StatusPill :status="s" />
            <span v-if="s === project.status" class="ml-auto text-[10px] text-fg-subtle">current</span>
          </button>
        </div>
      </transition>
    </Teleport>
  </div>
</template>
