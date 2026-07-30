<script setup lang="ts">
import DashboardPreview from "@/components/landing/DashboardPreview.vue";
</script>

<template>
<!-- ─── Dashboard preview — SEE what you get, don't just read it. ───── -->
<section class="relative px-6 pb-24">
  <!-- Ambient glow under the preview frame -->
  <div class="absolute inset-x-0 top-1/2 -translate-y-1/2 h-[500px] pointer-events-none"
    style="background: radial-gradient(ellipse 60% 60% at 50% 50%, rgb(var(--signal-green-rgb) / 0.06) 0%, transparent 70%)" />
  <div class="relative max-w-[1280px] mx-auto">
    <DashboardPreview />
    <!-- Caption under the mockup -->
    <p class="text-center mt-6 font-mono text-micro tracking-caps uppercase"
      style="color: var(--fg-subtle)">
      Your actual dashboard — live, realtime, Claude-driven
    </p>
  </div>
</section>
</template>
