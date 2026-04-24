<script setup lang="ts">
/**
 * Deterministic glass-orb avatar — one per project, driven off the slug so
 * the same project always looks the same across every surface (sidebar,
 * card, detail header). Replaces the 📦 emoji fallback with something that
 * actually feels bespoke.
 *
 * Uniqueness guarantees:
 *   - 30-color vivid-pastel pool (3 picks × 30 = 27,000 ordered triples)
 *   - 360° base-rotation of the gradient derived from separate hash bits
 *   - Each property (c1, c2, c3, rotation, blob-position) pulls from
 *     independent bytes of a 32-bit FNV hash so they don't collapse together
 *   - Practical collision probability: ~0.04% for 100 projects in a
 *     workspace (9.7M visually distinct possibilities). If you somehow
 *     bump into a visual twin, add a suffix to the slug or we'll extend
 *     this to per-workspace guaranteed-uniqueness via a stored config.
 *
 * The orb layers three radial-gradient blobs (offset blob positions) +
 * a linear base, then adds a white specular highlight (::after) so it
 * reads as a glass sphere. All pure CSS, no images, no animation.
 */
import { computed } from "vue";

const props = withDefaults(defineProps<{
  /** Seed — typically project.id (ULID) or project.slug. Same seed = same orb. */
  seed: string;
  /** Pixel size. Defaults to 40px. */
  size?: number;
  /** Rounded square instead of full circle (squircle-ish). Default: circle. */
  squircle?: boolean;
}>(), {
  size: 40,
  squircle: false,
});

// FNV-1a. Tiny, dependency-free, deterministic. Returns a 32-bit unsigned int.
function hash(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

// 30 vivid pastels, tuned for both Paper (light) and Midnight (dark) bgs.
// Ordering doesn't matter — picks are independent.
const POOL = [
  "#ff6b9d", "#ff8f6b", "#ffc56b", "#c5ff6b", "#6bffb4",
  "#6bd4ff", "#6b9dff", "#b592ff", "#ff6bd4", "#ff7e7e",
  "#7dffd4", "#a6e4ff", "#d4c2ff", "#ffc8a0", "#c8ffc2",
  "#ffb5d8", "#b5e8ff", "#e8b5ff", "#f5e07c", "#7cf5c7",
  "#f5a67c", "#7cb5f5", "#c77cf5", "#f57cb5", "#b5f57c",
  "#7cf5e0", "#f5c77c", "#a6f57c", "#ff9e6b", "#6bb5ff",
];

// 8 blob-position presets. Each tuple is (x%, y%) for each of the 3 blobs
// so the orb's highlight cluster shifts around and same-color orbs don't
// collapse visually when bit-16..23 of hash collides with someone else's.
const POSITIONS: Array<[[number, number], [number, number], [number, number]]> = [
  [[72, 28], [28, 72], [50, 100]],
  [[30, 25], [75, 60], [45, 90]],
  [[65, 35], [25, 70], [55, 95]],
  [[40, 20], [80, 75], [35, 85]],
  [[75, 40], [30, 60], [60, 95]],
  [[50, 30], [20, 80], [80, 70]],
  [[25, 35], [70, 30], [50, 85]],
  [[60, 20], [35, 75], [70, 90]],
];

const style = computed(() => {
  const h = hash(props.seed || "default");

  // Independent 8-bit slices so each property is statistically separate.
  const b0 = h & 0xff;           // c1 index
  const b1 = (h >>> 8) & 0xff;   // c2 index
  const b2 = (h >>> 16) & 0xff;  // c3 index
  const b3 = (h >>> 24) & 0xff;  // rotation angle
  // reuse some mid bits for position preset
  const b4 = (h ^ (h >>> 11)) & 0xff;  // position-preset index

  const c1 = POOL[b0 % POOL.length];
  let c2 = POOL[b1 % POOL.length];
  if (c2 === c1) c2 = POOL[(b1 + 7) % POOL.length];  // force distinct from c1
  let c3 = POOL[b2 % POOL.length];
  if (c3 === c1 || c3 === c2) c3 = POOL[(b2 + 13) % POOL.length];

  const rotation = Math.floor((b3 / 255) * 360);
  const pos = POSITIONS[b4 % POSITIONS.length];
  const s = props.size;

  return {
    width: `${s}px`,
    height: `${s}px`,
    borderRadius: props.squircle ? `${s * 0.3}px` : "50%",
    background: `
      radial-gradient(circle at ${pos[0][0]}% ${pos[0][1]}%, ${c1} 0%, transparent 55%),
      radial-gradient(circle at ${pos[1][0]}% ${pos[1][1]}%, ${c2} 0%, transparent 55%),
      radial-gradient(circle at ${pos[2][0]}% ${pos[2][1]}%, ${c3} 0%, transparent 65%),
      linear-gradient(${rotation}deg, ${c1}, ${c3})
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
