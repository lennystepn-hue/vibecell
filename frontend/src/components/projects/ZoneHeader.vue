<script setup lang="ts">
/**
 * Section divider for the project dashboard. Gives the page a clear
 * top-to-bottom narrative: NOW → WORK → CONFIG → PULSE. Labels use the
 * //shell-comment visual convention from the rest of the app.
 */
withDefaults(defineProps<{
  label: string;
  hint?: string;
  /** Some zones are collapsible — pass a v-model:open to drive the caret. */
  collapsible?: boolean;
  open?: boolean;
}>(), {
  collapsible: false,
  open: true,
});

const emit = defineEmits<{ "update:open": [boolean]; }>();

function toggle(open: boolean) {
  emit("update:open", !open);
}
</script>

<template>
  <header
    class="flex items-baseline gap-3 mt-10 mb-3 select-none"
    :class="{ 'cursor-pointer group': collapsible }"
    @click="collapsible && toggle(open)"
  >
    <span
      v-if="collapsible"
      class="font-mono text-fg-subtle transition-transform duration-fast"
      :class="{ 'rotate-90': open }"
      aria-hidden="true"
    >▸</span>
    <h2
      class="mono-label text-fg-body"
      :class="collapsible ? 'group-hover:text-fg-primary transition-colors' : ''"
    >// {{ label }}</h2>
    <span v-if="hint" class="text-small text-fg-subtle">— {{ hint }}</span>
    <div
      class="flex-1 border-b border-dashed border-border/50 mb-[6px]"
      aria-hidden="true"
    />
  </header>
</template>
