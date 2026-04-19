<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";

import Modal from "@/components/ui/Modal.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import SelectField from "@/components/ui/SelectField.vue";
import TextArea from "@/components/ui/TextArea.vue";
import TextField from "@/components/ui/TextField.vue";

import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: "close"): void }>();

const projects = useProjectsStore();
const toast = useToastStore();
const router = useRouter();

const name = ref("");
const slug = ref("");
const emoji = ref("📦");
const pitch = ref("");
const status = ref("building");
const submitting = ref(false);
const error = ref<string | null>(null);

function autoSlug(from: string): string {
  return from
    .toLowerCase()
    .replace(/[^a-z0-9-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 50);
}

watch(name, (v) => {
  if (!slug.value || slug.value === autoSlug(name.value.slice(0, -1))) {
    slug.value = autoSlug(v);
  }
});

watch(
  () => props.open,
  (o) => {
    if (o) {
      name.value = "";
      slug.value = "";
      emoji.value = "📦";
      pitch.value = "";
      status.value = "building";
      error.value = null;
    }
  },
);

const disabled = computed(() => !name.value.trim() || !slug.value.trim() || submitting.value);

async function onSubmit() {
  error.value = null;
  submitting.value = true;
  const { data, error: apiError, response } = await api.POST("/api/v1/projects", {
    body: {
      name: name.value.trim(),
      slug: slug.value.trim(),
      emoji: emoji.value.trim() || null,
      pitch: pitch.value.trim() || null,
      status: status.value,
    },
  });
  submitting.value = false;

  if (apiError || !data) {
    const detail = (apiError as { detail?: string } | undefined)?.detail;
    error.value = detail ?? `Failed (${response?.status ?? "unknown"})`;
    return;
  }

  toast.push(`Created ${data.name}`, "success");
  await projects.fetchList();
  emit("close");
  router.push(`/p/${data.slug}`);
}
</script>

<template>
  <Modal :open="open" title="New project" width="520px" @close="emit('close')">
    <form class="flex flex-col gap-4" @submit.prevent="onSubmit">
      <div class="grid grid-cols-[1fr_120px] gap-3">
        <TextField v-model="name" label="name" placeholder="Butlr" :autofocus="true" />
        <TextField v-model="emoji" label="emoji" placeholder="📦" />
      </div>
      <TextField
        v-model="slug"
        label="slug"
        placeholder="butlr"
        :error="error"
      />
      <SelectField
        v-model="status"
        label="status"
        :options="[
          { value: 'idea', label: 'idea' },
          { value: 'building', label: 'building' },
          { value: 'live', label: 'live' },
          { value: 'paused', label: 'paused' },
          { value: 'shipped', label: 'shipped' },
        ]"
      />
      <TextArea v-model="pitch" label="pitch (optional)" placeholder="one line on what this is" />
      <div class="flex justify-end gap-2 mt-2">
        <button
          type="button"
          class="h-10 px-4 text-body text-fg-muted hover:text-fg-body transition-colors"
          :disabled="submitting"
          @click="emit('close')"
        >Cancel</button>
        <PrimaryButton type="submit" :disabled="disabled" :loading="submitting">
          Create
        </PrimaryButton>
      </div>
    </form>
  </Modal>
</template>
