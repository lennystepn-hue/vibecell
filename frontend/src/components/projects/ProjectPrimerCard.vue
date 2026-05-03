<script setup lang="ts">
/**
 * ProjectPrimerCard — long-form per-project README aimed at AIs joining cold.
 *
 * Two visual modes:
 *   • View   — pre-wrap rendered text + Copy + Edit buttons. Empty state
 *              when no primer is set yet, with a single CTA to "Write one".
 *   • Edit   — textarea, debounced auto-save (PATCH /projects/{slug} with
 *              just primer_md), Save / Cancel.
 *
 * The editor doesn't render Markdown to HTML — that'd require a renderer
 * dependency we don't otherwise need. Plain pre-wrap with a monospace
 * font is enough for the use case (the AI parses Markdown anyway, and the
 * user is reading their own writing).
 */
import { computed, onMounted, ref, watch } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { api } from "@/api/client";
import type { components } from "@/api/types.gen";
import { useProjectsStore } from "@/stores/projects";
import { useToastStore } from "@/stores/toast";

// ProjectFullOut grew a primer_md field server-side; the generated OpenAPI
// types lag behind a deploy, so layer the property in by hand.
type Project = components["schemas"]["ProjectFullOut"] & {
  primer_md?: string | null;
};

const props = defineProps<{ project: Project }>();
const projects = useProjectsStore();
const toast = useToastStore();

const editing = ref(false);
const draft = ref("");
const saving = ref(false);
const justCopied = ref(false);

const primer = computed<string>(() => (props.project.primer_md ?? "").trimEnd());
const hasPrimer = computed(() => primer.value.length > 0);
const charCount = computed(() => draft.value.length);
const PRIMER_MAX = 51200;

function startEdit() {
  draft.value = primer.value;
  editing.value = true;
}

function cancelEdit() {
  editing.value = false;
  draft.value = "";
}

async function save() {
  if (saving.value) return;
  saving.value = true;
  const { data, error } = await api.PATCH("/api/v1/projects/{slug}", {
    params: { path: { slug: props.project.slug } },
    body: { primer_md: draft.value } as Record<string, unknown>,
  });
  saving.value = false;
  if (error || !data) {
    toast.push("Couldn't save primer", "error");
    return;
  }
  // Push the new value into the projects store so other consumers (e.g.
  // header / telemetry rail / any other PrimerCard instance) re-render
  // without a refetch.
  if (projects.active && projects.active.slug === props.project.slug) {
    (projects.active as Record<string, unknown>).primer_md = draft.value;
  }
  editing.value = false;
  toast.push("Primer saved", "success");
}

async function copyToClipboard() {
  if (!hasPrimer.value) return;
  try {
    await navigator.clipboard.writeText(primer.value);
    justCopied.value = true;
    setTimeout(() => {
      justCopied.value = false;
    }, 1800);
  } catch {
    /* clipboard denied — user can still select the text manually */
  }
}

// If the user navigates between projects while the editor is open, drop
// the half-edited draft so we don't accidentally PATCH the new project
// with the old project's primer text.
watch(
  () => props.project.slug,
  () => {
    editing.value = false;
    draft.value = "";
  },
);

onMounted(() => {
  /* nothing — the parent already loaded ProjectFullOut */
});
</script>

<template>
  <section class="glass rounded-lg p-5 flex flex-col h-full min-h-0">
    <header class="flex items-center justify-between mb-3 select-none">
      <h3 class="mono-label text-fg-muted">
        //primer
        <span v-if="hasPrimer" class="opacity-60">({{ primer.length.toLocaleString() }} chars)</span>
      </h3>
      <div class="flex items-center gap-3">
        <button
          v-if="hasPrimer && !editing"
          type="button"
          class="mono-label text-fg-muted hover:text-fg-body transition-colors"
          @click="copyToClipboard"
        >{{ justCopied ? "✓ copied" : "copy" }}</button>
        <button
          v-if="!editing"
          type="button"
          class="mono-label text-fg-muted hover:text-fg-body transition-colors"
          @click="startEdit"
        >{{ hasPrimer ? "✎ edit" : "+ write one" }}</button>
      </div>
    </header>

    <!-- ── EDIT MODE ────────────────────────────────────────────────── -->
    <div v-if="editing" class="flex flex-col gap-3 flex-1 min-h-0">
      <textarea
        v-model="draft"
        :maxlength="PRIMER_MAX"
        :disabled="saving"
        rows="14"
        placeholder="# Project primer&#10;&#10;Write the README an AI joining your project should read first.&#10;&#10;## What this is&#10;## How it's built&#10;## Conventions&#10;## Watch out for&#10;## Where things live"
        class="flex-1 min-h-[260px] w-full px-3 py-2 rounded-md font-mono text-small bg-bg-surface border border-border text-fg-primary placeholder:text-fg-subtle resize-y leading-relaxed"
      />
      <div class="flex items-center justify-between">
        <span class="font-mono text-[10px] text-fg-subtle">
          {{ charCount.toLocaleString() }} / {{ PRIMER_MAX.toLocaleString() }} chars
        </span>
        <div class="flex items-center gap-2">
          <button
            type="button"
            class="mono-label text-fg-muted hover:text-fg-body transition-colors"
            :disabled="saving"
            @click="cancelEdit"
          >cancel</button>
          <PrimaryButton :loading="saving" :disabled="saving" @click="save">
            Save primer
          </PrimaryButton>
        </div>
      </div>
    </div>

    <!-- ── VIEW MODE / EMPTY STATE ──────────────────────────────────── -->
    <div v-else-if="hasPrimer" class="flex-1 min-h-0 overflow-y-auto">
      <pre
        class="whitespace-pre-wrap break-words font-mono text-small leading-relaxed text-fg-body"
      >{{ primer }}</pre>
    </div>

    <div v-else class="flex-1 min-h-0 flex flex-col items-start justify-start gap-3">
      <MonoLabel>// no primer yet</MonoLabel>
      <p class="text-small text-fg-muted leading-relaxed max-w-prose">
        The primer is your project's README for AIs. Cover what this is, how
        it's structured, what conventions to follow, and which gotchas to
        watch out for. Claude can fetch it via the
        <code class="font-mono text-fg-body">vibecell_primer</code> MCP tool
        on every session start — instant onboarding for any AI in any editor.
      </p>
      <button
        type="button"
        class="mt-1 inline-flex items-center gap-2 px-4 py-2 rounded-md text-small font-mono"
        :style="{
          background: 'var(--signal-green-bg)',
          color: 'var(--signal-green)',
          border: '1px solid var(--signal-green)',
        }"
        @click="startEdit"
      >
        <span aria-hidden="true">+</span>
        <span>Write the primer</span>
      </button>
    </div>
  </section>
</template>
