<script setup lang="ts">
import { RouterLink } from "vue-router";

import LivePulse from "@/components/app/LivePulse.vue";
import ProjectPreviewImage from "@/components/projects/ProjectPreviewImage.vue";
import ProjectOrb from "@/components/ui/ProjectOrb.vue";
import StatusPill from "@/components/ui/StatusPill.vue";
import { usePresenceStore } from "@/stores/presence";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectListItem"];

const props = defineProps<{ project: Project }>();
const presence = usePresenceStore();
const liveClass = () => (presence.isLive(props.project.slug)
  ? "ring-1 ring-signal-green/40 shadow-[0_0_18px_rgba(92,200,164,0.15)]"
  : "");
</script>

<template>
  <RouterLink
    :to="`/p/${project.slug}`"
    class="group block glass rounded-lg p-4 transition-all duration-fast ease-out hover:bg-bg-surface-hi hover:border-border-strong relative overflow-hidden isolate"
    :class="liveClass()"
  >
    <!-- Screenshot as a subtle card background. `hero` variant is absolute-
         positioned, object-cover, opacity ~0.28, slightly blurred. On hover
         we lift the opacity to 0.4 so you can see more of the site. The
         gradient overlay underneath keeps text readable even when the
         screenshot is busy. -->
    <ProjectPreviewImage
      :slug="project.slug"
      variant="hero"
      class="!opacity-[0.22] group-hover:!opacity-[0.38] transition-opacity duration-med -z-10"
    />
    <!-- Readability gradient: fades the bg-surface tone from left (where
         the text is) to transparent on the right so the screenshot peeks
         through more on that side. -->
    <div
      class="absolute inset-0 -z-10 pointer-events-none"
      style="background: linear-gradient(to right, var(--bg-surface) 0%, var(--bg-surface) 30%, rgba(0,0,0,0) 100%)"
      aria-hidden="true"
    />

    <div class="flex items-start gap-3 mb-2">
      <ProjectOrb :seed="project.slug" :size="40" />
      <div class="flex-1 min-w-0">
        <div class="flex items-baseline justify-between gap-2">
          <!-- Name + optional GitHub icon inline, left side -->
          <div class="flex items-center gap-1.5 min-w-0">
            <h3 class="text-section font-semibold text-fg-primary tracking-tight truncate">
              {{ project.name }}
            </h3>
            <a
              v-if="project.github_url"
              :href="project.github_url"
              target="_blank"
              rel="noopener noreferrer"
              class="shrink-0 text-fg-subtle hover:text-fg-body transition-colors z-10"
              aria-label="Open on GitHub"
              @click.stop
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="currentColor" aria-hidden="true">
                <path d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27.68 0 1.36.09 2 .27 1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.013 8.013 0 0 0 16 8c0-4.42-3.58-8-8-8z"/>
              </svg>
            </a>
          </div>
          <!-- Status pill, right side, never overlapped -->
          <div class="flex items-center gap-2 shrink-0">
            <LivePulse :slug="project.slug" variant="dot" />
            <StatusPill :status="project.status as never" />
          </div>
        </div>
        <p class="mono text-small text-fg-subtle truncate mt-0.5">{{ project.slug }}</p>
        <LivePulse :slug="project.slug" variant="pill" class="mt-1" />
      </div>
    </div>
    <p v-if="project.pitch" class="text-small text-fg-muted line-clamp-2 mt-3 relative">
      {{ project.pitch }}
    </p>
    <p v-else class="mono-label mt-3 opacity-50 relative">// no pitch yet</p>
  </RouterLink>
</template>

<!-- orb has its own inherent vibe; no hover filter juggling needed anymore -->
