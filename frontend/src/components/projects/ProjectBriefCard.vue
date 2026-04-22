<script setup lang="ts">
/**
 * "Where the fuck was I?" — the morning brief. AI-generated using the user's
 * own Anthropic key (stored as the project's ANTHROPIC_API_KEY secret, or
 * falling back to the platform key). Funny + irreverent by system prompt.
 */
import { ref, watch } from "vue";

import { onProjectLiveEvent } from "@/composables/useProjectLive";

const props = defineProps<{ slug: string }>();

const brief = ref<string>("");
const loading = ref(false);
const err = ref<string | null>(null);
const meta = ref<{
  model?: string;
  key_source?: string;
  input_tokens?: number;
  output_tokens?: number;
} | null>(null);

async function generate() {
  loading.value = true;
  err.value = null;
  try {
    const r = await fetch(`/api/v1/projects/${props.slug}/ai/resume_brief`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    if (!r.ok) {
      const body = await r.json().catch(() => ({}));
      if (r.status === 402) {
        err.value = body.detail ?? "No Anthropic API key configured for this project. Store one via vibecell.secret_set ANTHROPIC_API_KEY.";
      } else {
        err.value = body.detail ?? `Error ${r.status}`;
      }
      return;
    }
    const json = await r.json();
    brief.value = json.brief ?? "";
    meta.value = json.meta ?? null;
  } catch {
    err.value = "Failed to reach the AI service.";
  } finally {
    loading.value = false;
  }
}

// Clear brief when switching project so the old one doesn't flash.
watch(() => props.slug, () => { brief.value = ""; err.value = null; meta.value = null; });

// Live refresh when something material happens (new session, ship, decision).
onProjectLiveEvent(
  ["session.created", "ship.created", "decision.created"],
  () => { if (brief.value) void generate(); },
);

function parseBriefBody(raw: string): { main: string; action: string | null } {
  // The system prompt asks the model to end with an *italicised* concrete action.
  // Split on the last italics span (simple markdown "*text*").
  const match = raw.match(/(.*)\s+\*([^*]+?)\*\s*$/s);
  if (match) {
    return { main: match[1].trim(), action: match[2].trim() };
  }
  return { main: raw.trim(), action: null };
}
</script>

<template>
  <section class="glass rounded-lg p-5">
    <header class="flex items-start justify-between gap-3 mb-3">
      <div>
        <h3 class="mono-label text-signal-green">// where the fuck was i</h3>
        <p class="text-[11px] text-fg-subtle font-mono mt-0.5">
          AI-generated brief, powered by your own key.
        </p>
      </div>
      <button
        class="px-3 h-8 rounded-md text-small font-mono bg-signal-green hover:opacity-90 transition-opacity disabled:opacity-50"
        style="color: #070b10"
        :disabled="loading"
        @click="generate"
      >
        {{ loading ? "…" : (brief ? "regenerate" : "tell me") }}
      </button>
    </header>

    <div v-if="err" class="rounded-md p-3 text-small" style="background: rgba(229,101,101,0.08); border: 1px solid rgba(229,101,101,0.25); color: #e5a5a5">
      {{ err }}
      <p v-if="err.includes('ANTHROPIC_API_KEY')" class="text-[11px] text-fg-subtle mt-1.5">
        Quick fix: ask Claude
        <code class="font-mono text-fg-body">vibecell.secret_set ANTHROPIC_API_KEY sk-ant-…</code>
      </p>
    </div>

    <div v-else-if="!brief && !loading" class="text-small text-fg-subtle py-2">
      Click <em>tell me</em> for a ~150-word "where was I" brief. Summarises your
      last session, next step, open questions, and gives you a single concrete
      action to start with.
    </div>

    <div v-else-if="brief" class="space-y-3">
      <p class="text-body text-fg-body leading-relaxed whitespace-pre-wrap">
        {{ parseBriefBody(brief).main }}
      </p>
      <p
        v-if="parseBriefBody(brief).action"
        class="text-body italic"
        style="color: #5cc8a4; border-left: 2px solid #5cc8a4; padding-left: 10px"
      >→ {{ parseBriefBody(brief).action }}</p>
    </div>

    <footer v-if="meta && brief" class="mt-3 pt-2 border-t border-border text-[10px] font-mono text-fg-subtle flex items-center gap-3 flex-wrap">
      <span>{{ meta.model }}</span>
      <span v-if="meta.key_source === 'project-secret'" class="text-signal-green">your key ✓</span>
      <span v-else class="text-fg-muted">platform key</span>
      <span v-if="meta.input_tokens != null">{{ meta.input_tokens }}→{{ meta.output_tokens }} tokens</span>
    </footer>
  </section>
</template>
