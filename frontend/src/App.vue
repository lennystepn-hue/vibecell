<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";

import AppLayout from "@/components/app/AppLayout.vue";
import CommandPalette from "@/components/palette/CommandPalette.vue";
import CookieConsent from "@/components/app/CookieConsent.vue";
import KeyboardShortcuts from "@/components/app/KeyboardShortcuts.vue";
import { useAuthStore } from "@/stores/auth";
import { usePresenceStore } from "@/stores/presence";
import { useThemeStore } from "@/stores/theme";

const auth = useAuthStore();
const presence = usePresenceStore();
// Boot the theme store so data-theme gets written to <html> from localStorage.
useThemeStore();

// Start/stop presence polling based on auth state — Redis-backed, 5s poll,
// 2.5m aging window. When you're signed in the dashboard shows live pulses
// on any project Claude is actively running tool calls against.
watch(
  () => auth.isAuthed,
  (authed) => {
    if (authed) presence.start(5000);
    else presence.stop();
  },
  { immediate: true },
);
onBeforeUnmount(() => presence.stop());
</script>

<template>
  <AppLayout>
    <RouterView />
  </AppLayout>
  <CommandPalette />
  <KeyboardShortcuts />
  <!-- Mounted globally so the analytics-consent banner appears once
       across any route the user lands on first. Self-hides forever
       once they pick Accept or Decline. -->
  <CookieConsent />
</template>
