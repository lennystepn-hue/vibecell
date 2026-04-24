<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from "vue";

interface Props {
  open: boolean;
  title?: string;
  width?: string;
}
const props = withDefaults(defineProps<Props>(), { width: "520px" });

const emit = defineEmits<{ (e: "close"): void }>();

const dialogRef = ref<HTMLDivElement | null>(null);

function onKey(ev: KeyboardEvent) {
  if (ev.key === "Escape" && props.open) {
    ev.preventDefault();
    emit("close");
  }
}

onMounted(() => document.addEventListener("keydown", onKey));
onUnmounted(() => document.removeEventListener("keydown", onKey));

watch(
  () => props.open,
  (o) => {
    if (o) {
      setTimeout(() => {
        const el = dialogRef.value?.querySelector<HTMLInputElement | HTMLTextAreaElement>(
          "input, textarea, select, button",
        );
        el?.focus();
      }, 30);
    }
  },
);
</script>

<template>
  <transition
    enter-active-class="transition-opacity duration-fast ease-out"
    enter-from-class="opacity-0"
    enter-to-class="opacity-100"
    leave-active-class="transition-opacity duration-fast ease-in"
    leave-from-class="opacity-100"
    leave-to-class="opacity-0"
  >
    <div
      v-if="open"
      class="fixed inset-0 z-40 flex items-start justify-center pt-[12vh] px-4"
      style="background: var(--bg-overlay)"
      @click.self="emit('close')"
    >
      <div
        ref="dialogRef"
        :style="{ width, maxWidth: '100%' }"
        class="glass rounded-xl overflow-hidden shadow-modal"
        style="background: var(--bg-chrome); border-color: var(--border-default)"
        role="dialog"
        aria-modal="true"
      >
        <header
          v-if="title"
          class="px-5 h-12 flex items-center border-b border-border-subtle"
        >
          <h2 class="text-section text-fg-primary font-semibold tracking-tight">{{ title }}</h2>
          <button
            type="button"
            class="ml-auto text-fg-muted hover:text-fg-body transition-colors w-7 h-7 flex items-center justify-center rounded-md"
            aria-label="Close"
            @click="emit('close')"
          >✕</button>
        </header>
        <div class="p-5">
          <slot />
        </div>
      </div>
    </div>
  </transition>
</template>
