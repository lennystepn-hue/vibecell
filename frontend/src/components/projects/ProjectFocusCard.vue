<script setup lang="ts">
import EmptyHint from "@/components/ui/EmptyHint.vue";
import WidgetCard from "@/components/projects/WidgetCard.vue";
import MonoLabel from "@/components/ui/MonoLabel.vue";
import type { components } from "@/api/types.gen";

type Project = components["schemas"]["ProjectFullOut"];
defineProps<{ project: Project }>();
</script>

<template>
  <WidgetCard id="focus">
    <div
      v-if="project.context?.blocked_by"
      class="mb-4 px-3 py-2 rounded-sm text-small"
      :style="{ background: 'var(--signal-red-bg)', color: 'var(--signal-red)' }"
    >
      <span class="font-mono uppercase text-nano tracking-widest mr-2">blocked</span>
      <span>{{ project.context.blocked_by }}</span>
    </div>

    <div class="space-y-5">
      <div>
        <MonoLabel>current focus</MonoLabel>
        <p v-if="project.context?.current_focus" class="text-section text-fg-primary mt-1">
          {{ project.context.current_focus }}
        </p>
        <EmptyHint v-else tool="vibecell_set_focus" density="inline" class="mt-1">
          Nothing set. Tell Claude what you're working on and it keeps this current.
        </EmptyHint>
      </div>

      <div>
        <MonoLabel>next step</MonoLabel>
        <p v-if="project.context?.next_step" class="text-body text-fg-body mt-1">
          {{ project.context.next_step }}
        </p>
        <EmptyHint v-else tool="vibecell_set_focus" density="inline" class="mt-1">
          Nothing set. Claude writes this at the end of a session so the next one
          starts where you stopped.
        </EmptyHint>
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
  </WidgetCard>
</template>
