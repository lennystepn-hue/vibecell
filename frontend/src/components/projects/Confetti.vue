<script setup lang="ts">
/**
 * Canvas-less confetti — pure CSS + a small reactive particle list. Fires
 * when the `fire` counter ticks up (watch, not prop-changed-once). Used for
 * ship_created celebrations. ~60 particles × 2s lifetime = cheap.
 */
import { onBeforeUnmount, ref, watch } from "vue";

const props = defineProps<{
  /** Any number — bump it (e.g. ++counter on ship event) to re-fire. */
  fire: number;
}>();

interface Particle {
  id: number;
  x: number;   // 0..100 vw
  delay: number; // ms
  spin: number;  // deg rotation
  scale: number; // 0.6..1.3
  color: string;
  shape: "square" | "circle" | "bar";
}

const particles = ref<Particle[]>([]);
let nextId = 0;
let cleanupTimer: ReturnType<typeof setTimeout> | null = null;

const PALETTE = [
  "var(--signal-green)",
  "#5cc8a4",
  "#8ab4ff",
  "#c084fc",
  "#f5b84a",
  "#ffffff",
];

function launch(count = 60) {
  const shapes: Particle["shape"][] = ["square", "circle", "bar"];
  const batch: Particle[] = [];
  for (let i = 0; i < count; i++) {
    batch.push({
      id: nextId++,
      x: Math.random() * 100,
      delay: Math.random() * 120,
      spin: (Math.random() - 0.5) * 720,
      scale: 0.6 + Math.random() * 0.7,
      color: PALETTE[Math.floor(Math.random() * PALETTE.length)],
      shape: shapes[Math.floor(Math.random() * shapes.length)],
    });
  }
  particles.value = particles.value.concat(batch);
  if (cleanupTimer) clearTimeout(cleanupTimer);
  cleanupTimer = setTimeout(() => {
    particles.value = [];
  }, 3200);
}

watch(() => props.fire, (v, old) => {
  if (v !== old && v > 0) launch();
});

onBeforeUnmount(() => {
  if (cleanupTimer) clearTimeout(cleanupTimer);
});
</script>

<template>
  <Teleport to="body">
    <div
      class="fixed inset-0 pointer-events-none overflow-hidden z-[999]"
      aria-hidden="true"
    >
      <span
        v-for="p in particles"
        :key="p.id"
        class="confetti-piece"
        :class="`shape-${p.shape}`"
        :style="{
          left: p.x + 'vw',
          background: p.color,
          animationDelay: p.delay + 'ms',
          '--spin': p.spin + 'deg',
          '--scale': p.scale,
        }"
      />
    </div>
  </Teleport>
</template>

<style scoped>
.confetti-piece {
  position: absolute;
  top: -16px;
  width: 8px;
  height: 14px;
  will-change: transform, opacity;
  animation: confetti-fall 2.6s cubic-bezier(0.22, 0.61, 0.36, 1) forwards;
  transform-origin: center;
  opacity: 0.9;
}
.shape-circle {
  border-radius: 50%;
  height: 8px;
}
.shape-bar {
  height: 3px;
  width: 14px;
}
@keyframes confetti-fall {
  0% {
    transform: translate3d(0, 0, 0) rotate(0) scale(var(--scale));
    opacity: 0.95;
  }
  35% {
    opacity: 1;
  }
  100% {
    transform: translate3d(0, 105vh, 0) rotate(var(--spin)) scale(var(--scale));
    opacity: 0;
  }
}
</style>
