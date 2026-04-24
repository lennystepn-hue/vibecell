<script setup lang="ts">
/**
 * Hero orb — large glass sphere that:
 *   - continuously rotates on its Y-axis at a slow ambient pace
 *   - responds to cursor: tilt follows the pointer, specular highlight
 *     moves toward the cursor so the orb feels like a physical object
 *     you can nudge
 *   - returns to ambient rotation when the pointer leaves
 *
 * Layers:
 *   1. Outer halo (pulsing glow)
 *   2. Rotating 3D container — the orb tilts here
 *   3. Core body (stationary radial-gradient blobs)
 *   4. Aurora (rotating conic-gradient overlay, color-dodge blend)
 *   5. Specular highlight (follows the cursor, falls back to slow drift)
 *   6. Inner rim (1px ring for edge definition)
 */
import { computed, onBeforeUnmount, onMounted, ref } from "vue";

const root = ref<HTMLElement | null>(null);

// Mouse-controlled tilt (-1..1). Smoothed by a CSS transition.
const tiltX = ref(0);
const tiltY = ref(0);
// Auto Y-rotation — ticks continuously so the orb has presence even when
// idle. Pauses while the cursor is inside so the user's tilt isn't fighting
// the animation.
const autoYaw = ref(0);
const hovering = ref(false);
// Normalised pointer position inside the orb (-0.5..0.5 on each axis),
// used to place the specular highlight so the glint follows the cursor.
const pointerX = ref(0);
const pointerY = ref(-0.15);  // initial: top-left-ish default position

let rafId: number | null = null;
let lastT = performance.now();

function tick(now: number) {
  const dt = (now - lastT) / 1000;
  lastT = now;
  if (!hovering.value) {
    // 30-second full rotation
    autoYaw.value = (autoYaw.value + dt * 12) % 360;
  }
  rafId = requestAnimationFrame(tick);
}

onMounted(() => {
  rafId = requestAnimationFrame((t) => {
    lastT = t;
    tick(t);
  });
});
onBeforeUnmount(() => {
  if (rafId !== null) cancelAnimationFrame(rafId);
});

function onMove(e: MouseEvent) {
  if (!root.value) return;
  hovering.value = true;
  const rect = root.value.getBoundingClientRect();
  const nx = (e.clientX - rect.left) / rect.width - 0.5;   // -0.5 .. 0.5
  const ny = (e.clientY - rect.top) / rect.height - 0.5;
  tiltX.value = -ny * 24;  // rotateX: pointer-down → front tips down
  tiltY.value = nx * 28;   // rotateY: pointer-right → right edge comes forward
  pointerX.value = nx;
  pointerY.value = ny;
}

function onLeave() {
  hovering.value = false;
  tiltX.value = 0;
  tiltY.value = 0;
  pointerX.value = 0;
  pointerY.value = -0.15;
}

const orbTransform = computed(
  () => `perspective(900px) rotateX(${tiltX.value}deg) rotateY(${tiltY.value + autoYaw.value}deg)`,
);

