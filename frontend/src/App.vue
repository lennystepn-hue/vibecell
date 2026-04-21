<script setup lang="ts">
import { onBeforeUnmount, watch } from "vue";

import AppLayout from "@/components/app/AppLayout.vue";
import CommandPalette from "@/components/palette/CommandPalette.vue";
import { useAuthStore } from "@/stores/auth";
import { usePresenceStore } from "@/stores/presence";

const auth = useAuthStore();
const presence = usePresenceStore();

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
</template>
