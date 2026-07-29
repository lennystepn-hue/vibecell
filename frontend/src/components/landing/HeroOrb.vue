<script setup lang="ts">
/**
 * Hero orb — glass sphere that stays a clean circle at all times.
 *
 * "Rotation" is faked INSIDE the orb (rotating aurora + drifting highlight
 * band) rather than by 3D-rotating the 2D element, which just squishes it.
 * Mouse interaction shifts the specular glint toward the cursor so the orb
 * feels like a heavy glass ball you can push light across.
 *
 * Layers (z-stacked, all clipped to the orb circle):
 *   1. halo — outer breathing glow
 *   2. body — stationary radial-gradient blobs (mint/violet/pink/teal)
 *   3. aurora — conic gradient rotating forever, color-dodge blended
 *   4. band — a soft diagonal light-band that drifts so it reads as spin
 *   5. specular — top-left highlight, follows cursor
 *   6. rim — 1px ring for edge definition
 */
import { computed, ref } from "vue";

const root = ref<HTMLElement | null>(null);

// Normalised pointer position inside the orb (-0.5..0.5 on each axis).
// Drives only the specular glint — the orb shape itself stays a circle.
const pointerX = ref(0);
const pointerY = ref(-0.15);
const hovering = ref(false);

function onMove(e: MouseEvent) {
  if (!root.value) return;
  hovering.value = true;
  const rect = root.value.getBoundingClientRect();
  pointerX.value = (e.clientX - rect.left) / rect.width - 0.5;
  pointerY.value = (e.clientY - rect.top) / rect.height - 0.5;
}

function onLeave() {
  hovering.value = false;
  pointerX.value = 0;
  pointerY.value = -0.15;
}

// Map -0.5..0.5 → 0..100% positioning for the specular element.
const specularStyle = computed(() => ({
  top: `${18 + pointerY.value * 30}%`,
  left: `${22 + pointerX.value * 30}%`,
}));
</script>

<template>
  <div
    ref="root"
    class="hero-orb"
    aria-hidden="true"
    @mousemove="onMove"
    @mouseleave="onLeave"
  >
    <div class="halo" />
    <div class="orb-container">
      <div class="body" />
      <div class="aurora" />
      <div class="band" />
      <div class="specular" :style="specularStyle" />
      <div class="rim" />
    </div>
    <div
      class="cursor-hint"
      :class="{ 'cursor-hint-visible': hovering }"
      aria-hidden="true"
    >move me</div>
  </div>
</template>

<style scoped>
.hero-orb {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  isolation: isolate;
  cursor: crosshair;
}

/* ─── Outer halo — breathing glow ──────────────────────────────────── */
.halo {
  position: absolute;
  width: 120%;
  aspect-ratio: 1;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgb(var(--signal-green-rgb) / 0.22) 0%,
    rgb(var(--signal-violet-rgb) / 0.12) 30%,
    rgb(var(--aurora-4-rgb) / 0.06) 55%,
    transparent 70%
  );
  filter: blur(60px);
  animation: halo-breathe 8s ease-in-out infinite;
  pointer-events: none;
  z-index: 0;
}

/* ─── The sphere: always a perfect circle, never transformed in 3D ── */
.orb-container {
  position: relative;
  width: 82%;
  aspect-ratio: 1;
  max-width: 440px;
  max-height: 440px;
  border-radius: 50%;
  overflow: hidden;
  z-index: 1;
  /* No 1px ring. On dark canvas at desktop DPI it reads as faint glow,
     but at mobile DPI + when the parent section is overflow-hidden, it
     renders as a hard pixel border around the sphere — user-visible
     "rand". The rim layer below already gives us the inset-light
     definition the orb needs.
     Bottom drop-shadows kept but softened + pulled in so they don't
     get clipped to a visible horizontal line by the section's
     overflow-hidden boundary. */
  box-shadow:
    0 24px 60px rgb(var(--signal-green-rgb) / 0.18),
    0 10px 30px rgb(var(--signal-violet-rgb) / 0.10);
}