const specularStyle = computed(() => ({
  // Map normalised pointer (-0.5..0.5) → specular position (0..100%),
  // slightly biased toward top-left so the default looks natural.
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
    <div class="orb-container" :style="{ transform: orbTransform }">
      <div class="aurora" />
      <div class="body" />
      <div class="specular" :style="specularStyle" />
      <div class="rim" />
    </div>
    <!-- Micro cursor-hint, appears when pointer is near the orb -->
    <div
      class="cursor-hint"
      :class="{ 'cursor-hint-visible': hovering }"
      aria-hidden="true"
    >drag me</div>
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
  cursor: grab;
}
.hero-orb:active {
  cursor: grabbing;
}

/* ─── Outer halo — breathing, very soft, off the orb edge ────────────── */
.halo {
  position: absolute;
  inset: -10%;
  border-radius: 50%;
  background: radial-gradient(
    circle,
    rgba(92, 200, 164, 0.18) 0%,
    rgba(181, 146, 255, 0.08) 35%,
    transparent 65%
  );
  filter: blur(60px);
  animation: halo-breathe 8s ease-in-out infinite;
  pointer-events: none;
  z-index: 0;
}

/* ─── Main orb — tilts via inline transform ──────────────────────────── */
.orb-container {
  position: relative;
  width: 82%;
  aspect-ratio: 1;
  max-width: 440px;
  max-height: 440px;
  border-radius: 50%;
  overflow: hidden;
  z-index: 1;
  transform-style: preserve-3d;
  transition: transform 400ms cubic-bezier(0.22, 1, 0.36, 1);
  box-shadow:
    0 40px 100px rgba(92, 200, 164, 0.22),
    0 20px 50px rgba(181, 146, 255, 0.12),
    0 0 0 1px rgba(255, 255, 255, 0.08);
  will-change: transform;
}

.body {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  background:
    radial-gradient(circle at 30% 28%, #b592ff 0%, transparent 45%),
    radial-gradient(circle at 70% 70%, #5cc8a4 0%, transparent 50%),
    radial-gradient(circle at 50% 95%, #ff6b9d 0%, transparent 55%),
    radial-gradient(circle at 80% 20%, #7dffd4 0%, transparent 35%),
    linear-gradient(135deg, #3a8f75 0%, #6b4aa8 100%);
  box-shadow:
    inset 0 -60px 120px rgba(0, 0, 0, 0.35),
    inset 0 40px 80px rgba(255, 255, 255, 0.12);
  z-index: 1;
}

.aurora {
  position: absolute;
  inset: -20%;
  border-radius: 50%;
  background: conic-gradient(
    from 0deg,
    rgba(92, 200, 164, 0.35) 0%,
    rgba(181, 146, 255, 0.25) 25%,
    rgba(125, 255, 212, 0.35) 50%,
    rgba(255, 107, 157, 0.25) 75%,
    rgba(92, 200, 164, 0.35) 100%
  );
  animation: aurora-rotate 22s linear infinite;
  mix-blend-mode: color-dodge;
  opacity: 0.55;
  filter: blur(12px);
  z-index: 2;
  pointer-events: none;
}

.specular {
  position: absolute;
  width: 45%;
  height: 38%;
  border-radius: 50%;
  background: radial-gradient(
    ellipse at 30% 20%,
    rgba(255, 255, 255, 0.75) 0%,
    rgba(255, 255, 255, 0.2) 40%,
    transparent 70%
  );
  filter: blur(4px);
  transition: top 250ms cubic-bezier(0.22, 1, 0.36, 1),
              left 250ms cubic-bezier(0.22, 1, 0.36, 1);
  z-index: 3;
  pointer-events: none;
}

.rim {
  position: absolute;
  inset: 0;
  border-radius: 50%;
  box-shadow:
    inset 0 0 0 1px rgba(255, 255, 255, 0.15),
    inset 0 0 60px rgba(255, 255, 255, 0.05);
  z-index: 4;
  pointer-events: none;
}

/* ─── Cursor hint ────────────────────────────────────────────────────── */
.cursor-hint {
  position: absolute;
  bottom: 6%;
  left: 50%;
  transform: translateX(-50%);
  font-family: var(--font-mono, ui-monospace, monospace);
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: rgba(207, 212, 220, 0.5);
  opacity: 0;
  transition: opacity 300ms ease;
  pointer-events: none;
  z-index: 5;
}
.cursor-hint-visible {
  opacity: 1;
}

/* ─── Keyframes ──────────────────────────────────────────────────────── */
@keyframes aurora-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes halo-breathe {
  0%, 100% { opacity: 0.55; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.08); }
}

@media (prefers-reduced-motion: reduce) {
  .aurora,
  .halo {
    animation: none;
  }
  .orb-container {
    transition: none;
  }
}
</style>
