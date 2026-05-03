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

const newEmail = ref("");
const requestingChange = ref(false);
const changeSent = ref(false);

const exporting = ref(false);
const deleteConfirmation = ref("");
const deleting = ref(false);
const showDeleteModal = ref(false);

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

async function requestEmailChange() {
  if (!newEmail.value || newEmail.value === auth.user?.email) return;
  requestingChange.value = true;
  changeSent.value = false;
  try {
    const r = await fetch("/api/v1/me/change-email", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ new_email: newEmail.value.trim().toLowerCase() }),
    });
    // Backend always returns 202 (no email-enumeration), so we always show
    // the same "we sent you a link" state — even if the address is taken.
    // The user finds out by either receiving or not receiving the mail.
    if (r.ok || r.status === 202) {
      changeSent.value = true;
    } else {
      toast.push("Couldn't request email change", "error");
    }
  } catch (e) {
    toast.push(`Network error: ${e instanceof Error ? e.message : String(e)}`, "error");
  } finally {
    requestingChange.value = false;
  }
}

async function downloadExport() {
  exporting.value = true;
  try {
    const r = await fetch("/api/v1/me/export", { credentials: "include" });
    if (!r.ok) {
      toast.push("Couldn't generate export", "error");
      return;
    }
    const blob = await r.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `vibecell-export-${auth.user?.id ?? "me"}.json`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } finally {
    exporting.value = false;
  }
}

async function deleteAccount() {
  if (!auth.user) return;
  if (deleteConfirmation.value.trim().toLowerCase() !== auth.user.email.toLowerCase()) {
    toast.push("Confirmation must match your email exactly", "error");
    return;
  }
  deleting.value = true;
  try {
    const r = await fetch("/api/v1/me", {
      method: "DELETE",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ confirmation: deleteConfirmation.value.trim().toLowerCase() }),
    });
    if (r.ok || r.status === 204) {
      // Account is gone — drop client state and bounce to landing.
      auth.$reset?.();
      window.location.replace("/");
    } else {
      let detail = `delete failed (HTTP ${r.status})`;
      try {
        const body = await r.json();
        if (body?.detail) {
          detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
        }
      } catch { /* keep generic */ }
      toast.push(detail, "error");
      showDeleteModal.value = false;
    }
  } catch (e) {
    toast.push(`Network error: ${e instanceof Error ? e.message : String(e)}`, "error");
  } finally {
    deleting.value = false;
  }
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
      <div class="max-w-[720px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
        <h1 class="text-display text-fg-primary tracking-tight mb-8">Settings</h1>

        <SettingsSection title="Account" subtitle="Identity associated with this session.">
          <div class="space-y-3">
            <div class="grid grid-cols-[88px_1fr] sm:grid-cols-[120px_1fr] gap-3 items-baseline">
              <span class="mono-label">email</span>
              <span class="font-mono text-body text-fg-body">{{ auth.user?.email ?? "—" }}</span>
            </div>
            <div v-if="auth.user?.handle" class="grid grid-cols-[88px_1fr] sm:grid-cols-[120px_1fr] gap-3 items-baseline">
              <span class="mono-label">handle</span>
              <span class="font-mono text-body text-fg-body">@{{ auth.user.handle }}</span>
            </div>
            <div class="grid grid-cols-[88px_1fr] sm:grid-cols-[120px_1fr] gap-3 items-baseline">
              <span class="mono-label">user id</span>
              <span class="font-mono text-small text-fg-subtle">{{ auth.user?.id ?? "—" }}</span>
            </div>
          </div>
        </SettingsSection>

        <SettingsSection
          title="Change email"
          subtitle="Move your account to a different address. We'll send a confirmation link to the new email."
        >
          <div class="space-y-4">
            <p
              v-if="changeSent"
              class="text-small text-fg-body p-3 border rounded"
              :style="{ background: 'var(--signal-green-bg)', borderColor: 'var(--signal-green)' }"
            >
              Sent — click the link in the new mailbox to finish the switch.
              The link expires in 24 hours.
            </p>
            <TextField
              v-model="newEmail"
              label="new email"
              type="email"
              placeholder="you@new-address.com"
              :disabled="requestingChange"
            />
            <div class="flex justify-end">
              <PrimaryButton
                :disabled="!newEmail || newEmail === auth.user?.email || requestingChange"
                :loading="requestingChange"
                @click="requestEmailChange"
              >
                Send confirmation link
              </PrimaryButton>
            </div>
            <p class="mono-label opacity-50">
              // your current sessions stay signed in until the new address confirms
            </p>
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
          title="Your data"
          subtitle="Download every row Vibecell stores about you (GDPR Art. 20)."
        >
          <PrimaryButton :disabled="exporting" :loading="exporting" @click="downloadExport">
            Download JSON export
          </PrimaryButton>
          <p class="mono-label opacity-50 mt-3">
            // includes: user · workspaces · projects · sessions · decisions · ideas · ships · audit log · cli devices · tokens
          </p>
        </SettingsSection>

        <SettingsSection
          title="Danger zone"
          subtitle="Permanently delete your account and all data (GDPR Art. 17)."
        >
          <div
            class="rounded p-4 border space-y-3"
            :style="{ background: 'var(--signal-red-bg)', borderColor: 'var(--signal-red)' }"
          >
            <p class="text-small text-fg-body">
              Deleting your account removes your user row, every workspace where you're the only member,
              and all projects, sessions, decisions, ideas, ships, audit logs, CLI devices and tokens
              attached to them. <strong>This cannot be undone.</strong>
            </p>
            <p class="text-small text-fg-muted font-mono">
              If you co-own a workspace with others, transfer ownership or remove the other members first
              — the delete will refuse with a 409 otherwise.
            </p>
            <button
              v-if="!showDeleteModal"
              type="button"
              class="h-9 px-3 rounded text-body font-medium transition-colors"
              :style="{ background: 'var(--signal-red)', color: 'var(--bg-canvas)' }"
              @click="showDeleteModal = true"
            >
              Delete my account
            </button>

            <div v-else class="space-y-3 pt-1">
              <p class="text-small text-fg-body">
                Type <code class="font-mono text-signal-red">{{ auth.user?.email }}</code> below to confirm.
              </p>
              <input
                v-model="deleteConfirmation"
                type="email"
                placeholder="your@email.address"
                autocomplete="off"
                class="h-9 px-2 text-small font-mono bg-bg-surface border rounded w-full"
                :style="{ borderColor: 'var(--signal-red)' }"
                :disabled="deleting"
              />
              <div class="flex gap-2 justify-end">
                <button
                  type="button"
                  class="h-9 px-3 rounded text-body transition-colors"
                  :style="{ border: '1px solid var(--border)' }"
                  :disabled="deleting"
                  @click="showDeleteModal = false; deleteConfirmation = ''"
                >Cancel</button>
                <button
                  type="button"
                  class="h-9 px-3 rounded text-body font-medium transition-colors"
                  :style="{ background: 'var(--signal-red)', color: 'var(--bg-canvas)' }"
                  :disabled="deleting || deleteConfirmation.trim().toLowerCase() !== auth.user?.email?.toLowerCase()"
                  @click="deleteAccount"
                >{{ deleting ? "Deleting…" : "Yes, delete forever" }}</button>
              </div>
            </div>
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
