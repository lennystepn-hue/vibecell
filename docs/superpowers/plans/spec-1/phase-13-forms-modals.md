# Phase 13 — Forms & Modals (editing)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Make the dashboard editable. Quick-add modal, inline context editor, status dropdown, and simple add-row CRUD for links + commands.

**Prerequisite:** Phase 12 complete (HEAD ≥ `9c03017`).

---

## Scope

- **Quick-add project modal** at `/p/new` (modal over `/p`)
- **Inline context editor** on `/p/:slug` — click edit → textareas for focus/next/user_wants + open_questions list
- **Status dropdown** — click the pill → pick new status → PATCH
- **Links CRUD inline** — add link form + per-row delete
- **Commands CRUD inline** — add command form + per-row delete
- **Stack + tags** — simple attach (by slug / by name) + detach

Out of this phase (future): rich environment/infra editing UI. The detail page already _reads_ them; editing waits for a Settings-style tab expansion later.

---

## Files

```
frontend/src/
├── components/
│   ├── ui/
│   │   ├── Modal.vue                   Dialog primitive (backdrop + glass + ESC + focus trap)
│   │   ├── TextField.vue               Input wrapper for forms with label + error
│   │   ├── TextArea.vue                matching textarea
│   │   └── SelectField.vue             dropdown select
│   ├── projects/
│   │   ├── QuickAddProject.vue         /p/new modal
│   │   ├── ProjectContextEditor.vue    inline edit over ProjectFocusCard
│   │   ├── ProjectStatusDropdown.vue   overlay on StatusPill
│   │   ├── ProjectLinksEditor.vue      add + delete per row
│   │   ├── ProjectCommandsEditor.vue   add + delete per row
│   │   ├── ProjectStackEditor.vue      attach by slug / detach chips
│   │   └── ProjectTagsEditor.vue       attach by name (creates if missing) / detach
│   └── projects/ProjectLinksCommands.vue  (modify) wire in editors
├── pages/
│   └── ProjectsIndex.vue               (modify) `New project` button opens quick-add
└── pages/ProjectDetail.vue             (modify) show ProjectContextEditor / Stack+Tags editors
```

---

## Task 13.1 — Modal primitive

**File:** `frontend/src/components/ui/Modal.vue`

```vue
<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";

interface Props {
  open: boolean;
  title?: string;
  width?: string;
}
const props = withDefaults(defineProps<Props>(), { width: "520px" });

const emit = defineEmits<{ (e: "close"): void }>();

const dialogRef = ref<HTMLDivElement | null>(null);

function onKey(ev: KeyboardEvent) {
  if (ev.key === "Escape" && props.open) {
    ev.preventDefault();
    emit("close");
  }
}

onMounted(() => document.addEventListener("keydown", onKey));
onUnmounted(() => document.removeEventListener("keydown", onKey));

watch(
  () => props.open,
  (o) => {
    if (o) {
      setTimeout(() => {
        const el = dialogRef.value?.querySelector<HTMLInputElement | HTMLTextAreaElement>(
          "input, textarea, select, button",
        );
        el?.focus();
      }, 30);
    }
  },
);
</script>

<template>
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
      class="fixed inset-0 z-40 flex items-start justify-center pt-[12vh] px-4"
      style="background: var(--bg-overlay)"
      @click.self="emit('close')"
    >
      <div
        ref="dialogRef"
        :style="{ width, maxWidth: '100%' }"
        class="glass rounded-xl overflow-hidden shadow-modal"
        style="background: rgba(13, 18, 26, 0.85); border-color: var(--border-default)"
        role="dialog"
        aria-modal="true"
      >
        <header
          v-if="title"
          class="px-5 h-12 flex items-center border-b border-border-subtle"
        >
          <h2 class="text-section text-fg-primary font-semibold tracking-tight">{{ title }}</h2>
          <button
            type="button"
            class="ml-auto text-fg-muted hover:text-fg-body transition-colors w-7 h-7 flex items-center justify-center rounded-md"
            aria-label="Close"
            @click="emit('close')"
          >✕</button>
        </header>
        <div class="p-5">
          <slot />
        </div>
      </div>
    </div>
  </transition>
</template>
```

