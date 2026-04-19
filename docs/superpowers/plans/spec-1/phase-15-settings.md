# Phase 15 — Settings

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** `/settings` — account identity + workspace rename + integrations (currently: GitHub connect/disconnect) + logout.

**Prerequisite:** Phase 14 complete (HEAD ≥ `75d38ab`).

---

## Routes

```
/settings                       → account + workspace + logout
/settings/integrations          → integrations list (github only in v1)
```

---

## Files

```
frontend/src/
├── pages/
│   ├── Settings.vue                 main
│   └── SettingsIntegrations.vue     /settings/integrations
├── components/
│   └── settings/
│       ├── SettingsNav.vue          sidebar nav (Account, Workspace, Integrations)
│       └── SettingsSection.vue      uniform section wrapper
└── router/index.ts                  (modify) add /settings + /settings/integrations
```

---

## Task 15.1 — SettingsNav + SettingsSection

**File:** `frontend/src/components/settings/SettingsNav.vue`

```vue
<script setup lang="ts">
import { RouterLink, useRoute } from "vue-router";

const route = useRoute();

const items = [
  { path: "/settings", label: "account" },
  { path: "/settings/integrations", label: "integrations" },
];
</script>

<template>
  <nav class="chrome border-r w-[180px] shrink-0 flex flex-col h-full">
    <div class="mono-label px-3 pt-3 pb-2">settings</div>
    <div class="flex-1 overflow-y-auto px-1">
      <RouterLink
        v-for="i in items"
        :key="i.path"
        :to="i.path"
        :class="[
          'block px-3 py-2 rounded-md mono text-small',
          'transition-colors duration-fast ease-out',
          route.path === i.path
            ? 'bg-bg-surface-hi text-fg-primary'
            : 'text-fg-muted hover:bg-bg-surface/60 hover:text-fg-body',
        ]"
      >
        {{ i.label }}
      </RouterLink>
    </div>
  </nav>
</template>
```

**File:** `frontend/src/components/settings/SettingsSection.vue`

```vue
<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>();
</script>

<template>
  <section class="glass rounded-lg p-6 mb-5">
    <header class="mb-5">
      <h2 class="text-section text-fg-primary tracking-tight">{{ title }}</h2>
      <p v-if="subtitle" class="text-small text-fg-muted mt-1">{{ subtitle }}</p>
    </header>
    <slot />
  </section>
</template>
```

Commit: `feat(frontend): SettingsNav + SettingsSection components`

---

## Task 15.2 — `/settings` page (account + workspace)

**File:** `frontend/src/pages/Settings.vue`

```vue
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
```

Commit: `feat(frontend): /settings page — account identity + workspace rename + logout`

---

## Task 15.3 — `/settings/integrations` page

**File:** `frontend/src/pages/SettingsIntegrations.vue`

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";

import SettingsNav from "@/components/settings/SettingsNav.vue";
import SettingsSection from "@/components/settings/SettingsSection.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";

import { api } from "@/api/client";
import { useToastStore } from "@/stores/toast";
import type { components } from "@/api/types.gen";

type Integration = components["schemas"]["IntegrationOut"];

const toast = useToastStore();
const loading = ref(true);
const integrations = ref<Integration[]>([]);
const disconnecting = ref(false);

async function load() {
  loading.value = true;
  const { data } = await api.GET("/api/v1/integrations");
  loading.value = false;
  integrations.value = data ?? [];
}

async function disconnectGithub() {
  if (!confirm("Disconnect GitHub? Your existing projects stay; you just lose repo-sync.")) return;
  disconnecting.value = true;
  const { error } = await api.DELETE("/api/v1/integrations/github");
  disconnecting.value = false;
  if (error) {
    toast.push("Couldn't disconnect GitHub", "error");
    return;
  }
  toast.push("GitHub disconnected", "success");
  await load();
}

onMounted(load);

function ghLogin(i: Integration): string {
  return (i.config as { login?: string } | undefined)?.login ?? "—";
}

function connectedOn(iso: string): string {
  return new Date(iso).toISOString().slice(0, 10);
}
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <SettingsNav />
    <div class="flex-1 overflow-y-auto">
      <div class="max-w-[720px] mx-auto px-8 py-8">
        <h1 class="text-display text-fg-primary tracking-tight mb-8">Integrations</h1>

        <div v-if="loading" class="text-fg-muted">
          <p class="mono-label">loading…</p>
        </div>

        <template v-else>
          <SettingsSection title="GitHub" subtitle="Read-only access to repo metadata.">
            <template v-for="i in integrations.filter((x) => x.kind === 'github')" :key="i.id">
              <div class="space-y-3">
                <div class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
                  <span class="mono-label">login</span>
                  <span class="font-mono text-body text-fg-body">{{ ghLogin(i) }}</span>
                </div>
                <div class="grid grid-cols-[120px_1fr] gap-3 items-baseline">
                  <span class="mono-label">connected</span>
                  <span class="font-mono text-small text-fg-subtle">{{ connectedOn(i.connected_at) }}</span>
                </div>
                <div class="flex justify-end pt-2">
                  <button
                    type="button"
                    class="h-10 px-4 rounded-md font-medium text-body transition-colors"
                    :style="{
                      background: 'var(--signal-red-bg)',
                      color: 'var(--signal-red)',
                      border: '1px solid var(--signal-red)',
                    }"
                    :disabled="disconnecting"
                    @click="disconnectGithub"
                  >
                    {{ disconnecting ? "Disconnecting…" : "Disconnect GitHub" }}
                  </button>
                </div>
              </div>
            </template>

            <template v-if="integrations.filter((x) => x.kind === 'github').length === 0">
              <p class="text-fg-muted mb-4">No GitHub integration yet.</p>
              <a
                href="/api/v1/integrations/github/oauth-start"
                class="inline-flex h-10 items-center gap-2 rounded-md px-4 font-medium text-body"
                :style="{ background: 'var(--signal-green)', color: 'var(--bg-body-to)' }"
              >Connect GitHub</a>
            </template>
          </SettingsSection>

          <SettingsSection title="More integrations" subtitle="Coming in Spec 4+">
            <ul class="space-y-2 text-small text-fg-muted">
              <li>// Stripe — billing + MRR sync</li>
              <li>// Vercel — deploy + build metadata</li>
              <li>// Cloudflare — DNS + domain inventory</li>
              <li>// Linear — task sync to open_questions</li>
            </ul>
          </SettingsSection>
        </template>
      </div>
    </div>
  </div>
</template>
```

Commit: `feat(frontend): /settings/integrations page — GitHub connect/disconnect`

---

## Task 15.4 — Router wire-up

Modify `frontend/src/router/index.ts` — add:

```ts
{
  path: "/settings",
  name: "settings",
  component: () => import("@/pages/Settings.vue"),
},
{
  path: "/settings/integrations",
  name: "settings-integrations",
  component: () => import("@/pages/SettingsIntegrations.vue"),
},
```

Commit: `feat(frontend): router — /settings + /settings/integrations routes`

---

## Phase 15 complete when

- [ ] `/settings` shows account identity, workspace rename form, sign-out button.
- [ ] `/settings/integrations` shows GitHub connect/disconnect + "Coming in Spec 4+" placeholder list.
- [ ] Workspace name save PATCHes and refreshes auth state.
- [ ] Sign-out clears cookie + navigates to `/login`.
- [ ] Disconnect GitHub DELETEs + refreshes.
- [ ] `pnpm typecheck` + `pnpm test --run` + `pnpm build` green.
- [ ] 4 commits on main (15.1–15.4).
