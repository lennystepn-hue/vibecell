<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import TopBar from "./TopBar.vue";

const route = useRoute();

// Routes that provide their own full-bleed header (public marketing + auth flows).
// On those routes we render the app chrome WITHOUT TopBar to avoid double headers.
const bareLayoutRoutes = new Set([
  "landing",
  "pricing",
  "legal",
  "login",
  "auth-verify",
  "index",  // IndexRedirect flashes briefly — no need for chrome
]);

const isBare = computed(() => bareLayoutRoutes.has(String(route.name ?? "")));
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <TopBar v-if="!isBare" />
    <main
      :class="isBare ? '' : 'flex-1 min-h-0 overflow-hidden'"
    >
      <slot />
    </main>
  </div>
</template>