Commit: `feat(frontend): Modal primitive with Esc/click-outside + auto-focus`

---

## Task 13.2 — TextField + TextArea + SelectField

**File:** `frontend/src/components/ui/TextField.vue`

```vue
<script setup lang="ts">
interface Props {
  modelValue: string;
  label?: string;
  type?: string;
  placeholder?: string;
  autofocus?: boolean;
  error?: string | null;
  disabled?: boolean;
  required?: boolean;
  id?: string;
}
const props = withDefaults(defineProps<Props>(), {
  type: "text",
  autofocus: false,
  disabled: false,
  required: false,
});
defineEmits<{ (e: "update:modelValue", v: string): void }>();
const id = props.id ?? `tf-${Math.random().toString(36).slice(2, 8)}`;
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" :for="id" class="mono-label">// {{ label }}</label>
    <input
      :id="id"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :autofocus="autofocus"
      :disabled="disabled"
      :required="required"
      :class="[
        'h-10 px-3 rounded-md font-sans text-body bg-bg-surface/60 border',
        error ? 'border-signal-red' : 'border-border',
        'text-fg-primary placeholder:text-fg-subtle',
        'transition-colors duration-fast ease-out hover:bg-bg-surface-hi disabled:opacity-50',
      ]"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="error" class="text-small text-signal-red">{{ error }}</p>
  </div>
</template>
```

**File:** `frontend/src/components/ui/TextArea.vue`

```vue
<script setup lang="ts">
interface Props {
  modelValue: string;
  label?: string;
  placeholder?: string;
  rows?: number;
  error?: string | null;
}
withDefaults(defineProps<Props>(), { rows: 3 });
defineEmits<{ (e: "update:modelValue", v: string): void }>();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" class="mono-label">// {{ label }}</label>
    <textarea
      :value="modelValue"
      :placeholder="placeholder"
      :rows="rows"
      :class="[
        'px-3 py-2 rounded-md font-sans text-body bg-bg-surface/60 border',
        error ? 'border-signal-red' : 'border-border',
        'text-fg-primary placeholder:text-fg-subtle resize-y',
        'transition-colors duration-fast ease-out hover:bg-bg-surface-hi',
      ]"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
    <p v-if="error" class="text-small text-signal-red">{{ error }}</p>
  </div>
</template>
```

**File:** `frontend/src/components/ui/SelectField.vue`

```vue
<script setup lang="ts">
interface Option {
  value: string;
  label: string;
}
interface Props {
  modelValue: string;
  options: Option[];
  label?: string;
}
defineProps<Props>();
defineEmits<{ (e: "update:modelValue", v: string): void }>();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" class="mono-label">// {{ label }}</label>
    <select
      :value="modelValue"
      class="h-10 px-3 rounded-md font-sans text-body bg-bg-surface/60 border border-border text-fg-primary hover:bg-bg-surface-hi transition-colors duration-fast"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
  </div>
</template>
```

Commit: `feat(frontend): form primitives (TextField, TextArea, SelectField)`

---

## Task 13.3 — Quick-add project modal

**File:** `frontend/src/components/projects/QuickAddProject.vue`

```vue
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
```

**Modify** `frontend/src/pages/ProjectsIndex.vue` — replace the `PrimaryButton>+ New project</PrimaryButton>` section to toggle a modal:

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";

import ProjectCard from "@/components/projects/ProjectCard.vue";
import QuickAddProject from "@/components/projects/QuickAddProject.vue";
import EmptyState from "@/components/ui/EmptyState.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useProjectsStore } from "@/stores/projects";

const projects = useProjectsStore();
const quickAddOpen = ref(false);

onMounted(() => projects.fetchList());
</script>

