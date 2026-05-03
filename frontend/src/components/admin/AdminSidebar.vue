<script setup lang="ts">
/**
 * Narrow nav rail for the admin section. Sticks at top:44px (below
 * the global TopBar) and scrolls independently of the content area.
 * Click any item navigates via vue-router; active route gets the
 * green-accent highlight per the .impeccable.md "single accent per
 * surface" rule.
 *
 * Sections are intentionally short — power users navigate by URL too.
 */
import { RouterLink } from "vue-router";

interface NavItem { to: string; label: string; mark: string; hint: string }

const items: NavItem[] = [
  { to: "/admin/overview", label: "overview", mark: "◈", hint: "KPIs · MRR · active-now · system-health" },
  { to: "/admin/users",    label: "users",    mark: "◌", hint: "search + per-user actions" },
  { to: "/admin/coupons",  label: "coupons",  mark: "%", hint: "Stripe coupons CRUD" },
  { to: "/admin/audit",    label: "audit",    mark: "▤", hint: "every admin write logged" },
  { to: "/admin/system",   label: "system",   mark: "⚙", hint: "DB / Redis / cron heartbeats" },
  { to: "/admin/settings", label: "settings", mark: "≡", hint: "admin emails · trial defaults" },
];
</script>

<template>
  <aside
    class="chrome border-r w-[200px] shrink-0 hidden md:flex flex-col h-full"
  >
    <div class="mono-label px-3 pt-3 pb-2 flex items-center gap-2">
      <span class="text-signal-green">◇</span>
      <span>admin</span>
    </div>
    <nav class="flex-1 overflow-y-auto px-1 pb-4 space-y-0.5">
      <RouterLink
        v-for="item in items"
        :key="item.to"
        :to="item.to"
        :title="item.hint"
        :class="[
          'flex items-center gap-2.5 px-2 py-1.5 rounded-md ml-2 mr-1',
          'font-mono text-small',
          'transition-colors duration-fast ease-out',
          'text-fg-muted hover:bg-bg-surface hover:text-fg-body',
        ]"
        active-class="bg-bg-surface-hi text-fg-primary"
      >
        <span class="font-mono text-fg-subtle w-3 text-center">{{ item.mark }}</span>
        <span class="truncate">{{ item.label }}</span>
      </RouterLink>
    </nav>
    <footer class="border-t border-border-subtle px-3 py-2 mono-label">
      <RouterLink to="/p" class="hover:text-fg-body transition-colors">← back to projects</RouterLink>
    </footer>
  </aside>
</template>
