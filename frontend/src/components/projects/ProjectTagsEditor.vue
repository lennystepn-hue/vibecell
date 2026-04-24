<script setup lang="ts">
import { ref, nextTick } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
const props = defineProps<{ project: Project }>();
const projects = useProjectsStore();
const toast = useToastStore();

const newTag = ref("");
const adding = ref(false);
const inputRef = ref<HTMLInputElement | null>(null);

function openAdding() {
  adding.value = true;
  nextTick(() => inputRef.value?.focus());
}

function cancelAdding() {
  adding.value = false;
  newTag.value = "";
}

async function addTag() {
  const name = newTag.value.trim();
  if (!name) return;
  const { error } = await api.POST("/api/v1/projects/{slug}/tags", {
    params: { path: { slug: props.project.slug } },
    body: { name, color: null },
  });
  if (error) {
    toast.push(`Couldn't add tag "${name}"`, "error");
    return;
  }
  newTag.value = "";
  adding.value = false;
  await projects.fetchProject(props.project.slug);
}

async function removeTag(tagId: string) {
  const { error } = await api.DELETE("/api/v1/projects/{slug}/tags/{tag_id}", {
    params: { path: { slug: props.project.slug, tag_id: tagId } },
  });
  if (error) {
    toast.push("Couldn't remove tag", "error");
    return;
  }
  await projects.fetchProject(props.project.slug);
}
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>tags</MonoLabel>

    <div class="flex flex-wrap gap-2 mt-3">
      <span
        v-for="t in project.tags"
        :key="t.id"
        class="group inline-flex items-center gap-1.5 px-2.5 h-6 rounded-sm font-mono text-[11px]"
        :style="{
          background: t.color ? t.color + '20' : 'var(--signal-blue-bg)',
          color: t.color ?? 'var(--fg-body)',
          border: '1px solid var(--border-subtle)',
        }"
      >
        #{{ t.name }}
        <button
          type="button"
          class="opacity-0 group-hover:opacity-100 text-fg-subtle hover:text-signal-red transition-all"
          aria-label="Remove tag"
          @click="removeTag(t.id)"
        >✕</button>
      </span>
    </div>

    <!-- Inline add row (shown only when adding) -->
    <form v-if="adding" class="flex gap-2 mt-3" @submit.prevent="addTag">
      <input
        ref="inputRef"
        v-model="newTag"
        type="text"
        placeholder="tag name"
        class="flex-1 h-9 px-3 rounded-md font-sans text-small bg-bg-surface border border-border text-fg-body placeholder:text-fg-subtle"
        @keydown.esc="cancelAdding"
      />
      <button
        type="submit"
        :disabled="!newTag.trim()"
        class="h-9 px-3 rounded-md font-medium text-small disabled:opacity-50"
        :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
      >add</button>
    </form>

    <!-- Trigger button (hidden when adding) -->
    <button
      v-else
      type="button"
      class="mt-3 mono-label text-fg-subtle hover:text-fg-body transition-colors"
      @click="openAdding"
    >+ add tag</button>
  </section>
</template>
