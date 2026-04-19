<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import TextField from "@/components/ui/TextField.vue";
import { useLaunchesStore } from "@/stores/launches";
import { useShipsStore } from "@/stores/ships";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
type LaunchOut = components["schemas"]["LaunchOut"];

type Platform = "ph" | "hn" | "x" | "reddit" | "newsletter" | "other";

const props = defineProps<{ project: Project }>();
const launches = useLaunchesStore();
const ships = useShipsStore();
const toast = useToastStore();

const editing = ref(false);
const submitting = ref(false);

const form = ref<{ platform: Platform; url: string; launched_at: string }>({
  platform: "ph",
  url: "",
  launched_at: new Date().toISOString().slice(0, 10),
});

function reload() {
  void launches.fetchList(props.project.slug);
  void ships.fetchList(props.project.slug);
}

onMounted(reload);
watch(() => props.project.slug, reload);

const platformLabels: Record<Platform, string> = {
  ph: "Product Hunt",
  hn: "Hacker News",
  x: "X",
  reddit: "Reddit",
  newsletter: "Newsletter",
  other: "Other",
};

function fmtDate(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}

function metricsKeys(l: LaunchOut): [string, unknown][] {
  return Object.entries(l.metrics ?? {});
}

async function onSubmit() {
  submitting.value = true;
  const iso = new Date(form.value.launched_at).toISOString();
  const created = await launches.create(props.project.slug, {
    platform: form.value.platform,
    launched_at: iso,
    url: form.value.url.trim() || null,
    metrics: {},
  });
  submitting.value = false;
  if (created) {
    toast.push(`Launch recorded on ${platformLabels[form.value.platform]}`, "success");
    editing.value = false;
    form.value.url = "";
  } else {
    toast.push("Couldn't record launch", "error");
  }
}

const count = computed(() => launches.list.length);
const shipsCount = computed(() => ships.list.length);
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-center justify-between mb-4">
      <MonoLabel>ships + launches
        <span class="ml-2 opacity-60">({{ shipsCount }} ships · {{ count }} launches)</span>
      </MonoLabel>
      <button
        v-if="!editing"
        type="button"
        class="mono-label hover:text-fg-body transition-colors"
        @click="editing = true"
      >+ record launch</button>
    </header>

    <form v-if="editing" class="mb-5 p-4 rounded-md bg-bg-surface/40 space-y-3" @submit.prevent="onSubmit">
      <div class="grid grid-cols-3 gap-3">
        <div>
          <label class="mono-label">// platform</label>
          <select
            v-model="form.platform"
            class="h-10 mt-1 w-full px-3 rounded-md font-sans text-body bg-bg-surface/60 border border-border text-fg-primary"
          >
            <option value="ph">Product Hunt</option>
            <option value="hn">Hacker News</option>
            <option value="x">X</option>
            <option value="reddit">Reddit</option>
            <option value="newsletter">Newsletter</option>
            <option value="other">Other</option>
          </select>
        </div>
        <TextField v-model="form.launched_at" label="launched at" type="date" />
        <TextField v-model="form.url" label="url" placeholder="https://…" />
      </div>
      <div class="flex justify-end gap-3">
        <button
          type="button"
          class="mono-label hover:text-fg-body transition-colors"
          @click="editing = false"
        >cancel</button>
        <PrimaryButton type="submit" :loading="submitting">Record launch</PrimaryButton>
      </div>
    </form>

    <div v-if="shipsCount > 0" class="mb-5">
      <MonoLabel>ships</MonoLabel>
      <ul class="mt-2 space-y-1">
        <li
          v-for="s in ships.list"
          :key="s.id"
          class="flex items-center gap-3 text-small py-1.5 border-b border-border-subtle last:border-b-0"
        >
          <span class="font-mono text-fg-primary w-20 shrink-0">{{ s.version || '—' }}</span>
          <span class="text-fg-subtle font-mono text-[10px] w-20 shrink-0">{{ fmtDate(s.shipped_at) }}</span>
          <span class="flex-1 text-fg-body truncate">{{ s.summary || '(no summary)' }}</span>
        </li>
      </ul>
    </div>

    <div>
      <MonoLabel>launches</MonoLabel>
      <p v-if="count === 0" class="text-small text-fg-muted italic mt-2">
        No launches recorded yet. Track Product Hunt / HN / X / Reddit launches here.
      </p>
      <ul v-else class="mt-2 space-y-1">
        <li
          v-for="l in launches.list"
          :key="l.id"
          class="flex items-center gap-3 text-small py-1.5 border-b border-border-subtle last:border-b-0"
        >
          <span
            class="font-mono text-[10px] uppercase px-2 py-0.5 rounded-sm w-28 shrink-0 text-center"
            :style="{ background: 'var(--signal-blue-bg)', color: 'var(--fg-body)' }"
          >{{ platformLabels[(l.platform as Platform)] || l.platform }}</span>
          <span class="text-fg-subtle font-mono text-[10px] w-20 shrink-0">{{ fmtDate(l.launched_at) }}</span>
          <a
            v-if="l.url"
            :href="l.url"
            target="_blank"
            rel="noopener"
            class="link flex-1 truncate"
          >{{ l.url }}</a>
          <span v-else class="flex-1 text-fg-subtle italic">no url</span>
          <div class="flex gap-2 shrink-0 text-[10px] text-fg-subtle font-mono">
            <span
              v-for="[k, v] in metricsKeys(l)"
              :key="k"
            >{{ k }}:<span class="text-fg-body ml-0.5">{{ v }}</span></span>
          </div>
        </li>
      </ul>
    </div>
  </section>
</template>
