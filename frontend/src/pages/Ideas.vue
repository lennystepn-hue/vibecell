<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import ProjectOrb from "@/components/ui/ProjectOrb.vue";
import TextArea from "@/components/ui/TextArea.vue";
import { useIdeasStore, type IdeaStatus } from "@/stores/ideas";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";

const ideas = useIdeasStore();
const projects = useProjectsStore();
const toast = useToastStore();

const activeTab = ref<IdeaStatus>("inbox");
const newBody = ref("");
const submitting = ref(false);

const menu = ref<{
  open: boolean;
  x: number;
  y: number;
  ideaId: string | null;
}>({ open: false, x: 0, y: 0, ideaId: null });
const triageSubmenuOpen = ref(false);

onMounted(async () => {
  await Promise.all([projects.fetchList(), ideas.fetchList("inbox")]);
});

async function switchTab(tab: IdeaStatus) {
  activeTab.value = tab;
  await ideas.fetchList(tab);
}

function formatDate(iso: string): string {
  return new Date(iso).toISOString().slice(0, 16).replace("T", " ");
}

async function quickAdd() {
  const body = newBody.value.trim();
  if (!body) return;
  submitting.value = true;
  const created = await ideas.create({ body, source: "web" });
  submitting.value = false;
  if (created) {
    newBody.value = "";
    toast.push("Idea captured", "success");
  } else {
    toast.push("Couldn't save idea", "error");
  }
}

function openMenu(ev: MouseEvent, ideaId: string) {
  ev.preventDefault();
  menu.value = { open: true, x: ev.clientX, y: ev.clientY, ideaId };
  triageSubmenuOpen.value = false;
  const close = () => {
    menu.value = { ...menu.value, open: false };
    document.removeEventListener("click", close);
  };
  setTimeout(() => document.addEventListener("click", close), 0);
}

async function triageTo(slug: string) {
  const id = menu.value.ideaId;
  if (!id) return;
  const project = projects.list.find((p) => p.slug === slug);
  if (!project) return;
  const updated = await ideas.update(id, {
    status: "triaged",
    project_id: project.id,
  });
  if (updated) {
    toast.push(`Triaged → ${project.name}`, "success");
  } else {
    toast.push("Couldn't triage", "error");
  }
  menu.value.open = false;
}

async function discard() {
  const id = menu.value.ideaId;
  if (!id) return;
  const updated = await ideas.update(id, { status: "discarded" });
  if (updated) {
    toast.push("Idea discarded", "success");
  }
  menu.value.open = false;
}

async function removeIdea() {
  const id = menu.value.ideaId;
  if (!id) return;
  const ok = await ideas.remove(id);
  if (ok) {
    toast.push("Idea deleted", "success");
  }
  menu.value.open = false;
}

const tabs: { id: IdeaStatus; label: string }[] = [
  { id: "inbox", label: "inbox" },
  { id: "triaged", label: "triaged" },
  { id: "discarded", label: "discarded" },
];

const currentIdea = computed(() =>
  menu.value.ideaId ? ideas.list.find((i) => i.id === menu.value.ideaId) ?? null : null,
);

function projectNameFor(id: string | null | undefined): string | null {
  if (!id) return null;
  return projects.list.find((p) => p.id === id)?.name ?? null;
}
</script>

