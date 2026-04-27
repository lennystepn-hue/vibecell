<script setup lang="ts">
import { computed, ref, watch } from "vue";

import Modal from "@/components/ui/Modal.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import TextArea from "@/components/ui/TextArea.vue";
import TextField from "@/components/ui/TextField.vue";
import { useSessionsStore } from "@/stores/sessions";
import { useShipsStore } from "@/stores/ships";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];

const props = defineProps<{ project: Project }>();
const ships = useShipsStore();
const sessions = useSessionsStore();
const toast = useToastStore();

const open = ref(false);
const submitting = ref(false);

const form = ref({
  version: "",
  summary: "",
  changelog_md: "",
});

// On project change, load ships in background so "last ship" math works.
watch(
  () => props.project.slug,
  (slug) => {
    void ships.fetchList(slug);
  },
  { immediate: true },
);

const lastShipAt = computed<string | null>(() => {
  if (ships.list.length === 0) return null;
  // API returns newest first; fall back to sort just in case.
  const sorted = [...ships.list].sort(
    (a, b) => new Date(b.shipped_at).getTime() - new Date(a.shipped_at).getTime(),
  );
  return sorted[0]?.shipped_at ?? null;
});

const autoChangelog = computed<string>(() => {
  const last = lastShipAt.value;
  const candidates = sessions.list.filter((s) => !last || s.started_at > last);
  return candidates
    .filter((s) => (s.summary ?? "").trim().length > 0)
    .map((s) => `- ${s.summary}`)
    .join("\n");
});

const liveUrl = computed<string | null>(() => {
  const prod = props.project.environments.find((e) => e.kind === "prod");
  return prod?.url ?? props.project.environments[0]?.url ?? null;
});

const projectAgeDays = computed<number>(() => {
  // Use oldest session.started_at as a best-effort "project creation" proxy.
  if (sessions.list.length === 0) return 0;
  const sorted = [...sessions.list].sort(
    (a, b) => new Date(a.started_at).getTime() - new Date(b.started_at).getTime(),
  );
  const first = sorted[0];
  if (!first) return 0;
  const diff = Date.now() - new Date(first.started_at).getTime();
  return Math.max(1, Math.floor(diff / (1000 * 60 * 60 * 24)));
});

const tweetDrafts = computed<string[]>(() => {
  const name = props.project.name;
  const v = form.value.version || "v0.1.0";
  const summary = form.value.summary || (props.project.pitch ?? "new update");
  const bullets = (form.value.changelog_md || autoChangelog.value).slice(0, 240);
  const url = liveUrl.value ?? `https://vibecell.dev/p/${props.project.slug}`;
  return [
    `Shipped ${v} of ${name}: ${summary}. Try it at ${url}`,
    `${name} ${v} is out. Here's what's new:\n${bullets}`,
    `After ${projectAgeDays.value} days building ${name}, shipping ${v} today. ${props.project.pitch ?? ""}`.trim(),
  ];
});

function openModal() {
  form.value = {
    version: "",
    summary: "",
    changelog_md: autoChangelog.value,
  };
  open.value = true;
  // Refresh sessions list so auto-changelog is current.
  void sessions.fetchList(props.project.slug);
}

watch(
  () => autoChangelog.value,
  (val) => {
    // Only overwrite if user hasn't typed anything yet.
    if (open.value && form.value.changelog_md.trim().length === 0) {
      form.value.changelog_md = val;
    }
  },
);

async function copy(text: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.push("Copied to clipboard", "success");
  } catch {
    toast.push("Copy failed", "error");
  }
}

async function onSubmit() {
  submitting.value = true;
  const created = await ships.create(props.project.slug, {
    shipped_at: new Date().toISOString(),
    version: form.value.version.trim() || null,
    summary: form.value.summary.trim() || null,
    changelog_md: form.value.changelog_md.trim() || null,
  });
  submitting.value = false;
  if (created) {
    toast.push(`Shipped ${created.version ?? "new version"}!`, "success");
    open.value = false;
  } else {
    toast.push("Couldn't record ship", "error");
  }
}
</script>

<template>
  <button
    type="button"
    class="mono-label hover:text-signal-green transition-colors"
    @click="openModal"
  >↑ ship it</button>

  <Modal :open="open" title="ship it" width="640px" @close="open = false">
    <form class="space-y-4" @submit.prevent="onSubmit">
      <div class="grid grid-cols-2 gap-3">
        <TextField v-model="form.version" label="version" placeholder="v0.2.0" />
        <TextField v-model="form.summary" label="summary" placeholder="One-line description" />
      </div>

      <TextArea
        v-model="form.changelog_md"
        label="changelog (markdown — auto-filled from sessions since last ship)"
        :rows="6"
        placeholder="- ..."
      />

      <div>
        <MonoLabel>tweet drafts
          <span class="opacity-60">(click to copy)</span>
        </MonoLabel>
        <ul class="mt-2 space-y-2">
          <li
            v-for="(draft, i) in tweetDrafts"
            :key="i"
            class="p-3 rounded-md bg-bg-surface border border-border-subtle text-small text-fg-body cursor-pointer hover:bg-bg-surface-hi transition-colors whitespace-pre-wrap"
            :title="`Copy draft ${i + 1}`"
            @click="copy(draft)"
          >
            <span class="mono-label opacity-60 mr-2">{{ ['announce', 'whatsnew', 'reflect'][i] }}</span>
            {{ draft }}
          </li>
        </ul>
      </div>

      <div class="flex justify-end gap-3 pt-2">
        <button
          type="button"
          class="mono-label hover:text-fg-body transition-colors"
          @click="open = false"
        >cancel</button>
        <PrimaryButton type="submit" :loading="submitting">Record ship</PrimaryButton>
      </div>
    </form>
  </Modal>
</template>
