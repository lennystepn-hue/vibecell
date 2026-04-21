<script setup lang="ts">
import { ref } from "vue";

import CopyableValue from "@/components/ui/CopyableValue.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
const props = defineProps<{ project: Project }>();

const projects = useProjectsStore();
const toast = useToastStore();

const showForm = ref(false);
const submitting = ref(false);
const formKind = ref("production");
const formUrl = ref("");
const formDbAlias = ref("");
const formEnvPath = ref("");

async function addEnv() {
  if (!formKind.value.trim()) return;
  submitting.value = true;
  const { error } = await api.POST("/api/v1/projects/{slug}/environments", {
    params: { path: { slug: props.project.slug } },
    body: {
      kind: formKind.value.trim(),
      url: formUrl.value.trim() || null,
      db_alias: formDbAlias.value.trim() || null,
      env_template_path: formEnvPath.value.trim() || null,
    },
  });
  submitting.value = false;
  if (error) {
    toast.push("Failed to add environment", "error");
    return;
  }
  formKind.value = "production";
  formUrl.value = "";
  formDbAlias.value = "";
  formEnvPath.value = "";
  showForm.value = false;
  await projects.fetchProject(props.project.slug);
}

async function removeEnv(envId: string) {
  const { error } = await api.DELETE("/api/v1/projects/{slug}/environments/{env_id}", {
    params: { path: { slug: props.project.slug, env_id: envId } },
  });
  if (error) {
    toast.push("Failed to remove environment", "error");
    return;
  }
  await projects.fetchProject(props.project.slug);
}
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>environments</MonoLabel>

    <div v-if="project.environments && project.environments.length > 0" class="mt-3 space-y-2">
      <div
        v-for="env in project.environments"
        :key="env.id"
        class="group flex items-start gap-2 py-1.5 border-b border-border-subtle last:border-b-0"
      >
        <span class="mono-label shrink-0 w-24 truncate pt-0.5">{{ env.kind }}</span>
        <div class="flex-1 min-w-0 space-y-0.5">
          <CopyableValue v-if="env.url" :value="env.url" mono small class="text-fg-body" />
          <span v-if="env.db_alias" class="block font-mono text-[11px] text-fg-subtle">db: {{ env.db_alias }}</span>
          <span v-if="env.env_template_path" class="block font-mono text-[11px] text-fg-subtle">{{ env.env_template_path }}</span>
        </div>
        <button
          type="button"
          class="opacity-0 group-hover:opacity-100 text-fg-muted hover:text-signal-red transition-all shrink-0 text-small"
          aria-label="Remove environment"
          @click="removeEnv(env.id)"
        >✕</button>
      </div>
    </div>
    <p v-else-if="!showForm" class="text-small text-fg-muted italic mt-2">— no environments —</p>

    <form v-if="showForm" class="mt-3 space-y-2 pt-2 border-t border-border-subtle" @submit.prevent="addEnv">
      <div class="flex gap-2">
        <input
          v-model="formKind"
          type="text"
          placeholder="kind (production, staging…)"
          class="flex-1 h-9 px-2 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
        />
      </div>
      <input
        v-model="formUrl"
        type="url"
        placeholder="https://…"
        class="w-full h-9 px-2 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
      />
      <div class="flex gap-2 justify-end">
        <button
          type="button"
          class="mono-label hover:text-fg-body transition-colors"
          @click="showForm = false"
        >cancel</button>
        <button
          type="submit"
          :disabled="!formKind.trim() || submitting"
          class="h-9 px-3 rounded-md font-medium text-small disabled:opacity-50"
          :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
        >add</button>
      </div>
    </form>

    <button
      v-else
      type="button"
      class="mt-3 mono-label text-fg-subtle hover:text-fg-body transition-colors"
      @click="showForm = true"
    >+ add environment</button>
  </section>
</template>