<template>
  <div class="max-w-[1200px] mx-auto px-6 py-8">
    <header class="flex items-baseline justify-between mb-8">
      <div>
        <h1 class="text-display text-fg-primary tracking-tight">Projects</h1>
        <p class="text-fg-muted mt-1">
          <span class="tabular-nums">{{ projects.list.length }}</span> in your hangar
        </p>
      </div>
      <div class="flex gap-2">
        <RouterLink
          to="/import/github"
          class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body border border-border bg-bg-surface/50 text-fg-body hover:bg-bg-surface-hi transition-colors"
        >
          <span aria-hidden="true">↗</span>
          <span>Import from GitHub</span>
        </RouterLink>
        <PrimaryButton @click="quickAddOpen = true">
          <span aria-hidden="true">+</span>
          <span>New project</span>
        </PrimaryButton>
      </div>
    </header>

    <div v-if="projects.loadingList && projects.list.length === 0" class="text-fg-muted">
      <p class="mono-label">loading your projects…</p>
    </div>

    <EmptyState
      v-else-if="projects.list.length === 0"
      title="Your hangar is empty."
      subtitle="Pull in your repos from GitHub or add the first one manually — either works."
    >
      <template #actions>
        <RouterLink
          to="/import/github"
          class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body border border-border bg-bg-surface/50 text-fg-body hover:bg-bg-surface-hi transition-colors"
        >
          Import from GitHub
        </RouterLink>
        <PrimaryButton @click="quickAddOpen = true">+ New project</PrimaryButton>
      </template>
    </EmptyState>

    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <ProjectCard v-for="p in projects.list" :key="p.id" :project="p" />
    </div>

    <QuickAddProject :open="quickAddOpen" @close="quickAddOpen = false" />
  </div>
</template>
```

Commit: `feat(frontend): quick-add project modal with auto-slug + emoji + status`

---

## Task 13.4 — Inline context editor + status dropdown

**File:** `frontend/src/components/projects/ProjectContextEditor.vue`

```vue
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
        <div v-for="(q, i) in open_questions" :key="i" class="flex gap-2 items-start">
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
```

**File:** `frontend/src/components/projects/ProjectStatusDropdown.vue`

```vue
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
```

**Modify** `frontend/src/pages/ProjectDetail.vue` to support context-edit toggle + status dropdown. Replace the `ProjectHero` + `ProjectFocusCard` section with:

```vue
<!-- Above other imports -->
<script setup lang="ts">
// ...existing imports...
import { computed, onMounted, ref, watch } from "vue";

import ProjectContextEditor from "@/components/projects/ProjectContextEditor.vue";
import ProjectStatusDropdown from "@/components/projects/ProjectStatusDropdown.vue";

// ...existing code up to the projects store…

const editingContext = ref(false);
</script>
```

Then inside the template, replace the hero section and focus card:

```vue
<header class="flex items-start gap-4 mb-6">
  <span class="text-[44px] leading-none" aria-hidden="true">
    {{ projects.active.emoji || "📦" }}
  </span>
  <div class="flex-1 min-w-0">
    <div class="flex items-center gap-3 flex-wrap">
      <h1 class="text-display text-fg-primary tracking-tight">{{ projects.active.name }}</h1>
      <ProjectStatusDropdown :project="projects.active" />
    </div>
    <p v-if="projects.active.pitch" class="text-body text-fg-muted mt-2 max-w-3xl">
      {{ projects.active.pitch }}
    </p>
    <p v-else class="mono-label mt-2 opacity-50">// no pitch set</p>
  </div>
  <button
    v-if="!editingContext"
    type="button"
    class="mono-label hover:text-fg-body transition-colors self-start"
    @click="editingContext = true"
  >✎ edit context</button>
</header>

