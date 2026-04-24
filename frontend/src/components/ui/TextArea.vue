<script setup lang="ts">
interface Props {
  modelValue: string;
  label?: string;
  placeholder?: string;
  rows?: number;
  error?: string | null;
}
withDefaults(defineProps<Props>(), { rows: 3 });
defineEmits<{ (e: "update:modelValue", v: string): void }>();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" class="mono-label">// {{ label }}</label>
    <textarea
      :value="modelValue"
      :placeholder="placeholder"
      :rows="rows"
      :class="[
        'px-3 py-2 rounded-md font-sans text-body bg-bg-surface border',
        error ? 'border-signal-red' : 'border-border',
        'text-fg-primary placeholder:text-fg-subtle resize-y',
        'transition-colors duration-fast ease-out hover:bg-bg-surface-hi',
      ]"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    />
    <p v-if="error" class="text-small text-signal-red">{{ error }}</p>
  </div>
</template>
