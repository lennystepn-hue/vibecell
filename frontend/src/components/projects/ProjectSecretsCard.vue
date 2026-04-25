<script setup lang="ts">
import { ref, watch } from "vue";

import { onProjectLiveEvent } from "@/composables/useProjectLive";
import CopyableValue from "@/components/ui/CopyableValue.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";

const props = defineProps<{ project: { slug: string } }>();

interface SecretRow {
  label: string;
  kind: string;
  reference: string;  // either masked ****** for inline, or the op:// path for references
  created_at: string | null;
  last_used_at: string | null;
}

function relative(iso: string | null): string {
  if (!iso) return "";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

const secrets = ref<SecretRow[]>([]);
const loading = ref(false);
const adding = ref(false);
const newLabel = ref("");
const newValue = ref("");
const error = ref<string | null>(null);

/** Map a free-text value to the backend's `kind` enum.
 *  Keep this in sync with backend/app/schemas/secret.py::_ALLOWED_KINDS. */
function detectKind(value: string): string {
  if (value.startsWith("op://")) return "op";
  if (value.startsWith("bw://")) return "bw";
  if (value.startsWith("ssh-agent://")) return "ssh_agent";
  // Bare $ENV or env://NAME — both treated as env-path lookup
  if (value.startsWith("env://") || /^\$[A-Z_][A-Z0-9_]*$/.test(value)) return "env_path";
  return "inline_encrypted";
}

async function load() {
  const slug = props.project.slug;
  loading.value = true;
  // Clear immediately so stale data from the previous project never flashes.
  secrets.value = [];
  try {
    const r = await fetch(`/api/v1/projects/${slug}/secrets`, { credentials: "include" });
    if (r.ok && slug === props.project.slug) {
      // Guard: only commit the response if we're still on the same project
      // (avoids race when navigating projects fast).
      secrets.value = await r.json();
    }
  } finally {
    if (slug === props.project.slug) loading.value = false;
  }
}

// Re-load whenever the project slug changes (Vue may reuse the component
// across /projects/:slug navigations — without this watch, secrets from
// the previous project would remain visible on the next project's page).
watch(() => props.project.slug, () => load(), { immediate: true });

// Live-refresh when Claude or another tab touches a secret.
onProjectLiveEvent(["secret.added", "secret.removed", "secret.used"], () => void load());

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
  error.value = null;
  try {
    const r = await fetch(`/api/v1/projects/${props.project.slug}/secrets`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        label: newLabel.value,
        kind: detectKind(newValue.value),
        reference: newValue.value,
      }),
    });
    if (r.ok) {
      newLabel.value = "";
      newValue.value = "";
      await load();
    } else {
      // Surface backend errors instead of silently swallowing them.
      let detail = `add failed (HTTP ${r.status})`;
      try {
        const body = await r.json();
        if (body?.detail) {
          detail = typeof body.detail === "string"
            ? body.detail
            : JSON.stringify(body.detail);
        }
      } catch { /* non-JSON response; keep generic message */ }
      error.value = detail;
    }
  } catch (e) {
    error.value = `network error: ${e instanceof Error ? e.message : String(e)}`;
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

</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-center justify-between mb-3 select-none">
      <h3 class="mono-label text-fg-muted">//secrets</h3>
      <span class="text-small text-fg-subtle">{{ secrets.length }} labels</span>
    </header>

    <div>
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
          <span
            v-if="s.last_used_at"
            class="text-[10px] font-mono text-signal-green shrink-0"
            :title="`Last retrieved by Claude on ${new Date(s.last_used_at).toLocaleString()}`"
          >used {{ relative(s.last_used_at) }}</span>
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
        <p
          v-if="error"
          class="text-[11px] text-signal-red mt-2 font-mono break-words"
          role="alert"
        >{{ error }}</p>
        <p class="text-[10px] text-fg-subtle mt-2 font-mono">
          Auto-detects kind: op:// → 1Password · bw:// → Bitwarden · ssh-agent:// → SSH · otherwise → AES-256-GCM encrypted at rest
        </p>
      </div>
    </div>
  </section>
</template>
