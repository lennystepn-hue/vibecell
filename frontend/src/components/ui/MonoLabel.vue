<script setup lang="ts">
interface Props {
  prefix?: string;
}
withDefaults(defineProps<Props>(), { prefix: "//" });
</script>

<template>
  <div class="mono-label">
    <span class="opacity-60">{{ prefix }}</span>
    <slot />
  </div>
</template>
