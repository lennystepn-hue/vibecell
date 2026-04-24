<script setup lang="ts">
interface Props {
  selected: boolean;
  icon?: string;
  label: string;
  hint?: string;
  shortcut?: string;
}
defineProps<Props>();

defineEmits<{ (e: "click"): void; (e: "hover"): void }>();
</script>

<template>
  <button
    type="button"
    :class="[
      'w-full flex items-center gap-3 px-4 h-10 text-left',
      'font-sans text-body',
      'transition-colors duration-fast ease-out',
      selected ? 'bg-bg-surface-hi text-fg-primary' : 'text-fg-body hover:bg-bg-surface',
    ]"
    @click="$emit('click')"
    @mouseenter="$emit('hover')"
  >
    <span
      v-if="icon"
      class="text-[16px] leading-none shrink-0 w-5 text-center"
      aria-hidden="true"
    >{{ icon }}</span>
    <span class="flex-1 truncate">{{ label }}</span>
    <span v-if="hint" class="mono text-small text-fg-muted">{{ hint }}</span>
    <kbd
      v-if="shortcut"
      class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
      style="background: var(--signal-blue-bg); color: var(--fg-muted); border: 1px solid var(--border-subtle)"
    >{{ shortcut }}</kbd>
  </button>
</template>