<template>
  <div class="max-w-[900px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
    <header class="mb-6">
      <h1 class="text-display text-fg-primary tracking-tight">Ideas</h1>
        <p class="text-body text-fg-muted mt-1">Workspace inbox · capture now, triage later.</p>
      </header>

      <section class="glass rounded-lg p-4 mb-6">
        <TextArea
          v-model="newBody"
          label="capture an idea"
          placeholder="What if… / note to self / feature request"
          :rows="2"
        />
        <div class="flex justify-end mt-3">
          <PrimaryButton :disabled="!newBody.trim()" :loading="submitting" @click="quickAdd">Add to inbox</PrimaryButton>
        </div>
      </section>

      <nav class="flex gap-1 mb-4 border-b border-border-subtle">
        <button
          v-for="t in tabs"
          :key="t.id"
          type="button"
          class="px-4 py-2 mono-label transition-colors"
          :class="activeTab === t.id ? 'text-fg-primary border-b-2 border-signal-green' : 'hover:text-fg-body'"
          @click="switchTab(t.id)"
        >{{ t.label }}</button>
      </nav>

      <div v-if="ideas.loading && ideas.list.length === 0" class="text-fg-muted text-small py-8 text-center">loading…</div>
      <div v-else-if="ideas.list.length === 0" class="text-fg-muted text-small py-12 text-center italic">
        No ideas in <span class="font-mono">{{ activeTab }}</span>.
      </div>

      <ul v-else class="space-y-1">
        <li
          v-for="idea in ideas.list"
          :key="idea.id"
          class="p-3 rounded-md bg-bg-surface hover:bg-bg-surface-hi transition-colors cursor-context-menu"
          @contextmenu="openMenu($event, idea.id)"
        >
          <p class="text-body text-fg-body whitespace-pre-wrap">{{ idea.body }}</p>
          <div class="mt-2 flex items-center gap-3 text-small text-fg-subtle">
            <span class="font-mono text-[10px]">{{ formatDate(idea.captured_at) }}</span>
            <span
              v-if="idea.source"
              class="font-mono text-[9px] uppercase px-1.5 py-0.5 rounded-sm"
              :style="{ background: 'var(--signal-blue-bg)', color: 'var(--fg-body)' }"
            >{{ idea.source }}</span>
            <span v-if="projectNameFor(idea.project_id)" class="text-fg-body">
              → {{ projectNameFor(idea.project_id) }}
            </span>
            <span class="ml-auto opacity-60">right-click for actions</span>
          </div>
        </li>
      </ul>

      <!-- Context menu -->
      <div
        v-if="menu.open"
        class="fixed z-50 glass rounded-md py-1 shadow-modal text-small"
        :style="{ left: `${menu.x}px`, top: `${menu.y}px`, minWidth: '200px' }"
        style="background: var(--bg-chrome); border-color: var(--border-default)"
        @click.stop
      >
        <div class="relative">
          <button
            type="button"
            class="w-full px-3 py-1.5 text-left hover:bg-bg-surface-hi flex items-center justify-between"
            @mouseenter="triageSubmenuOpen = true"
          >
            <span>triage to project</span>
            <span class="text-fg-subtle">▸</span>
          </button>
          <div
            v-if="triageSubmenuOpen"
            class="absolute left-full top-0 ml-1 glass rounded-md py-1 shadow-modal max-h-64 overflow-y-auto"
            :style="{ minWidth: '200px' }"
            style="background: var(--bg-chrome); border-color: var(--border-default)"
          >
            <button
              v-for="p in projects.list"
              :key="p.id"
              type="button"
              class="w-full px-3 py-1.5 text-left hover:bg-bg-surface-hi flex items-center gap-2"
              @click="triageTo(p.slug)"
            >
              <ProjectOrb :seed="p.slug" :size="18" />
              <span class="truncate">{{ p.name }}</span>
              <span class="font-mono text-[10px] text-fg-subtle ml-auto">{{ p.slug }}</span>
            </button>
            <p v-if="projects.list.length === 0" class="px-3 py-2 text-fg-muted italic text-small">No projects</p>
          </div>
        </div>
        <button
          type="button"
          class="w-full px-3 py-1.5 text-left hover:bg-bg-surface-hi text-fg-body"
          @click="discard"
        >discard</button>
        <div class="border-t border-border-subtle my-1"></div>
        <button
          type="button"
          class="w-full px-3 py-1.5 text-left hover:bg-bg-surface-hi text-signal-red"
          @click="removeIdea"
        >delete</button>
        <p class="px-3 pt-1 pb-0.5 text-fg-subtle text-[10px] font-mono">
          {{ currentIdea?.body.slice(0, 40) || '' }}
        </p>
      </div>
    </div>
</template>