<div class="grid grid-cols-1 xl:grid-cols-3 gap-4">
  <div class="xl:col-span-2">
    <ProjectContextEditor
      v-if="editingContext"
      :project="projects.active"
      @close="editingContext = false"
    />
    <ProjectFocusCard v-else :project="projects.active" />
  </div>
  <ProjectStackCard :project="projects.active" />
  <div class="xl:col-span-2">
    <ProjectInfraCard :project="projects.active" />
  </div>
  <div class="xl:col-span-3">
    <ProjectLinksCommands :project="projects.active" />
  </div>
</div>
```

(Remove the old `<ProjectHero :project="projects.active" />` since we inlined its content; you can delete the old component file if you want.)

Commit: `feat(frontend): inline context editor + status dropdown on project detail`

---

## Task 13.5 — Links/Commands inline CRUD

**Modify** `frontend/src/components/projects/ProjectLinksCommands.vue` — append to the existing file's template the add-row forms at the bottom of each tab, plus a delete icon on each row.

Full replacement:

```vue
<script setup lang="ts">
import { ref } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
const props = defineProps<{ project: Project }>();

const projects = useProjectsStore();
const toast = useToastStore();
const tab = ref<"links" | "commands">("links");

// Link add
const linkUrl = ref("");
const linkKind = ref("");
const linkLabel = ref("");
const addingLink = ref(false);

async function addLink() {
  if (!linkUrl.value.trim()) return;
  addingLink.value = true;
  const { error } = await api.POST("/api/v1/projects/{slug}/links", {
    params: { path: { slug: props.project.slug } },
    body: {
      url: linkUrl.value.trim(),
      kind: linkKind.value.trim() || null,
      label: linkLabel.value.trim() || null,
    },
  });
  addingLink.value = false;
  if (error) {
    toast.push("Failed to add link", "error");
    return;
  }
  linkUrl.value = linkKind.value = linkLabel.value = "";
  await projects.fetchProject(props.project.slug);
}

async function deleteLink(linkId: string) {
  const { error } = await api.DELETE("/api/v1/projects/{slug}/links/{link_id}", {
    params: { path: { slug: props.project.slug, link_id: linkId } },
  });
  if (error) {
    toast.push("Failed to delete link", "error");
    return;
  }
  await projects.fetchProject(props.project.slug);
}

// Command add
const cmdLabel = ref("");
const cmdCommand = ref("");
const cmdRunIn = ref<"terminal" | "background">("terminal");
const addingCmd = ref(false);

async function addCommand() {
  if (!cmdLabel.value.trim() || !cmdCommand.value.trim()) return;
  addingCmd.value = true;
  const { error } = await api.POST("/api/v1/projects/{slug}/commands", {
    params: { path: { slug: props.project.slug } },
    body: {
      label: cmdLabel.value.trim(),
      command: cmdCommand.value.trim(),
      run_in: cmdRunIn.value,
      confirm_required: 1,
    },
  });
  addingCmd.value = false;
  if (error) {
    toast.push("Failed to add command", "error");
    return;
  }
  cmdLabel.value = cmdCommand.value = "";
  cmdRunIn.value = "terminal";
  await projects.fetchProject(props.project.slug);
}

async function deleteCommand(cmdId: string) {
  const { error } = await api.DELETE("/api/v1/projects/{slug}/commands/{cmd_id}", {
    params: { path: { slug: props.project.slug, cmd_id: cmdId } },
  });
  if (error) {
    toast.push("Failed to delete command", "error");
    return;
  }
  await projects.fetchProject(props.project.slug);
}
</script>

