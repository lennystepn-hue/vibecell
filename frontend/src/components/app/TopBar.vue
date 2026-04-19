<script setup lang="ts">
import { useRoute } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { useCommandPaletteStore } from "@/stores/command-palette";
import KbdHint from "@/components/ui/KbdHint.vue";

const route = useRoute();
const auth = useAuthStore();
const palette = useCommandPaletteStore();
</script>

<template>
  <header
    class="chrome sticky top-0 z-30 flex items-center gap-3 px-4 h-11 border-b font-sans text-body"
  >
    <div class="flex items-center gap-2 min-w-0">
      <span class="text-signal-green font-mono tracking-wider" aria-hidden="true">◈</span>
      <span class="font-medium text-fg-primary truncate max-w-[20ch]">
        {{ auth.activeWorkspace?.slug ?? "hangar" }}
      </span>
      <span v-if="route.params.slug" class="text-fg-subtle">/</span>
      <span v-if="route.params.slug" class="font-mono text-fg-body truncate max-w-[24ch]">
        {{ route.params.slug }}
      </span>
    </div>

    <button
      class="ml-auto flex items-center gap-3 h-7 px-3 rounded-md border border-border bg-bg-surface/50 text-fg-muted text-small transition-colors hover:bg-bg-surface-hi"
      @click="palette.toggle"
    >
      <span>switch project…</span>
      <KbdHint keys="⌘K" />
    </button>
  </header>
</template>
