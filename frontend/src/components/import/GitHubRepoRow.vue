<script setup lang="ts">
import SignalDot from "@/components/ui/SignalDot.vue";
import type { components } from "@/api/types.gen";

type Repo = components["schemas"]["GitHubRepoOut"];

interface Props {
  repo: Repo;
  selected: boolean;
  alreadyImported?: boolean;
}
defineProps<Props>();
defineEmits<{ (e: "toggle"): void }>();

function shortDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Date(iso).toISOString().slice(0, 10);
}
</script>

<template>
  <label
    :class="[
      'flex items-center gap-3 px-3 py-2.5 rounded-md cursor-pointer group',
      'transition-colors duration-fast ease-out',
      alreadyImported
        ? 'opacity-50 cursor-not-allowed'
        : (selected ? 'bg-signal-green-bg' : 'hover:bg-bg-surface'),
    ]"
  >
    <input
      type="checkbox"
      :checked="selected"
      :disabled="alreadyImported"
      class="shrink-0 accent-signal-green w-4 h-4 rounded-sm cursor-pointer disabled:cursor-not-allowed"
      @change="$emit('toggle')"
    />
    <div class="flex-1 min-w-0">
      <div class="flex items-baseline gap-2 flex-wrap">
        <span class="font-mono text-body text-fg-primary truncate">{{ repo.full_name }}</span>
        <span
          v-if="repo.private"
          class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
          :style="{ background: 'var(--signal-amber-bg)', color: 'var(--signal-amber)' }"
        >private</span>
        <span
          v-if="alreadyImported"
          class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
          :style="{ background: 'var(--signal-blue-bg)', color: 'var(--signal-blue)' }"
        >already imported</span>
      </div>
      <p
        v-if="repo.description"
        class="text-small text-fg-muted truncate mt-0.5"
      >{{ repo.description }}</p>
    </div>

    <div class="shrink-0 flex items-center gap-4 text-small mono">
      <div v-if="repo.language" class="flex items-center gap-1.5 text-fg-muted">
        <SignalDot tone="blue" :glow="false" />
        <span>{{ repo.language }}</span>
      </div>
      <div class="text-fg-subtle tabular-nums w-[5rem] text-right">
        {{ shortDate(repo.pushed_at) }}
      </div>
    </div>
  </label>
</template>
