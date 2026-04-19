<script setup lang="ts">
import { computed, onMounted, ref, watch } from "vue";
import { useRouter } from "vue-router";

import SettingsNav from "@/components/settings/SettingsNav.vue";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import TextField from "@/components/ui/TextField.vue";

import { api } from "@/api/client";
import { useAuthStore } from "@/stores/auth";
import { useToastStore } from "@/stores/toast";

const auth = useAuthStore();
const toast = useToastStore();
const router = useRouter();

const workspaceName = ref("");
const savingWs = ref(false);
const loggingOut = ref(false);

onMounted(async () => {
  if (!auth.isAuthed) await auth.refresh();
  workspaceName.value = auth.activeWorkspace?.name ?? "";
});

watch(
  () => auth.activeWorkspace?.name,
  (n) => {
    if (!workspaceName.value && n) workspaceName.value = n;
  },
);

const wsNameDirty = computed(
  () => workspaceName.value.trim().length > 0 && workspaceName.value !== auth.activeWorkspace?.name,
);

async function saveWorkspace() {
  if (!auth.activeWorkspace) return;
  savingWs.value = true;
  const { error } = await api.PATCH("/api/v1/workspaces/{slug}", {
    params: { path: { slug: auth.activeWorkspace.slug } },
    body: { name: workspaceName.value.trim() },
  });
  savingWs.value = false;
  if (error) {
    toast.push("Couldn't save workspace name", "error");
    return;
  }
  await auth.refresh();
  toast.push("Workspace updated", "success");
}

async function logout() {
  loggingOut.value = true;
  await auth.logout();
  loggingOut.value = false;
  router.push("/login");
}
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <SettingsNav />
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-[720px] mx-auto px-8 py-8">
        <h1 class="text-display text-fg-primary tracking-tight mb-8">Settings</h1>

        <SettingsSection title="Account" subtitle="Identity associated with this session.">
          <div class="space-y-3">
            <div class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
              <span class="mono-label">email</span>
              <span class="font-mono text-body text-fg-body">{{ auth.user?.email ?? "—" }}</span>
            </div>
            <div v-if="auth.user?.handle" class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
              <span class="mono-label">handle</span>
              <span class="font-mono text-body text-fg-body">@{{ auth.user.handle }}</span>
            </div>
            <div class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
              <span class="mono-label">user id</span>
              <span class="font-mono text-small text-fg-subtle">{{ auth.user?.id ?? "—" }}</span>
            </div>
          </div>
        </SettingsSection>

        <SettingsSection
          title="Workspace"
          :subtitle="`Active workspace — ${auth.activeWorkspace?.slug ?? '—'}`"
        >
          <div class="space-y-4">
            <TextField
              v-model="workspaceName"
              label="name"
              :disabled="savingWs"
            />
            <div class="flex justify-end">
              <PrimaryButton
                :disabled="!wsNameDirty || savingWs"
                :loading="savingWs"
                @click="saveWorkspace"
              >
                Save workspace
              </PrimaryButton>
            </div>
            <p class="mono-label opacity-50">
              // slug cannot be changed — open a new workspace if you need a different one
            </p>
          </div>
        </SettingsSection>

        <SettingsSection
          title="Session"
          subtitle="Sign out of this browser."
        >
          <button
            type="button"
            class="h-10 px-4 rounded-md font-medium text-body transition-colors"
            :style="{
              background: 'var(--signal-red-bg)',
              color: 'var(--signal-red)',
              border: '1px solid var(--signal-red)',
            }"
            :disabled="loggingOut"
            @click="logout"
          >
            {{ loggingOut ? "Signing out…" : "Sign out" }}
          </button>
        </SettingsSection>
      </div>
    </div>
  </div>
</template>
