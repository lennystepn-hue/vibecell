<script setup lang="ts">
import { computed } from "vue";
import { useRoute } from "vue-router";

import TopBar from "./TopBar.vue";
import TrialBanner from "./TrialBanner.vue";
import { useAuthStore } from "@/stores/auth";

const route = useRoute();
const auth = useAuthStore();

// Routes that provide their own full-bleed header (public marketing + auth flows).
// On those routes we render the app chrome WITHOUT TopBar to avoid double headers.
const bareLayoutRoutes = new Set([
  "landing",
  "pricing",
  "legal",
  "login",
  "auth-verify",
  "auth-change-email-confirm",
]);

const isBare = computed(() => bareLayoutRoutes.has(String(route.name ?? "")));
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <TrialBanner v-if="!isBare && auth.isAuthed" />
    <TopBar v-if="!isBare" />
    <main
      :class="isBare ? '' : 'flex-1 min-h-0 overflow-hidden'"
    >
      <slot />
    </main>
  </div>
</template>
