<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { onProjectLiveEvent } from "@/composables/useProjectLive";

const props = withDefaults(defineProps<{
  slug: string;
  /**
   * "mini"  — small 160×100 clickable thumbnail, meant for the top-right
   *           corner of a header or card. If `href` is given it becomes a
   *           link that opens the live URL in a new tab.
   * "panel" — full bordered rectangle with 16:10 aspect (detail page hero).
   * "thumb" — tiny inline (used in activity timeline / ship list).
   * "hero"  — fills the parent as a background image (with heavy gradient
   *           overlay applied by the consumer).
   */
  variant?: "mini" | "panel" | "thumb" | "hero";
  /** Override the URL path (used when a specific screenshot_id is being shown). */
  url?: string;
  /** When set, the preview becomes a link opening this URL in a new tab. */
  href?: string;
  /** Text overlay for the empty state. */
  emptyLabel?: string;
}>(), {
  variant: "panel",
  url: "",
  href: "",
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
    src.value = res.url;
  } catch {
    failed.value = true;
  } finally {
    loading.value = false;
  }
}

watch(() => props.slug, (s) => void load(s), { immediate: true });
watch(() => props.url, () => void load(props.slug));
onProjectLiveEvent(["screenshot.captured", "ship.created"], () => void load(props.slug));

const miniClass = computed(() =>
  "block w-[180px] h-[112px] rounded-md overflow-hidden border border-border transition-all " +
  "hover:border-signal-green/50 hover:shadow-[0_0_16px_rgba(92,200,164,0.18)] " +
  "bg-bg-surface/40",
);
</script>

<template>
  <!-- ─── mini: 180×112 clickable thumbnail ──────────────────────────────── -->
  <template v-if="variant === 'mini'">
    <a
      v-if="href && src"
      :href="href"
      target="_blank"
      rel="noopener noreferrer"
      :class="miniClass"
      :title="`Open ${href} in new tab`"
    >
      <img
        :src="src"
        alt="live preview"
        class="w-full h-full object-cover object-top"
        loading="lazy"
      />
    </a>
    <div
      v-else-if="src"
      :class="miniClass"
    >
      <img
        :src="src"
        alt="live preview"
        class="w-full h-full object-cover object-top"
        loading="lazy"
      />
    </div>
    <div
      v-else-if="loading"
      :class="[miniClass, 'flex items-center justify-center cursor-default']"
    >
      <span class="font-mono text-[10px] text-fg-subtle">capturing…</span>
    </div>
    <div
      v-else
      :class="[miniClass, 'flex items-center justify-center cursor-default']"
    >
      <span class="font-mono text-[10px] text-fg-subtle">{{ emptyLabel }}</span>
    </div>
  </template>

  <!-- ─── panel: full 16:10 rectangle ────────────────────────────────────── -->
  <div
    v-else-if="variant === 'panel'"
    class="relative w-full aspect-[16/10] rounded-lg overflow-hidden border border-border bg-bg-surface/40"
  >
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

  <!-- ─── thumb: tiny inline. Caller owns width/height + rounding via class. -->
  <img
    v-else-if="variant === 'thumb' && src"
    :src="src"
    alt=""
    class="object-cover shrink-0"
    loading="lazy"
  />

  <!-- ─── hero: background-fill ──────────────────────────────────────────── -->
  <img
    v-else-if="variant === 'hero' && src"
    :src="src"
    alt=""
    class="absolute inset-0 w-full h-full object-cover opacity-[0.28] blur-[0.5px]"
    loading="lazy"
    aria-hidden="true"
  />
</template>
