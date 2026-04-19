<script setup lang="ts">
import { ref, watch } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import TextArea from "@/components/ui/TextArea.vue";
import TextField from "@/components/ui/TextField.vue";

import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
const props = defineProps<{ project: Project }>();
const emit = defineEmits<{ (e: "close"): void }>();

const projects = useProjectsStore();
const toast = useToastStore();

const current_focus = ref(props.project.context?.current_focus ?? "");
const next_step = ref(props.project.context?.next_step ?? "");
const user_wants = ref(props.project.context?.user_wants ?? "");
const blocked_by = ref(props.project.context?.blocked_by ?? "");
const open_questions = ref<string[]>([...(props.project.context?.open_questions ?? [])] as string[]);
const saving = ref(false);

watch(() => props.project, (p) => {
  current_focus.value = p.context?.current_focus ?? "";
  next_step.value = p.context?.next_step ?? "";
  user_wants.value = p.context?.user_wants ?? "";
  blocked_by.value = p.context?.blocked_by ?? "";
  open_questions.value = [...(p.context?.open_questions ?? [])] as string[];
});

function addQuestion() {
  open_questions.value = [...open_questions.value, ""];
}
function removeQuestion(i: number) {
  open_questions.value = open_questions.value.filter((_, idx) => idx !== i);
}

async function save() {
  saving.value = true;
  const { error } = await api.PATCH("/api/v1/projects/{slug}/context", {
    params: { path: { slug: props.project.slug } },
    body: {
      current_focus: current_focus.value || null,
      next_step: next_step.value || null,
      user_wants: user_wants.value || null,
      blocked_by: blocked_by.value || null,
      open_questions: open_questions.value.filter((q) => q.trim().length > 0),
    },
  });
  saving.value = false;
  if (error) {
    toast.push("Failed to save context", "error");
    return;
  }
  toast.push("Context saved", "success");
  await projects.fetchProject(props.project.slug);
  emit("close");
}
</script>

<template>
  <section class="glass rounded-lg p-5 space-y-5">
    <div>
      <MonoLabel>editing context</MonoLabel>
    </div>

    <TextArea
      v-model="current_focus"
      label="current focus"
      :rows="2"
      placeholder="What you're working on right now"
    />

    <TextArea
      v-model="next_step"
      label="next step"
      :rows="2"
      placeholder="The one concrete next action"
    />

    <TextArea
      v-model="user_wants"
      label="user wants"
      :rows="2"
      placeholder="What the user is asking for (optional)"
    />

    <TextField
      v-model="blocked_by"
      label="blocked by"
      placeholder="Waiting on… (leave empty when unblocked)"
    />

    <div>
      <div class="flex items-center gap-2">
        <MonoLabel>open questions</MonoLabel>
        <button
          type="button"
          class="mono-label hover:text-fg-body transition-colors"
          @click="addQuestion"
        >+ add</button>
      </div>
      <div class="mt-2 space-y-2">
        <div v-for="(_q, i) in open_questions" :key="i" class="flex gap-2 items-start">
          <input
            v-model="open_questions[i]"
            type="text"
            class="flex-1 h-9 px-3 rounded-md font-sans text-body bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
            placeholder="?"
          />
          <button
            type="button"
            class="w-9 h-9 text-fg-muted hover:text-signal-red transition-colors"
            aria-label="Remove question"
            @click="removeQuestion(i)"
          >✕</button>
        </div>
      </div>
    </div>

    <div class="flex justify-end gap-2">
      <button
        type="button"
        class="h-10 px-4 text-body text-fg-muted hover:text-fg-body transition-colors"
        :disabled="saving"
        @click="emit('close')"
      >Cancel</button>
      <PrimaryButton :disabled="saving" :loading="saving" @click="save">Save</PrimaryButton>
    </div>
  </section>
</template>
