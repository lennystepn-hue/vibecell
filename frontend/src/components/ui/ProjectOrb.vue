<script setup lang="ts">
/**
 * Deterministic glass-orb avatar — one per project, driven off the slug so
 * the same project always looks the same across every surface (sidebar,
 * card, detail header). Replaces the 📦 emoji fallback with something that
 * actually feels bespoke.
 *
 * The orb layers three radial-gradient blobs (three colors picked from a
 * curated pastel-vivid pool via an FNV-style hash of the seed), then adds:
 *   - a white specular highlight top-left so it reads as a glass sphere
 *   - a soft inset shadow bottom-right for depth
 *   - a tight ring-glow outside for separation on both light + dark themes
 *
 * Pure CSS, no images, no animation (could add a slow hue-rotate for "live"
 * projects later if it's fun).
 */
import { computed } from "vue";

const props = withDefaults(defineProps<{
  /** Seed — typically the project slug. Same seed = same orb. */
  seed: string;
  /** Pixel size. Defaults to 40px. */
  size?: number;
  /** Rounded square instead of full circle (squircle-ish). Default: circle. */
  squircle?: boolean;
}>(), {
  size: 40,
  squircle: false,
});

// FNV-1a. Tiny, dependency-free, deterministic.
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// Curated pool — every color is vivid enough to carry an avatar but soft
// enough that 3 of them blended don't look garish. Tuned for both Paper
// (light bg) and Midnight (dark bg) themes.
const POOL = [
  "#ff6b9d", "#ff8f6b", "#ffc56b", "#c5ff6b", "#6bffb4",
  "#6bd4ff", "#6b9dff", "#b592ff", "#ff6bd4", "#ff7e7e",
  "#7dffd4", "#a6e4ff", "#d4c2ff", "#ffc8a0", "#c8ffc2",
  "#ffb5d8", "#b5e8ff", "#e8b5ff",
];

const style = computed(() => {
  const h = hash(props.seed || "default");
  const c1 = POOL[h % POOL.length];
  const c2 = POOL[(h >>> 7) % POOL.length];
  const c3 = POOL[(h >>> 13) % POOL.length];
  const s = props.size;

  // 4 layered radial blobs (offset corners) + a linear base. Specular
  // highlight is rendered as a separate :after pseudo-element so it doesn't
  // blend into the gradient and kill the glass feel.
  return {
    width: `${s}px`,
    height: `${s}px`,
    borderRadius: props.squircle ? `${s * 0.3}px` : "50%",
    background: `
      radial-gradient(circle at 72% 28%, ${c1} 0%, transparent 55%),
      radial-gradient(circle at 28% 72%, ${c2} 0%, transparent 55%),
      radial-gradient(circle at 50% 100%, ${c3} 0%, transparent 65%),
      linear-gradient(135deg, ${c1}, ${c3})
    `,
    boxShadow: `
      inset 0 ${s * 0.05}px ${s * 0.15}px rgba(255,255,255,0.45),
      inset 0 -${s * 0.05}px ${s * 0.12}px rgba(0,0,0,0.18),
      0 ${s * 0.08}px ${s * 0.3}px ${c1}40,
      0 0 0 1px rgba(255,255,255,0.12)
    `,
  };
});
</script>

<template>
  <span class="orb shrink-0" :style="style" aria-hidden="true" />
</template>

<style scoped>
.orb {
  display: inline-block;
  position: relative;
  isolation: isolate;
}
/* Specular highlight — top-left crescent-ish glint that sells the glass
   sphere look. Scales with the orb via % positioning. */
.orb::after {
  content: "";
  position: absolute;
  top: 8%;
  left: 18%;
  width: 45%;
  height: 35%;
  border-radius: 50%;
  background: radial-gradient(
    ellipse at 30% 20%,
    rgba(255, 255, 255, 0.7) 0%,
    rgba(255, 255, 255, 0.15) 40%,
    transparent 70%
  );
  filter: blur(2px);
  pointer-events: none;
}
</style>
