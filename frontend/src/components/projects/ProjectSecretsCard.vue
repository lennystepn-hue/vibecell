<script setup lang="ts">
import { onMounted, ref } from "vue";

import CopyableValue from "@/components/ui/CopyableValue.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";

const props = defineProps<{ project: { slug: string } }>();

interface SecretRow {
  label: string;
  kind: string;
  reference: string;  // either masked ****** for inline, or the op:// path for references
  created_at: string | null;
}

const secrets = ref<SecretRow[]>([]);
const loading = ref(false);
const adding = ref(false);
const newLabel = ref("");
const newValue = ref("");

const expanded = ref<boolean>(
  typeof localStorage !== "undefined"
    ? localStorage.getItem(`vc:card-expanded:secrets:${props.project.slug}`) !== "false"
    : true,
);
function toggle() {
  expanded.value = !expanded.value;
  localStorage.setItem(`vc:card-expanded:secrets:${props.project.slug}`, expanded.value ? "true" : "false");
}

async function load() {
  loading.value = true;
  try {
    const r = await fetch(`/api/v1/projects/${props.project.slug}/secrets`, { credentials: "include" });
    if (r.ok) secrets.value = await r.json();
  } finally {
    loading.value = false;
  }
}

function kindBadge(k: string): { label: string; color: string; title: string } {
  switch (k) {
    case "inline_encrypted": return { label: "encrypted", color: "text-signal-green", title: "Value encrypted at rest with workspace DEK" };
    case "op": return { label: "1password", color: "text-fg-primary", title: "Stored in 1Password — Vibecell only has the path" };
    case "bw": return { label: "bitwarden", color: "text-fg-primary", title: "Stored in Bitwarden — Vibecell only has the path" };
    case "ssh_agent": return { label: "ssh-agent", color: "text-fg-muted", title: "Resolved via ssh-agent at exec time" };
    case "env_path": return { label: "env", color: "text-fg-muted", title: "Read from environment variable at exec time" };
    default: return { label: k, color: "text-fg-muted", title: k };
  }
}

async function save() {
  if (!newLabel.value || !newValue.value) return;
  adding.value = true;
  try {
    const r = await fetch(`/api/v1/projects/${props.project.slug}/secrets`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ label: newLabel.value, value: newValue.value }),
    });
    if (r.ok) {
      newLabel.value = "";
      newValue.value = "";
      await load();
    }
  } finally {
    adding.value = false;
  }
}

async function remove(label: string) {
  if (!confirm(`Remove secret "${label}"?`)) return;
  await fetch(`/api/v1/projects/${props.project.slug}/secrets/${label}`, {
    method: "DELETE",
    credentials: "include",
  });
  await load();
}

onMounted(() => load());
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-center justify-between cursor-pointer select-none" :class="{ 'mb-3': expanded }" @click="toggle">
      <div class="flex items-center gap-2">
        <span class="font-mono text-fg-subtle transition-transform duration-fast" :class="{ 'rotate-90': expanded }">▸</span>
        <h3 class="mono-label text-fg-muted">//secrets</h3>
      </div>
      <span class="text-small text-fg-subtle">{{ secrets.length }} labels</span>
    </header>

    <div v-if="expanded">
      <p v-if="secrets.length === 0" class="text-small text-fg-subtle py-2">
        No secrets yet. Paste an API key or 1Password path — Claude (via vibecell_secret_set) or the + button below will store it securely.
      </p>

      <ul v-else class="space-y-1.5 mb-3">
        <li v-for="s in secrets" :key="s.label" class="flex items-center gap-3 py-1.5 border-b border-border last:border-0">
          <code class="font-mono text-small text-fg-body shrink-0">@{{ s.label }}</code>
          <span class="mono-label text-[10px]" :class="kindBadge(s.kind).color" :title="kindBadge(s.kind).title">
            {{ kindBadge(s.kind).label }}
          </span>
          <span class="flex-1 min-w-0">
            <CopyableValue v-if="s.kind !== 'inline_encrypted'" :value="s.reference" mono small />
            <span v-else class="text-small text-fg-subtle font-mono">******</span>
          </span>
          <button
            class="text-small text-fg-subtle hover:text-signal-red transition-colors"
            @click="remove(s.label)"
            title="Remove"
          >✕</button>
        </li>
      </ul>

      <div class="border-t border-border pt-3">
        <div class="flex items-center gap-2">
          <input
            v-model="newLabel"
            placeholder="LABEL (e.g. DATABASE_URL)"
            class="h-8 px-2 text-small font-mono bg-bg-surface border border-border rounded w-44"
            @keydown.enter="save"
          />
          <input
            v-model="newValue"
            type="password"
            placeholder="value or op://... / bw://... / ssh-agent://..."
            class="h-8 px-2 text-small font-mono bg-bg-surface border border-border rounded flex-1 min-w-0"
            @keydown.enter="save"
          />
          <PrimaryButton :disabled="adding || !newLabel || !newValue" @click="save">
            {{ adding ? "…" : "add" }}
          </PrimaryButton>
        </div>
        <p class="text-[10px] text-fg-subtle mt-2 font-mono">
          Auto-detects kind: op:// → 1Password · bw:// → Bitwarden · ssh-agent:// → SSH · otherwise → AES-256-GCM encrypted at rest
        </p>
      </div>
    </div>
  </section>
</template>
