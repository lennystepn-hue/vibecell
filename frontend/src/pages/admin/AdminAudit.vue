<script setup lang="ts">
/**
 * /admin/audit — full admin audit log with filtering. Read-only;
 * the log is append-only by design.
 */
import { computed, onMounted, ref } from "vue";

interface AuditRow {
  id: string; actor_user_id: string; actor_email: string | null;
  action: string; target_type: string | null; target_id: string | null;
  payload: Record<string, unknown>; ip: string | null; at: string;
}

const rows = ref<AuditRow[]>([]);
const loading = ref(false);
const filter = ref("");

async function load() {
  loading.value = true;
  try {
    const r = await fetch("/api/v1/admin/audit-log?limit=200", { credentials: "include" });
    if (r.ok) rows.value = ((await r.json()) as { items: AuditRow[] }).items;
  } finally {
    loading.value = false;
  }
}
onMounted(load);

const filtered = computed(() => {
  const q = filter.value.trim().toLowerCase();
  if (!q) return rows.value;
  return rows.value.filter((r) =>
    r.action.toLowerCase().includes(q)
    || (r.actor_email ?? "").toLowerCase().includes(q)
    || (r.target_id ?? "").toLowerCase().includes(q),
  );
});

function fmtRel(iso: string): string {
  const d = new Date(iso).getTime();
  const diff = Date.now() - d;
  const min = Math.floor(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  return `${Math.floor(hr / 24)}d ago`;
}
</script>

<template>
  <div class="max-w-[1100px] mx-auto px-4 sm:px-8 py-6 sm:py-8">
    <header class="flex items-baseline justify-between mb-6 gap-4 flex-wrap">
      <div>
        <p class="font-mono text-[11px] uppercase tracking-[0.15em] text-signal-green mb-1">// admin · audit</p>
        <h1 class="text-display text-fg-primary tracking-tight">Audit log</h1>
        <p class="text-body text-fg-muted mt-1">Append-only record of every admin write. Searchable by action / actor / target.</p>
      </div>
      <input
        v-model="filter"
        type="text"
        placeholder="filter…"
        class="h-9 px-3 rounded-md text-small font-mono bg-bg-surface border border-border text-fg-primary placeholder:text-fg-subtle w-full sm:w-72"
      />
    </header>

    <section class="glass rounded-lg p-1">
      <div v-if="loading && !rows.length" class="p-4 text-small text-fg-subtle font-mono">loading…</div>
      <div v-else-if="!filtered.length" class="p-4 text-small text-fg-muted">No matching entries.</div>
      <ul v-else class="divide-y divide-border-subtle">
        <li
          v-for="row in filtered"
          :key="row.id"
          class="px-4 py-3 font-mono text-small"
        >
          <div class="flex items-center gap-3 flex-wrap">
            <span :style="{ color: 'var(--signal-amber, #f59e0b)' }">{{ row.action }}</span>
            <span v-if="row.target_type" class="text-fg-subtle text-[11px]">{{ row.target_type }}</span>
            <span v-if="row.target_id" class="text-fg-body text-[11px] truncate max-w-[300px]">{{ row.target_id }}</span>
            <span class="ml-auto text-fg-subtle text-[10px]">{{ fmtRel(row.at) }}</span>
          </div>
          <p class="text-[10px] text-fg-subtle mt-1">
            {{ row.actor_email ?? row.actor_user_id }} · {{ row.ip ?? "?" }}
          </p>
          <pre
            v-if="row.payload && Object.keys(row.payload).length > 0"
            class="text-[10px] text-fg-muted mt-1 overflow-x-auto"
          >{{ JSON.stringify(row.payload) }}</pre>
        </li>
      </ul>
    </section>
  </div>
</template>
