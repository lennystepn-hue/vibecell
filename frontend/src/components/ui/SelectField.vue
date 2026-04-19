<script setup lang="ts">
interface Option {
  value: string;
  label: string;
}
interface Props {
  modelValue: string;
  options: Option[];
  label?: string;
}
defineProps<Props>();
defineEmits<{ (e: "update:modelValue", v: string): void }>();
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" class="mono-label">// {{ label }}</label>
    <select
      :value="modelValue"
      class="h-10 px-3 rounded-md font-sans text-body bg-bg-surface/60 border border-border text-fg-primary hover:bg-bg-surface-hi transition-colors duration-fast"
      @change="$emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
    >
      <option v-for="o in options" :key="o.value" :value="o.value">{{ o.label }}</option>
    </select>
  </div>
</template>