<template>
  <section class="glass rounded-lg p-0 overflow-hidden">
    <div class="flex border-b border-border-subtle">
      <button
        :class="[
          'flex-1 h-10 px-5 text-left mono-label transition-colors duration-fast',
          tab === 'links' ? 'text-fg-primary bg-bg-surface/40' : 'hover:text-fg-body',
        ]"
        @click="tab = 'links'"
      >
        links <span class="ml-1 tabular-nums opacity-60">{{ project.links.length }}</span>
      </button>
      <button
        :class="[
          'flex-1 h-10 px-5 text-left mono-label transition-colors duration-fast',
          tab === 'commands' ? 'text-fg-primary bg-bg-surface/40' : 'hover:text-fg-body',
        ]"
        @click="tab = 'commands'"
      >
        commands <span class="ml-1 tabular-nums opacity-60">{{ project.commands.length }}</span>
      </button>
    </div>

    <div v-if="tab === 'links'" class="p-5 space-y-4">
      <ul v-if="project.links.length > 0" class="space-y-2">
        <li v-for="l in project.links" :key="l.id" class="flex items-center gap-3 group">
          <span class="mono-label w-14 shrink-0 text-right">{{ l.kind || "link" }}</span>
          <a :href="l.url" target="_blank" rel="noopener" class="link text-body flex-1 truncate">
            {{ l.label || l.url }}
            <span class="text-fg-subtle ml-1" aria-hidden="true">↗</span>
          </a>
          <button
            type="button"
            class="opacity-0 group-hover:opacity-100 text-fg-muted hover:text-signal-red transition-all"
            aria-label="Delete link"
            @click="deleteLink(l.id)"
          >✕</button>
        </li>
      </ul>

      <form
        class="flex gap-2 pt-2 border-t border-border-subtle"
        @submit.prevent="addLink"
      >
        <input
          v-model="linkKind"
          type="text"
          placeholder="kind"
          class="w-20 h-9 px-2 rounded-md font-mono text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
        />
        <input
          v-model="linkLabel"
          type="text"
          placeholder="label (opt)"
          class="w-32 h-9 px-2 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
        />
        <input
          v-model="linkUrl"
          type="url"
          placeholder="https://…"
          class="flex-1 h-9 px-2 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
        />
        <button
          type="submit"
          :disabled="!linkUrl || addingLink"
          class="h-9 px-3 rounded-md font-medium text-small disabled:opacity-50"
          :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
        >add</button>
      </form>
    </div>

    <div v-else class="p-5 space-y-4">
      <ul v-if="project.commands.length > 0" class="space-y-2">
        <li
          v-for="c in project.commands"
          :key="c.id"
          class="flex flex-col gap-1 p-3 rounded-md border border-border-subtle group"
        >
          <div class="flex items-center gap-2">
            <MonoLabel>{{ c.run_in }}</MonoLabel>
            <span class="text-section font-semibold text-fg-primary">{{ c.label }}</span>
            <button
              type="button"
              class="ml-auto opacity-0 group-hover:opacity-100 text-fg-muted hover:text-signal-red transition-all"
              aria-label="Delete command"
              @click="deleteCommand(c.id)"
            >✕</button>
          </div>
          <code class="font-mono text-small text-fg-muted truncate">{{ c.command }}</code>
        </li>
      </ul>

      <form class="space-y-2 pt-2 border-t border-border-subtle" @submit.prevent="addCommand">
        <div class="flex gap-2">
          <input
            v-model="cmdLabel"
            type="text"
            placeholder="label (e.g. Deploy)"
            class="flex-1 h-9 px-2 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
          />
          <select
            v-model="cmdRunIn"
            class="w-32 h-9 px-2 rounded-md font-mono text-small bg-bg-surface/60 border border-border text-fg-body"
          >
            <option value="terminal">terminal</option>
            <option value="background">background</option>
          </select>
        </div>
        <div class="flex gap-2">
          <input
            v-model="cmdCommand"
            type="text"
            placeholder="$ command to run"
            class="flex-1 h-9 px-2 rounded-md font-mono text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
          />
          <button
            type="submit"
            :disabled="!cmdLabel || !cmdCommand || addingCmd"
            class="h-9 px-3 rounded-md font-medium text-small disabled:opacity-50"
            :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
          >add</button>
        </div>
      </form>

      <p class="mono-label opacity-50">// execution lands in the CLI phase (spec 3)</p>
    </div>
  </section>