/* Radial blobs — violet, mint, soft-pink, teal over a deep mint→violet base */
.body {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    radial-gradient(circle at 30% 28%, var(--orb-violet) 0%, transparent 45%),
    radial-gradient(circle at 72% 70%, var(--orb-green) 0%, transparent 50%),
    radial-gradient(circle at 50% 95%, var(--orb-rose) 0%, transparent 55%),
    radial-gradient(circle at 80% 20%, var(--orb-teal) 0%, transparent 35%),
    linear-gradient(135deg, var(--orb-green-deep) 0%, var(--orb-violet-deep) 100%);
  box-shadow:
    inset 0 -60px 120px rgb(var(--scrim-rgb) / 0.35),
    inset 0 40px 80px rgb(var(--specular-rgb) / 0.12);
  z-index: 1;
}

/* Aurora — the main "spin". Conic gradient turning forever, blur + dodge
   blend so it reads as iridescent atmosphere moving across the surface. */
.aurora {
  position: absolute;
  inset: -25%;
  border-radius: 50%;
  background: conic-gradient(
    from 0deg,
    rgb(var(--signal-green-rgb) / 0.45) 0%,
    rgb(var(--signal-violet-rgb) / 0.32) 25%,
    rgb(var(--orb-teal-rgb) / 0.45) 50%,
    rgb(var(--aurora-4-rgb) / 0.32) 75%,
    rgb(var(--signal-green-rgb) / 0.45) 100%
  );
  animation: aurora-rotate 18s linear infinite;
  mix-blend-mode: color-dodge;
  opacity: 0.7;
  filter: blur(14px);
  z-index: 2;
  pointer-events: none;
}

/* Light-band — a diagonal bright sheen that drifts across the orb on a
   slower schedule than the aurora. Combined, they sell "this is spinning". */
.band {
  position: absolute;
  inset: -30%;
  border-radius: 50%;
  background: conic-gradient(
    from 90deg,
    transparent 0%,
    rgb(var(--specular-rgb) / 0.25) 10%,
    transparent 22%,
    transparent 50%,
    rgb(var(--specular-rgb) / 0.12) 62%,
    transparent 75%,
    transparent 100%
  );
  animation: band-rotate 32s linear infinite;
  mix-blend-mode: overlay;
  opacity: 0.6;
  filter: blur(8px);
  z-index: 3;
  pointer-events: none;
}

/* Specular — sits on top, follows cursor. Also gets a subtle drift when
   the cursor is elsewhere via the default specularStyle top/left values. */
.specular {
  position: absolute;
  width: 45%;
  height: 38%;
  border-radius: 50%;
  background: radial-gradient(
    ellipse at 30% 20%,
    rgb(var(--specular-rgb) / 0.78) 0%,
    rgb(var(--specular-rgb) / 0.2) 40%,
    transparent 72%
  );
  filter: blur(4px);
  transition: top 300ms cubic-bezier(0.22, 1, 0.36, 1),
              left 300ms cubic-bezier(0.22, 1, 0.36, 1);
  z-index: 4;
  pointer-events: none;
}

.rim {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  box-shadow:
    inset 0 0 0 1px rgb(var(--specular-rgb) / 0.15),
    inset 0 0 60px rgb(var(--specular-rgb) / 0.05);
  z-index: 5;
  pointer-events: none;
}

/* Cursor hint — soft label at the bottom that fades in on hover */
.cursor-hint {
  position: absolute;
  bottom: 8%;
  left: 50%;
  transform: translateX(-50%);
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgb(var(--fg-body-rgb) / 0.4);
  opacity: 0;
  transition: opacity 300ms ease;
  pointer-events: none;
  z-index: 6;
}
.cursor-hint-visible {
  opacity: 1;
}

/* ─── Keyframes ──────────────────────────────────────────────────────── */
@keyframes aurora-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
@keyframes band-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(-360deg); }
}
@keyframes halo-breathe {
  0%, 100% { opacity: 0.6; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.06); }
}

@media (prefers-reduced-motion: reduce) {
  .aurora,
  .band,
  .halo {
    animation: none;
  }
}
</style>
