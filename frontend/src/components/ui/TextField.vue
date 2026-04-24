<script setup lang="ts">
interface Props {
  modelValue: string;
  label?: string;
  type?: string;
  placeholder?: string;
  autofocus?: boolean;
  error?: string | null;
  disabled?: boolean;
  required?: boolean;
  id?: string;
}
const props = withDefaults(defineProps<Props>(), {
  type: "text",
  autofocus: false,
  disabled: false,
  required: false,
});
defineEmits<{ (e: "update:modelValue", v: string): void }>();
const id = props.id ?? `tf-${Math.random().toString(36).slice(2, 8)}`;
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label v-if="label" :for="id" class="mono-label">// {{ label }}</label>
    <input
      :id="id"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :autofocus="autofocus"
      :disabled="disabled"
      :required="required"
      :class="[
        'h-10 px-3 rounded-md font-sans text-body bg-bg-surface border',
        error ? 'border-signal-red' : 'border-border',
        'text-fg-primary placeholder:text-fg-subtle',
        'transition-colors duration-fast ease-out hover:bg-bg-surface-hi disabled:opacity-50',
      ]"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
    />
    <p v-if="error" class="text-small text-signal-red">{{ error }}</p>
  </div>
</template>