</template>
```

Commit: `feat(frontend): inline links + commands CRUD on project detail`

---

## Task 13.6 — Stack + Tags editors

**File:** `frontend/src/components/projects/ProjectStackEditor.vue`

```vue
<script setup lang="ts">
import { computed, ref, watch } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import { api } from "@/api/client";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
type StackItem = components["schemas"]["StackItemOut"];
const props = defineProps<{ project: Project }>();

const projects = useProjectsStore();
const toast = useToastStore();

const query = ref("");
const results = ref<StackItem[]>([]);
const highlightedIndex = ref(0);
const searching = ref(false);

const attachedSlugs = computed(() => new Set(props.project.stack.map((s) => s.stack_item_slug)));
const filteredResults = computed(() => results.value.filter((r) => !attachedSlugs.value.has(r.slug)));

let searchTimer: ReturnType<typeof setTimeout> | null = null;
watch(query, (q) => {
  if (searchTimer) clearTimeout(searchTimer);
  if (!q.trim()) {
    results.value = [];
    return;
  }
  searchTimer = setTimeout(async () => {
    searching.value = true;
    const { data } = await api.GET("/api/v1/stack-items", {
      params: { query: { q, limit: 10 } },
    });
    searching.value = false;
    results.value = data ?? [];
    highlightedIndex.value = 0;
  }, 150);
});

async function attach(item: StackItem) {
  const { error } = await api.POST("/api/v1/projects/{slug}/stack", {
    params: { path: { slug: props.project.slug } },
    body: { stack_item_slug: item.slug, role: null },
  });
  if (error) {
    toast.push(`Couldn't attach ${item.slug}`, "error");
    return;
  }
  query.value = "";
  results.value = [];
  await projects.fetchProject(props.project.slug);
}

async function detach(slug: string) {
  const { error } = await api.DELETE("/api/v1/projects/{slug}/stack/{stack_item_slug}", {
    params: { path: { slug: props.project.slug, stack_item_slug: slug } },
  });
  if (error) {
    toast.push(`Couldn't remove ${slug}`, "error");
    return;
  }
  await projects.fetchProject(props.project.slug);
}
</script>

<template>
  <section class="glass rounded-lg p-5">
    <MonoLabel>stack</MonoLabel>

    <div class="flex flex-wrap gap-2 mt-3">
      <span
        v-for="s in project.stack"
        :key="s.stack_item_slug"
        class="group inline-flex items-center gap-1.5 px-2.5 h-6 rounded-sm font-mono text-[11px]"
        :style="{ background: 'var(--signal-blue-bg)', color: 'var(--fg-body)', border: '1px solid var(--border-subtle)' }"
      >
        {{ s.name }}
        <button
          type="button"
          class="opacity-0 group-hover:opacity-100 text-fg-subtle hover:text-signal-red transition-all"
          aria-label="Detach"
          @click="detach(s.stack_item_slug)"
        >✕</button>
      </span>
    </div>

    <div class="relative mt-3">
      <input
        v-model="query"
        type="text"
        placeholder="+ add framework, service, model…"
        class="w-full h-9 px-3 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
      />
      <div
        v-if="filteredResults.length > 0"
        class="absolute left-0 right-0 top-full mt-1 glass rounded-md overflow-hidden z-10 max-h-60 overflow-y-auto"
        style="background: rgba(13, 18, 26, 0.95)"
      >
        <button
          v-for="(item, i) in filteredResults"
          :key="item.slug"
          type="button"
          :class="[
            'w-full px-3 py-1.5 text-left flex items-center justify-between gap-3',
            i === highlightedIndex ? 'bg-bg-surface-hi' : 'hover:bg-bg-surface/60',
          ]"
          @click="attach(item)"
          @mouseenter="highlightedIndex = i"
        >
          <span>{{ item.name }}</span>
          <span class="mono text-[10px] text-fg-muted">{{ item.kind ?? "—" }}</span>
        </button>
      </div>
    </div>
  </section>
