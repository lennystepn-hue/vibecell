<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import TextArea from "@/components/ui/TextArea.vue";
import TextField from "@/components/ui/TextField.vue";
import { useDecisionsStore } from "@/stores/decisions";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];

const props = defineProps<{ project: Project }>();
const decisions = useDecisionsStore();
const toast = useToastStore();

const editing = ref(false);
const submitting = ref(false);

const form = ref({
  title: "",
  context: "",
  decision: "",
  consequences: "",
  reconsider_if: "",
});

function reload() {
  decisions.fetchList(props.project.slug);
}

onMounted(reload);
watch(() => props.project.slug, reload);

function resetForm() {
  form.value = { title: "", context: "", decision: "", consequences: "", reconsider_if: "" };
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toISOString().slice(0, 10);
}

async function onSubmit() {
  if (!form.value.title.trim() || !form.value.decision.trim()) {
    toast.push("Title and decision are required", "error");
    return;
  }
  submitting.value = true;
  const created = await decisions.create(props.project.slug, {
    title: form.value.title.trim(),
    context: form.value.context.trim() || null,
    decision: form.value.decision.trim(),
    consequences: form.value.consequences.trim() || null,
    reconsider_if: form.value.reconsider_if.trim() || null,
  });
  submitting.value = false;
  if (created) {
    toast.push("Decision recorded", "success");
    editing.value = false;
    resetForm();
  } else {
    toast.push("Couldn't record decision", "error");
  }
}

async function onDelete(id: string, title: string) {
  if (!window.confirm(`Delete decision "${title}"?`)) return;
  const ok = await decisions.remove(props.project.slug, id);
  toast.push(ok ? "Decision deleted" : "Couldn't delete", ok ? "success" : "error");
}

const count = computed(() => decisions.list.length);
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-center justify-between mb-4">
      <MonoLabel>decisions
        <span class="ml-2 opacity-60">({{ count }})</span>
      </MonoLabel>
      <button
        v-if="!editing"
        type="button"
        class="mono-label hover:text-fg-body transition-colors"
        @click="editing = true; resetForm()"
      >+ new decision</button>
    </header>

    <form v-if="editing" class="space-y-3 mb-5 p-4 rounded-md bg-bg-surface/40" @submit.prevent="onSubmit">
      <TextField v-model="form.title" label="title (required)" placeholder="Use Postgres over SQLite" />
      <TextArea v-model="form.context" label="context" placeholder="What forces led to this?" :rows="2" />
      <TextArea v-model="form.decision" label="decision (required)" placeholder="What did we decide?" :rows="2" />
      <TextArea v-model="form.consequences" label="consequences" placeholder="Downstream effects, trade-offs…" :rows="2" />
      <TextField v-model="form.reconsider_if" label="reconsider if" placeholder="e.g. write-throughput > 10k/s" />
      <div class="flex justify-end gap-3 pt-2">
        <button
          type="button"
          class="mono-label hover:text-fg-body transition-colors"
          @click="editing = false"
        >cancel</button>
        <PrimaryButton type="submit" :loading="submitting">Record decision</PrimaryButton>
      </div>
    </form>

    <div v-if="decisions.loading && count === 0" class="text-small text-fg-muted">loading…</div>
    <div v-else-if="count === 0 && !editing" class="text-small text-fg-muted italic">
      No decisions recorded yet. ADR-style entries help future-you remember <em>why</em>.
    </div>

    <ul class="space-y-3">
      <li
        v-for="d in decisions.list"
        :key="d.id"
        class="p-4 rounded-md bg-bg-surface/40 border border-border-subtle"
      >
        <header class="flex items-start justify-between gap-3 mb-2">
          <h3 class="text-section text-fg-primary font-semibold tracking-tight">{{ d.title }}</h3>
          <div class="flex items-center gap-3 shrink-0">
            <span class="font-mono text-[10px] text-fg-subtle">{{ formatDate(d.created_at) }}</span>
            <button
              type="button"
              class="mono-label hover:text-signal-red transition-colors"
              @click="onDelete(d.id, d.title)"
              :title="`Delete decision ${d.title}`"
            >✕</button>
          </div>
        </header>
        <div class="space-y-3">
          <div v-if="d.context">
            <MonoLabel>context</MonoLabel>
            <p class="text-small text-fg-muted mt-1 whitespace-pre-wrap">{{ d.context }}</p>
          </div>
          <div>
            <MonoLabel>decision</MonoLabel>
            <p class="text-body text-fg-body mt-1 whitespace-pre-wrap">{{ d.decision }}</p>
          </div>
          <div v-if="d.consequences">
            <MonoLabel>consequences</MonoLabel>
            <p class="text-small text-fg-muted mt-1 whitespace-pre-wrap">{{ d.consequences }}</p>
          </div>
          <div v-if="d.reconsider_if">
            <MonoLabel>reconsider if</MonoLabel>
            <p class="text-small text-fg-muted mt-1 italic">{{ d.reconsider_if }}</p>
          </div>
        </div>
      </li>
    </ul>
  </section>
</template>
