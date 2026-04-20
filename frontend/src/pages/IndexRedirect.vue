<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

onMounted(async () => {
  if (!auth.isAuthed && !auth.loading) {
    await auth.refresh();
  }
  // Spec 4: send unauthed visitors to landing page, authed users to projects
  router.replace(auth.isAuthed ? "/p" : "/landing");
});
</script>

<template>
  <div class="flex items-center justify-center h-[50vh]">
    <p class="mono-label">loading…</p>
  </div>
</template>