</template>
```

**File:** `frontend/src/components/projects/ProjectTagsEditor.vue`

```vue
<script setup lang="ts">
import { ref } from "vue";

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

    <form class="flex gap-2 mt-3" @submit.prevent="addTag">
      <input
        v-model="newTag"
        type="text"
        placeholder="+ tag"
        class="flex-1 h-9 px-3 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
      />
      <button
        type="submit"
        :disabled="!newTag.trim()"
        class="h-9 px-3 rounded-md font-medium text-small disabled:opacity-50"
        :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
      >add</button>
    </form>
  </section>
</template>
```

**Modify** `ProjectDetail.vue` — replace `<ProjectStackCard :project="projects.active" />` with `<ProjectStackEditor :project="projects.active" />`, and add `<ProjectTagsEditor :project="projects.active" />` below (spans 1 column in the xl grid).

Update imports in `ProjectDetail.vue`:
```vue
import ProjectStackEditor from "@/components/projects/ProjectStackEditor.vue";
import ProjectTagsEditor from "@/components/projects/ProjectTagsEditor.vue";
```

Layout snippet:
```vue
<ProjectStackEditor :project="projects.active" />
<div class="xl:col-span-2">
  <ProjectInfraCard :project="projects.active" />
</div>
<ProjectTagsEditor :project="projects.active" />
<div class="xl:col-span-3">
  <ProjectLinksCommands :project="projects.active" />
</div>
```

Commit: `feat(frontend): stack + tags editors with autocomplete + inline attach/detach`

---

## Task 13.7 — Smoke tests

Add a quick QuickAddProject test.

**File:** `frontend/src/components/projects/__tests__/QuickAddProject.spec.ts`

```ts
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount, flushPromises } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import QuickAddProject from "../QuickAddProject.vue";
import { useProjectsStore } from "@/stores/projects";

function makeRouter() {
  return createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/p", name: "p", component: { template: "<div/>" } },
      { path: "/p/:slug", name: "pd", component: { template: "<div/>" } },
    ],
  });
}

describe("QuickAddProject", () => {
  beforeEach(() => setActivePinia(createPinia()));

  it("renders when open and auto-slugs from name", async () => {
    const wrapper = mount(QuickAddProject, {
      props: { open: true },
      global: { plugins: [makeRouter()] },
    });
    await flushPromises();
    const nameInput = wrapper.find<HTMLInputElement>('input[placeholder="Butlr"]');
    await nameInput.setValue("My Shiny Project");
    // slug should auto-fill
    const slugInput = wrapper.find<HTMLInputElement>('input[placeholder="butlr"]');
    expect(slugInput.element.value).toBe("my-shiny-project");
  });

  it("emits close on cancel", async () => {
    const wrapper = mount(QuickAddProject, {
      props: { open: true },
      global: { plugins: [makeRouter()] },
    });
    await flushPromises();
    const ps = useProjectsStore();
    vi.spyOn(ps, "fetchList").mockResolvedValue();
    const cancel = wrapper.findAll("button").find((b) => b.text() === "Cancel");
    expect(cancel).toBeTruthy();
    await cancel!.trigger("click");
    expect(wrapper.emitted("close")).toBeTruthy();
  });
});
```

Commit: `test(frontend): QuickAddProject smoke tests (auto-slug + cancel emit)`

---

## Phase 13 complete when

- [ ] Clicking "New project" opens quick-add modal; creating navigates to new project.
- [ ] Status pill on project detail opens a dropdown with 7 options; clicking a status PATCHes.
- [ ] "✎ edit context" toggles a form over the focus card; save PATCHes.
- [ ] Links/commands tabs have add-row forms and delete-on-hover per row.
- [ ] Stack editor autocomplete searches `/stack-items` and attach/detach works.
- [ ] Tags editor adds by name (creates if missing) and removes by id.
- [ ] `pnpm typecheck` + `pnpm test --run` + `pnpm build` all green.
- [ ] 7 commits on main (13.1–13.7).
