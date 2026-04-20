<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router";

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
    <template v-if="auth.isAuthed && auth.activeWorkspace">
      <RouterLink
        to="/"
        class="flex items-center gap-2 min-w-0 hover:opacity-80 transition-opacity"
        aria-label="Back to projects"
      >
        <span class="text-signal-green font-mono tracking-wider" aria-hidden="true">◈</span>
        <span class="font-medium text-fg-primary truncate max-w-[20ch]">
          {{ auth.activeWorkspace.slug }}
        </span>
      </RouterLink>
      <span v-if="route.params.slug" class="text-fg-subtle">/</span>
      <RouterLink
        v-if="route.params.slug"
        :to="`/p/${route.params.slug}`"
        class="font-mono text-fg-body truncate max-w-[24ch] hover:opacity-80 transition-opacity"
      >
        {{ route.params.slug }}
      </RouterLink>
    </template>
    <template v-else>
      <div class="flex items-center gap-2 min-w-0">
        <span class="text-signal-green font-mono tracking-wider" aria-hidden="true">◈</span>
        <span class="font-mono text-fg-primary tracking-[0.08em] text-small uppercase">
          Vibecell
        </span>
      </div>
    </template>

    <nav v-if="auth.isAuthed" class="ml-6 flex items-center gap-4 text-small">
      <RouterLink
        to="/"
        class="mono-label hover:text-fg-body transition-colors"
        active-class="text-fg-primary"
        :class="{ 'text-fg-primary': route.path === '/' }"
      >projects</RouterLink>
      <RouterLink
        to="/ideas"
        class="mono-label hover:text-fg-body transition-colors"
        active-class="text-fg-primary"
      >ideas</RouterLink>
      <RouterLink
        to="/search"
        class="mono-label hover:text-fg-body transition-colors"
        active-class="text-fg-primary"
      >search</RouterLink>
    </nav>

    <button
      v-if="auth.isAuthed"
      class="ml-auto flex items-center gap-3 h-7 px-3 rounded-md border border-border bg-bg-surface/50 text-fg-muted text-small transition-colors hover:bg-bg-surface-hi"
      @click="palette.toggle"
    >
      <span>switch project…</span>
      <KbdHint keys="⌘K" />
    </button>
  </header>
</template>
