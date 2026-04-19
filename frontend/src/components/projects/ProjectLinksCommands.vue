<script setup lang="ts">
import { ref } from "vue";

import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();

const tab = ref<"links" | "commands">("links");
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

    <div v-if="tab === 'links'" class="p-5">
      <ul v-if="project.links.length > 0" class="space-y-2">
        <li v-for="l in project.links" :key="l.id" class="flex items-center gap-3">
          <span class="mono-label w-14 shrink-0 text-right">{{ l.kind || "link" }}</span>
          <a
            :href="l.url"
            target="_blank"
            rel="noopener"
            class="link text-body flex-1 truncate"
          >
            {{ l.label || l.url }}
            <span class="text-fg-subtle ml-1" aria-hidden="true">↗</span>
          </a>
        </li>
      </ul>
      <p v-else class="text-small text-fg-muted italic">— no links —</p>
    </div>

    <div v-else class="p-5">
      <ul v-if="project.commands.length > 0" class="space-y-2">
        <li
          v-for="c in project.commands"
          :key="c.id"
          class="flex flex-col gap-1 p-3 rounded-md border border-border-subtle"
        >
          <div class="flex items-center gap-2">
            <MonoLabel>{{ c.run_in }}</MonoLabel>
            <span class="text-section font-semibold text-fg-primary">{{ c.label }}</span>
          </div>
          <code class="font-mono text-small text-fg-muted truncate">{{ c.command }}</code>
        </li>
      </ul>
      <p v-else class="text-small text-fg-muted italic">— no commands saved —</p>
      <p class="mono-label opacity-50 mt-3">
        execution lands in the CLI phase (spec 3)
      </p>
    </div>
  </section>
</template>
