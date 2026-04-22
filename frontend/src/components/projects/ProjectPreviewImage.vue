<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { onProjectLiveEvent } from "@/composables/useProjectLive";

const props = withDefaults(defineProps<{
  slug: string;
  /** "hero" = fills card background. "panel" = bordered rectangle. "thumb" = small inline. */
  variant?: "hero" | "panel" | "thumb";
  /** Override the URL path (used when a specific screenshot_id is being shown). */
  url?: string;
  /** Text overlay for the empty state (defaults to //preview). */
  emptyLabel?: string;
}>(), {
  variant: "panel",
  url: "",
  emptyLabel: "//preview",
});

const loading = ref(true);
const failed = ref(false);
const src = ref<string>("");

function resolveUrl(slug: string): string {
  return props.url || `/api/v1/projects/${slug}/preview`;
}

// Probe the preview endpoint: 307 → load; 204 → empty state; error → failed.
// Using fetch first (not <img> directly) lets us detect the "no screenshot yet"
// 204 case without triggering a visible broken-image flash.
async function load(slug: string) {
  loading.value = true;
  failed.value = false;
  src.value = "";
  try {
    const res = await fetch(resolveUrl(slug), {
      credentials: "include",
      redirect: "follow",
    });
    if (res.status === 204) {
      failed.value = true;
      return;
    }
    if (!res.ok) {
      failed.value = true;
      return;
    }
    // Ok — either the redirect target, or the file itself. res.url points at
    // the final URL after redirects.
    src.value = res.url;
  } catch {
    failed.value = true;
  } finally {
    loading.value = false;
  }
}

watch(() => props.slug, (s) => void load(s), { immediate: true });
watch(() => props.url, () => void load(props.slug));

// Fresh capture? Swap in the new one.
onProjectLiveEvent(["screenshot.captured", "ship.created"], () => void load(props.slug));

const variantClass = computed(() => {
  switch (props.variant) {
    case "hero":
      return "absolute inset-0 w-full h-full object-cover opacity-[0.28] blur-[0.5px]";
    case "thumb":
      return "w-16 h-10 object-cover rounded-sm shrink-0";
    case "panel":
    default:
      return "w-full aspect-[16/10] object-cover rounded-lg";
  }
});
</script>

<template>
  <div v-if="variant === 'panel'" class="relative w-full aspect-[16/10] rounded-lg overflow-hidden border border-border bg-bg-surface/40">
    <transition
      enter-active-class="transition-opacity duration-300"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
    >
      <img
        v-if="src"
        :src="src"
        alt="project preview"
        class="w-full h-full object-cover"
        loading="lazy"
      />
      <div v-else-if="loading" class="absolute inset-0 flex items-center justify-center text-fg-subtle mono-label">
        capturing…
      </div>
      <div v-else-if="failed" class="absolute inset-0 flex items-center justify-center text-fg-subtle mono-label">
        {{ emptyLabel }}
      </div>
    </transition>
  </div>

  <img
    v-else-if="variant === 'thumb' && src"
    :src="src"
    alt=""
    :class="variantClass"
    loading="lazy"
  />

  <img
    v-else-if="variant === 'hero' && src"
    :src="src"
    alt=""
    :class="variantClass"
    loading="lazy"
    aria-hidden="true"
  />
</template>
