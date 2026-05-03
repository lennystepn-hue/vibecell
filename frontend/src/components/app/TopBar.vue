<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { useCommandPaletteStore } from "@/stores/command-palette";
import KbdHint from "@/components/ui/KbdHint.vue";
import UserMenu from "./UserMenu.vue";

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
        to="/p"
        class="flex items-center gap-2 min-w-0 hover:opacity-80 transition-opacity"
        aria-label="Back to projects"
      >
        <span class="text-signal-green font-mono tracking-wider" aria-hidden="true">◈</span>
        <!-- Workspace slug truncates harder on mobile (12ch) so the right-
             side actions never overlap. Desktop keeps 20ch breathing room. -->
        <span class="font-medium text-fg-primary truncate max-w-[12ch] sm:max-w-[20ch]">
          {{ auth.activeWorkspace.slug }}
        </span>
      </RouterLink>
      <span v-if="route.params.slug" class="text-fg-subtle">/</span>
      <RouterLink
        v-if="route.params.slug"
        :to="`/p/${route.params.slug}`"
        class="font-mono text-fg-body truncate max-w-[14ch] sm:max-w-[24ch] hover:opacity-80 transition-opacity"
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

    <!-- Quick-nav (projects / ideas / search) hidden on mobile — those routes
         are reachable from the UserMenu dropdown + the sidebar on /p. The
         topbar on small screens commits to: brand, current project, actions. -->
    <nav v-if="auth.isAuthed" class="hidden md:flex ml-6 items-center gap-4 text-small">
      <RouterLink
        to="/p"
        class="mono-label hover:text-fg-body transition-colors"
        active-class="text-fg-primary"
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

    <div v-if="auth.isAuthed" class="ml-auto flex items-center gap-2">
      <!-- Mobile: collapse the project-switcher to icon-only (⌘K still wired
           via the global keyboard shortcut in KeyboardShortcuts.vue). The
           verbose "switch project…" label only appears at sm+ where there's
           room for it. The button itself stays clickable on mobile so users
           without a keyboard can still open the palette. -->
      <button
        class="flex items-center gap-3 h-7 px-2 sm:px-3 rounded-md border border-border bg-bg-surface text-fg-muted text-small transition-colors hover:bg-bg-surface-hi"
        @click="palette.toggle"
        aria-label="Switch project"
      >
        <span class="hidden sm:inline">switch project…</span>
        <KbdHint keys="⌘K" />
      </button>
      <UserMenu variant="chrome" />
    </div>
    <div v-else class="ml-auto">
      <RouterLink
        to="/login"
        class="h-7 px-3 inline-flex items-center rounded-md text-small font-mono bg-signal-green/90 hover:bg-signal-green text-bg-body transition-colors"
        style="color:#070b10"
      >sign in →</RouterLink>
    </div>
  </header>
</template>
