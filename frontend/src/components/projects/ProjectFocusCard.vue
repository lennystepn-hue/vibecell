<script setup lang="ts">
import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <section class="glass rounded-lg p-5">
    <div
      v-if="project.context?.blocked_by"
      class="mb-4 px-3 py-2 rounded-sm text-small"
      :style="{ background: 'var(--signal-red-bg)', color: 'var(--signal-red)' }"
    >
      <span class="font-mono uppercase text-[10px] tracking-widest mr-2">blocked</span>
      <span>{{ project.context.blocked_by }}</span>
    </div>

    <div class="space-y-5">
      <div>
        <MonoLabel>current focus</MonoLabel>
        <p v-if="project.context?.current_focus" class="text-section text-fg-primary mt-1">
          {{ project.context.current_focus }}
        </p>
        <p v-else class="text-body text-fg-muted mt-1 italic">— not set —</p>
      </div>

      <div>
        <MonoLabel>next step</MonoLabel>
        <p v-if="project.context?.next_step" class="text-body text-fg-body mt-1">
          {{ project.context.next_step }}
        </p>
        <p v-else class="text-body text-fg-muted mt-1 italic">— not set —</p>
      </div>

      <details
        v-if="project.context?.user_wants || (project.context?.open_questions && project.context.open_questions.length > 0)"
      >
        <summary class="mono-label cursor-pointer select-none hover:text-fg-body transition-colors">
          more context ▾
        </summary>
        <div class="mt-3 space-y-4 pl-0">
          <div v-if="project.context?.user_wants">
            <MonoLabel>user wants</MonoLabel>
            <p class="text-small text-fg-muted mt-1">{{ project.context.user_wants }}</p>
          </div>
          <div
            v-if="project.context?.open_questions && project.context.open_questions.length > 0"
          >
            <MonoLabel>open questions</MonoLabel>
            <ul class="mt-1 space-y-1 list-none text-small text-fg-muted">
              <li v-for="(q, i) in project.context.open_questions" :key="i">
                <span class="text-fg-subtle mr-1">?</span>{{ q }}
              </li>
            </ul>
          </div>
        </div>
      </details>
    </div>
  </section>
</template>
