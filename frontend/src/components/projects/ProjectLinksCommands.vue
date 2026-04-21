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
const tab = ref<"links" | "commands">("links");

// Link add
const linkUrl = ref("");
const linkKind = ref("");
const linkLabel = ref("");
const addingLink = ref(false);
const showLinkForm = ref(false);
const linkUrlRef = ref<HTMLInputElement | null>(null);

function openLinkForm() {
  showLinkForm.value = true;
  nextTick(() => linkUrlRef.value?.focus());
}

function cancelLinkForm() {
  showLinkForm.value = false;
  linkUrl.value = linkKind.value = linkLabel.value = "";
}

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
  showLinkForm.value = false;
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
const showCmdForm = ref(false);
const cmdLabelRef = ref<HTMLInputElement | null>(null);

function openCmdForm() {
  showCmdForm.value = true;
  nextTick(() => cmdLabelRef.value?.focus());
}

function cancelCmdForm() {
  showCmdForm.value = false;
  cmdLabel.value = cmdCommand.value = "";
  cmdRunIn.value = "terminal";
}

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
  showCmdForm.value = false;
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
      <!-- Bug 2 fix: shrink-0 w-[92px] on kind column, min-w-0 flex-1 on value column -->
      <ul v-if="project.links.length > 0" class="space-y-2">
        <li v-for="l in project.links" :key="l.id" class="flex items-center gap-3 group">
          <span class="mono-label shrink-0 w-[92px] text-right truncate">{{ l.kind || "link" }}</span>
          <a :href="l.url" target="_blank" rel="noopener" class="link text-body min-w-0 flex-1 truncate">
            {{ l.label || l.url }}
            <span class="text-fg-subtle ml-1" aria-hidden="true">↗</span>
          </a>
          <button
            type="button"
            class="opacity-0 group-hover:opacity-100 text-fg-muted hover:text-signal-red transition-all shrink-0"
            aria-label="Delete link"
            @click="deleteLink(l.id)"
          >✕</button>
        </li>
      </ul>

      <!-- Inline add form (shown on demand) -->
      <form
        v-if="showLinkForm"
        class="flex flex-wrap gap-2 pt-2 border-t border-border-subtle"
        @submit.prevent="addLink"
      >
        <input
          v-model="linkKind"
          type="text"
          placeholder="kind"
          class="w-20 h-9 px-2 rounded-md font-mono text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
          @keydown.esc="cancelLinkForm"
        />
        <input
          v-model="linkLabel"
          type="text"
          placeholder="label (opt)"
          class="w-32 h-9 px-2 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
          @keydown.esc="cancelLinkForm"
        />
        <input
          ref="linkUrlRef"
          v-model="linkUrl"
          type="url"
          placeholder="https://…"
          class="flex-1 h-9 px-2 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
          @keydown.esc="cancelLinkForm"
        />
        <button
          type="submit"
          :disabled="!linkUrl || addingLink"
          class="h-9 px-3 rounded-md font-medium text-small disabled:opacity-50"
          :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
        >add</button>
      </form>

      <!-- Trigger button -->
      <button
        v-else
        type="button"
        class="mono-label text-fg-subtle hover:text-fg-body transition-colors"
        @click="openLinkForm"
      >+ add link</button>
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

      <!-- Inline add form (shown on demand) -->
      <form
        v-if="showCmdForm"
        class="space-y-2 pt-2 border-t border-border-subtle"
        @submit.prevent="addCommand"
      >
        <div class="flex gap-2">
          <input
            ref="cmdLabelRef"
            v-model="cmdLabel"
            type="text"
            placeholder="label (e.g. Deploy)"
            class="flex-1 h-9 px-2 rounded-md font-sans text-small bg-bg-surface/60 border border-border text-fg-body placeholder:text-fg-subtle"
            @keydown.esc="cancelCmdForm"
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
            @keydown.esc="cancelCmdForm"
          />
          <button
            type="submit"
            :disabled="!cmdLabel || !cmdCommand || addingCmd"
            class="h-9 px-3 rounded-md font-medium text-small disabled:opacity-50"
            :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
          >add</button>
        </div>
      </form>

      <!-- Trigger button -->
      <button
        v-else
        type="button"
        class="mono-label text-fg-subtle hover:text-fg-body transition-colors"
        @click="openCmdForm"
      >+ add command</button>

      <p class="mono-label opacity-50">// execution lands in the CLI phase (spec 3)</p>
    </div>
  </section>
</template>
