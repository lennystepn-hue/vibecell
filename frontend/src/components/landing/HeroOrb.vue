<script setup lang="ts">
/**
 * Hero orb — large, slowly-rotating glass sphere for the landing hero.
 *
 * Layered as:
 *   1. Outer halo (pulsing glow, off-canvas)
 *   2. Core body (stationary radial-gradient blobs in brand + complementary tones)
 *   3. Aurora (rotating conic-gradient overlay, mix-blend-mode: color-dodge)
 *   4. Specular highlight (slow drift for floating-glass feel)
 *   5. Inner rim (subtle 1px ring for edge definition)
 *
 * All CSS, no canvas, no images. Honors prefers-reduced-motion via a global
 * media-query override in tokens.css (which already zeroes dur-* vars).
 */
</script>

<template>
  <div class="hero-orb" aria-hidden="true">
    <div class="halo" />
    <div class="orb-container">
      <div class="aurora" />
      <div class="body" />
      <div class="specular" />
      <div class="rim" />
    </div>
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
}

/* ─── Outer glow halo — breathing, very soft, off the orb edge ────────── */
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

/* ─── Main orb container ─────────────────────────────────────────────── */
.orb-container {
  position: relative;
  width: 82%;
  aspect-ratio: 1;
  max-width: 420px;
  max-height: 420px;
  border-radius: 50%;
  overflow: hidden;
  z-index: 1;
  box-shadow:
    0 40px 100px rgba(92, 200, 164, 0.22),
    0 20px 50px rgba(181, 146, 255, 0.12),
    0 0 0 1px rgba(255, 255, 255, 0.08);
}

/* ─── Core body — stationary radial blobs in mint + violet + soft pink ─ */
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

/* ─── Aurora — rotating conic shimmer, blends onto the body ──────────── */
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
}

/* ─── Specular — top-left glass highlight, drifts subtly ─────────────── */
.specular {
  position: absolute;
  top: 10%;
  left: 15%;
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
  animation: specular-drift 12s ease-in-out infinite;
  z-index: 3;
  pointer-events: none;
}

/* ─── Rim — thin inner ring for edge definition ─────────────────────── */
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

/* ─── Keyframes ──────────────────────────────────────────────────────── */
@keyframes aurora-rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

@keyframes halo-breathe {
  0%, 100% { opacity: 0.55; transform: scale(1); }
  50% { opacity: 1; transform: scale(1.08); }
}

@keyframes specular-drift {
  0%, 100% { transform: translate(0, 0) scale(1); }
  33% { transform: translate(8px, -6px) scale(1.05); }
  66% { transform: translate(-4px, 4px) scale(0.98); }
}

/* Respect user preference to avoid motion */
@media (prefers-reduced-motion: reduce) {
  .aurora,
  .halo,
  .specular {
    animation: none;
  }
}
</style>
