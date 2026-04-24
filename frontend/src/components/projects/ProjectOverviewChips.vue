<script setup lang="ts">
import { computed, ref, watch } from "vue";

import { onProjectLiveEvent } from "@/composables/useProjectLive";

const props = defineProps<{ slug: string }>();

interface Stats {
  last_session_at: string | null;
  session_count_7d: number;
  decision_count_total: number;
  secrets_count: number;
  commits_7d: number;
  // env_status is derived client-side from the project aggregate:
  //   - needs_initial_scan: no stack, no infra, no fingerprint → Claude will catalog
  //   - catalogued: has a fingerprint; we show when the scan happened
  env_status: "needs_scan" | "catalogued" | "unknown";
  env_last_scanned: string | null;
  env_tracked_count: number;
}

const stats = ref<Stats | null>(null);

async function load(slug: string) {
  stats.value = null;
  try {
    // Pulled from the activity feed (cheap single call) plus secrets list for
    // secret count, plus the project aggregate so we know env_status.
    // Keep this component's data footprint small — it's a chip row, not a dashboard.
    const [actRes, secRes, projRes] = await Promise.all([
      fetch(`/api/v1/projects/${slug}/activity?limit=200`, { credentials: "include" }),
      fetch(`/api/v1/projects/${slug}/secrets`, { credentials: "include" }),
      fetch(`/api/v1/projects/${slug}`, { credentials: "include" }),
    ]);
    const events = actRes.ok ? await actRes.json() as Array<any> : [];
    const secrets = secRes.ok ? await secRes.json() as Array<any> : [];
    const proj = projRes.ok ? await projRes.json() as any : null;
    if (slug !== props.slug) return;  // stale navigation response

    const now = Date.now();
    const sevenDays = 7 * 24 * 60 * 60 * 1000;
    const sessions = events.filter((e) => e.type === "session");
    const decisions = events.filter((e) => e.type === "decision");
    const sessions7d = sessions.filter((e) => e.at && now - new Date(e.at).getTime() < sevenDays);
    const commits7d = sessions7d.reduce(
      (acc, s) => acc + (s.meta?.commit_count ?? 0),
      0,
    );

    const fp = proj?.context?.env_fingerprint || {};
    const fpFiles = (fp.files && typeof fp.files === "object") ? Object.keys(fp.files) : [];
    const hasFingerprint = fpFiles.length > 0;
    const hasStack = Array.isArray(proj?.stack) && proj.stack.length > 0;
    const hasInfra = proj?.infra && Object.keys(proj.infra).length > 0;
    let envStatus: Stats["env_status"] = "unknown";
    if (hasFingerprint) envStatus = "catalogued";
    else if (!hasStack && !hasInfra) envStatus = "needs_scan";
    // else: project has stack/infra from GitHub import but no fingerprint → unknown
    // (we DON'T nag the user to rescan working projects; Claude will pick this up on next session)

    stats.value = {
      last_session_at: sessions[0]?.at ?? null,
      session_count_7d: sessions7d.length,
      decision_count_total: decisions.length,
      secrets_count: secrets.length,
      commits_7d: commits7d,
      env_status: envStatus,
      env_last_scanned: fp.scanned_at ?? null,
      env_tracked_count: fpFiles.length,
    };
  } catch {
    /* noop — chip row is best-effort */
  }
}

watch(() => props.slug, (slug) => void load(slug), { immediate: true });

// Keep the chip row live: anything that changes the counts (session /
// decision / idea / ship / secret add) should nudge us to re-count.
onProjectLiveEvent(
  ["session.created", "decision.created", "idea.created", "ship.created", "secret.added", "secret.removed"],
  () => void load(props.slug),
);

function relative(iso: string | null): string {
  if (!iso) return "never";
  const ms = Date.now() - new Date(iso).getTime();
  if (ms < 60_000) return "just now";
  if (ms < 3_600_000) return `${Math.floor(ms / 60_000)}m ago`;
  if (ms < 86_400_000) return `${Math.floor(ms / 3_600_000)}h ago`;
  return `${Math.floor(ms / 86_400_000)}d ago`;
}

const hasAny = computed(() => stats.value !== null);
</script>

<template>
  <div
    v-if="hasAny"
    class="flex flex-wrap gap-2 text-small text-fg-muted"
  >
    <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface">
      <span class="w-1 h-1 rounded-full bg-signal-green" />
      <span class="mono-label">last session</span>
      <span class="text-fg-body">{{ relative(stats?.last_session_at ?? null) }}</span>
    </span>
    <span
      v-if="stats && stats.session_count_7d > 0"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface"
    >
      <span class="mono-label">7d</span>
      <span class="tabular-nums text-fg-body">{{ stats.session_count_7d }}</span>
      <span>sessions</span>
    </span>
    <span
      v-if="stats && stats.commits_7d > 0"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface"
    >
      <span class="mono-label">7d</span>
      <span class="tabular-nums text-fg-body">{{ stats.commits_7d }}</span>
      <span>commits</span>
    </span>
    <span
      v-if="stats && stats.decision_count_total > 0"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface"
    >
      <span class="tabular-nums text-fg-body">{{ stats.decision_count_total }}</span>
      <span>decisions</span>
    </span>
    <span
      v-if="stats && stats.secrets_count > 0"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-border bg-bg-surface"
    >
      <span class="tabular-nums text-fg-body">{{ stats.secrets_count }}</span>
      <span>secrets</span>
    </span>
    <!-- env catalog state: needs_scan = Claude will catalog on next session;
         catalogued = green chip with fingerprint age. -->
    <span
      v-if="stats?.env_status === 'needs_scan'"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-signal-amber/40 bg-signal-amber/5 text-signal-amber"
      title="Claude will catalog this project's stack + infra from your local manifests on the next session"
    >
      <span class="w-1 h-1 rounded-full bg-signal-amber" />
      <span class="mono-label">env</span>
      <span>uncatalogued</span>
    </span>
    <span
      v-else-if="stats?.env_status === 'catalogued'"
      class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full border border-signal-green/30 bg-signal-green/5"
      :title="`${stats.env_tracked_count} manifest files fingerprinted. Drift will be surfaced on next session.`"
    >
      <span class="w-1 h-1 rounded-full bg-signal-green" />
      <span class="mono-label">env</span>
      <span class="text-fg-body">catalogued {{ relative(stats.env_last_scanned) }}</span>
    </span>
  </div>
</template>
