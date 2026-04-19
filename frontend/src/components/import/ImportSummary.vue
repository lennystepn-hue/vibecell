<script setup lang="ts">
import PrimaryButton from "@/components/ui/PrimaryButton.vue";

interface Props {
  count: number;
  importing: boolean;
}
defineProps<Props>();
defineEmits<{ (e: "import"): void; (e: "clear"): void }>();
</script>

<template>
  <transition
    enter-active-class="transition-all duration-med ease-out"
    enter-from-class="opacity-0 translate-y-4"
    enter-to-class="opacity-100 translate-y-0"
    leave-active-class="transition-all duration-fast ease-in"
    leave-from-class="opacity-100 translate-y-0"
    leave-to-class="opacity-0 translate-y-4"
  >
    <div
      v-if="count > 0 || importing"
      class="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 glass rounded-xl shadow-modal px-5 py-3 flex items-center gap-4"
      style="background: rgba(13, 18, 26, 0.95)"
    >
      <p class="text-body">
        <span class="tabular-nums text-fg-primary font-semibold">{{ count }}</span>
        <span class="text-fg-muted ml-2">{{ count === 1 ? "repo selected" : "repos selected" }}</span>
      </p>
      <button
        type="button"
        class="text-small text-fg-muted hover:text-fg-body transition-colors"
        :disabled="importing"
        @click="$emit('clear')"
      >clear</button>
      <PrimaryButton :disabled="count === 0" :loading="importing" @click="$emit('import')">
        <span>Import {{ count }} {{ count === 1 ? "repo" : "repos" }}</span>
      </PrimaryButton>
    </div>
  </transition>
</template>
