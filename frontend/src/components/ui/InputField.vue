<script setup lang="ts">
interface Props {
  modelValue: string;
  label?: string;
  type?: string;
  placeholder?: string;
  autocomplete?: string;
  autofocus?: boolean;
  error?: string | null;
  disabled?: boolean;
  id?: string;
}

const props = withDefaults(defineProps<Props>(), {
  type: "text",
  autofocus: false,
  disabled: false,
});

defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "keydown", ev: KeyboardEvent): void;
}>();

const id = props.id ?? `input-${Math.random().toString(36).slice(2, 8)}`;
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label
      v-if="label"
      :for="id"
      class="mono-label"
    >
      // {{ label }}
    </label>
    <input
      :id="id"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :autofocus="autofocus"
      :disabled="disabled"
      :class="[
        'h-10 px-3 rounded-md font-sans text-body',
        'bg-bg-surface border',
        error ? 'border-signal-red' : 'border-border',
        'text-fg-primary placeholder:text-fg-subtle',
        'transition-colors duration-fast ease-out',
        'hover:bg-bg-surface-hi disabled:opacity-50 disabled:cursor-not-allowed',
      ]"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keydown="$emit('keydown', $event)"
    />
    <p v-if="error" class="text-small text-signal-red">{{ error }}</p>
  </div>
</template>
