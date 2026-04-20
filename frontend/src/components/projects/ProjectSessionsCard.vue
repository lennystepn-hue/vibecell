<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import Modal from "@/components/ui/Modal.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import TextArea from "@/components/ui/TextArea.vue";
import TextField from "@/components/ui/TextField.vue";
import { useSessionsStore } from "@/stores/sessions";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
type SessionOut = components["schemas"]["SessionOut"];

const props = defineProps<{ project: Project }>();
const sessions = useSessionsStore();
const toast = useToastStore();

const expanded = ref<Record<string, boolean>>({});
const modalOpen = ref(false);
const submitting = ref(false);

const form = ref({
  summary: "",
  next_step: "",
  files_touched: "",
  commits: "",
});

function reload() {
  sessions.fetchList(props.project.slug);
}

onMounted(reload);
watch(() => props.project.slug, reload);

function relTime(iso: string): string {
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const sec = Math.floor(diff / 1000);
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mo = Math.floor(day / 30);
  return `${mo}mo ago`;
}

function shortSha(v: unknown): string {
  if (typeof v === "string") return v.slice(0, 7);
  if (v && typeof v === "object" && "sha" in v) {
    return String((v as { sha: unknown }).sha).slice(0, 7);
  }
  return "";
}

function shaMsg(v: unknown): string {
  if (typeof v === "string") return "";
  if (v && typeof v === "object" && "msg" in v) {
    return String((v as { msg: unknown }).msg ?? "");
  }
  return "";
}

function toggleExpand(id: string) {
  expanded.value = { ...expanded.value, [id]: !expanded.value[id] };
}

function resetForm() {
  form.value = { summary: "", next_step: "", files_touched: "", commits: "" };
}

function parseCsv(input: string): string[] {
  return input
    .split(",")
    .map((s) => s.trim())
    .filter((s) => s.length > 0);
}

function parseCommits(input: string): unknown[] {
  const shas = parseCsv(input);
  return shas.map((sha) => ({ sha, msg: "" }));
}

async function onSubmit() {
  if (!form.value.summary.trim()) {
    toast.push("Summary is required", "error");
    return;
  }
  submitting.value = true;
  const now = new Date().toISOString();
  const created = await sessions.create(props.project.slug, {
    started_at: now,
    ended_at: now,
    summary: form.value.summary.trim(),
    next_step: form.value.next_step.trim() || null,
    files_touched: parseCsv(form.value.files_touched),
    commits: parseCommits(form.value.commits),
    source: "manual",
  });
  submitting.value = false;
  if (created) {
    toast.push("Session logged", "success");
    modalOpen.value = false;
    resetForm();
  } else {
    toast.push("Couldn't log session", "error");
  }
}

function openModal() {
  resetForm();
  modalOpen.value = true;
}

const count = computed(() => sessions.list.length);

function filesArr(s: SessionOut): string[] {
  return Array.isArray(s.files_touched)
    ? s.files_touched.filter((x): x is string => typeof x === "string")
    : [];
}

function commitsArr(s: SessionOut): unknown[] {
  return Array.isArray(s.commits) ? s.commits : [];
}
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-center justify-between mb-4">
      <MonoLabel>sessions
        <span class="ml-2 opacity-60">({{ count }})</span>
      </MonoLabel>
      <button
        type="button"
        class="mono-label hover:text-fg-body transition-colors"
        @click="openModal"
      >+ log session</button>
    </header>

    <div v-if="sessions.loading && count === 0" class="text-small text-fg-muted">loading…</div>
    <div v-else-if="count === 0" class="text-small text-fg-muted italic">
      No sessions logged yet. Claude will auto-log via <code class="font-mono text-fg-body">vibecell.log_session</code> — or add one manually.
    </div>

    <ul v-else class="space-y-0.5">
      <li
        v-for="s in sessions.list"
        :key="s.id"
        class="border-b border-border-subtle last:border-b-0"
      >
        <button
          type="button"
          class="w-full text-left flex items-center gap-3 py-2 hover:bg-bg-surface/40 rounded-sm transition-colors"
          @click="toggleExpand(s.id)"
        >
          <span class="font-mono text-small text-fg-subtle w-20 shrink-0">{{ relTime(s.started_at) }}</span>
          <span aria-hidden="true" class="text-fg-muted">🛠</span>
          <span class="flex-1 text-body text-fg-body truncate">
            {{ s.summary || "(no summary)" }}
          </span>
          <span class="mono-label shrink-0 opacity-60">
            {{ expanded[s.id] ? "▾" : "▸" }}
          </span>
        </button>
        <div v-if="expanded[s.id]" class="pl-[92px] pr-2 pb-3 space-y-2">
          <div v-if="filesArr(s).length > 0">
            <MonoLabel>files touched</MonoLabel>
            <div class="mt-1 flex flex-wrap gap-1.5">
              <span
                v-for="f in filesArr(s)"
                :key="f"
                class="font-mono text-[11px] px-2 py-0.5 rounded-sm"
                :style="{ background: 'var(--signal-blue-bg)', color: 'var(--fg-body)' }"
              >{{ f }}</span>
            </div>
          </div>
          <div v-if="commitsArr(s).length > 0">
            <MonoLabel>commits</MonoLabel>
            <ul class="mt-1 space-y-0.5 font-mono text-small">
              <li v-for="(c, i) in commitsArr(s)" :key="i" class="text-fg-body">
                <span class="text-fg-muted">{{ shortSha(c) }}</span>
                <span class="ml-2">{{ shaMsg(c) }}</span>
              </li>
            </ul>
          </div>
          <div v-if="s.next_step">
            <MonoLabel>next step</MonoLabel>
            <p class="mt-1 text-small text-fg-body italic">{{ s.next_step }}</p>
          </div>
          <div class="text-small text-fg-subtle">
            <span class="font-mono">source:</span> {{ s.source }}
          </div>
        </div>
      </li>
    </ul>

    <Modal :open="modalOpen" title="log session" @close="modalOpen = false">
      <form class="space-y-4" @submit.prevent="onSubmit">
        <TextArea
          v-model="form.summary"
          label="summary (required)"
          placeholder="What did you work on?"
          :rows="3"
        />
        <TextField
          v-model="form.next_step"
          label="next step"
          placeholder="e.g. wire up auth middleware"
        />
        <TextField
          v-model="form.files_touched"
          label="files touched (comma-separated)"
          placeholder="backend/app/main.py, frontend/src/App.vue"
        />
        <TextField
          v-model="form.commits"
          label="commits (comma-separated SHAs)"
          placeholder="abc1234, def5678"
        />
        <div class="flex justify-end gap-3 pt-2">
          <button
            type="button"
            class="mono-label hover:text-fg-body transition-colors"
            @click="modalOpen = false"
          >cancel</button>
          <PrimaryButton type="submit" :loading="submitting">Log session</PrimaryButton>
        </div>
      </form>
    </Modal>
  </section>
</template>
