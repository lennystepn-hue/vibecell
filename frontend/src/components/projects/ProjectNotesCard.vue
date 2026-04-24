<script setup lang="ts">
import { useDebounceFn } from "@vueuse/core";
import { computed, onMounted, ref, watch } from "vue";

import { useNotesStore } from "@/stores/notes";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];

const props = defineProps<{ project: Project }>();
const notes = useNotesStore();

const localValue = ref("");
const dirty = ref(false);
const lastSavedAt = ref<string | null>(null);

async function load() {
  const slug = props.project.slug;
  const n = await notes.fetch(slug);
  localValue.value = n?.markdown ?? "";
  lastSavedAt.value = n?.updated_at ?? null;
  dirty.value = false;
}

onMounted(load);
watch(() => props.project.slug, load);

async function doSave() {
  if (!dirty.value) return;
  const result = await notes.save(props.project.slug, localValue.value);
  if (result) {
    dirty.value = false;
    lastSavedAt.value = result.updated_at ?? new Date().toISOString();
  }
}

const debouncedSave = useDebounceFn(doSave, 1500);

function onInput(ev: Event) {
  const target = ev.target as HTMLTextAreaElement;
  localValue.value = target.value;
  dirty.value = true;
  debouncedSave();
}

function onBlur() {
  if (dirty.value) {
    void doSave();
  }
}

const statusLabel = computed(() => {
  if (notes.saving) return "saving…";
  if (dirty.value) return "unsaved changes";
  if (lastSavedAt.value) {
    const d = new Date(lastSavedAt.value);
    return `saved ${d.toISOString().slice(0, 16).replace("T", " ")}`;
  }
  return "empty";
});
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-center justify-between mb-3 select-none">
      <h3 class="mono-label text-fg-muted">//notes (markdown)</h3>
      <span class="mono-label opacity-60">{{ statusLabel }}</span>
    </header>
    <div>
      <textarea
        :value="localValue"
        placeholder="Free-form markdown. Auto-saves on pause + blur."
        rows="12"
        class="w-full px-3 py-2 rounded-md font-mono text-small bg-bg-surface border border-border text-fg-primary placeholder:text-fg-subtle resize-y"
        @input="onInput"
        @blur="onBlur"
      />
    </div>
  </section>
</template>
