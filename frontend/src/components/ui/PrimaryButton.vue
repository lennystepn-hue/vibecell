<script setup lang="ts">
interface Props {
  type?: "button" | "submit";
  disabled?: boolean;
  loading?: boolean;
  size?: "md" | "lg";
}

withDefaults(defineProps<Props>(), {
  type: "button",
  disabled: false,
  loading: false,
  size: "md",
});
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[
      'inline-flex items-center justify-center gap-2',
      'font-sans font-semibold tracking-tight',
      'rounded-md px-4',
      size === 'lg' ? 'h-11 text-section' : 'h-10 text-body',
      'transition-all duration-fast ease-out',
      'disabled:opacity-50 disabled:cursor-not-allowed',
    ]"
    :style="{
      background: 'var(--signal-green)',
      color: 'var(--bg-body-to)',
      boxShadow: '0 0 0 1px var(--signal-green), 0 0 16px rgba(92, 200, 164, 0.18)',
    }"
  >
    <svg
      v-if="loading"
      class="animate-spin h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.3" stroke-width="3" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        fill="none"
      />
    </svg>
    <slot />
  </button>
</template>
