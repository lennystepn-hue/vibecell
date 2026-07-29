<script setup lang="ts">
/**
 * The card shell. Every panel on the project console and most panels
 * elsewhere are this: a glass surface, an optional mono header with a `//`
 * prefix, an optional meta suffix, an optional right-hand action, and a body.
 *
 * Why this exists: the same markup was hand-written 16 times across the
 * console widgets alone —
 *
 *   <section class="glass rounded-lg p-5">
 *     <header class="flex items-center justify-between mb-4 select-none">
 *       <h3 class="mono-label text-fg-muted">//sessions</h3>
 *       …
 *
 * — and it had already drifted: some headers used `mb-3`, some `mb-4`, some
 * carried `select-none` and some did not. Those inconsistencies are now
 * decided in one place. `mb-4` and `select-none` won.
 *
 * Layout classes pass straight through: Vue merges `class` onto the root, so
 * `<Card class="flex flex-col h-full min-h-0">` still works for the cards
 * that need to fill their grid cell.
 *
 * @example
 * <Card title="sessions">
 *   <template #meta>({{ count }})</template>
 *   <template #actions>
 *     <button class="mono-label hover:text-fg-body" @click="open">+ log session</button>
 *   </template>
 *   <ul>…</ul>
 * </Card>
 */
withDefaults(
  defineProps<{
    /** Rendered as `//title` in the header. Omit for a card with no header. */
    title?: string;
    /**
     * `md` is the standard 20px inset. `none` hands padding to the caller —
     * for cards whose body runs edge to edge (lists with full-bleed rows).
     */
    padding?: "md" | "none";
    /**
     * `accent` marks the one card on a page that carries the answer — the
     * decision on a decision page, the verdict in a list of context. Amber
     * title and border. Use it once per view or it stops meaning anything.
     */
    tone?: "default" | "accent";
  }>(),
  { padding: "md", tone: "default" },
);
</script>

<template>
  <section
    class="glass rounded-lg"
    :class="[
      padding === 'md' ? 'p-5' : 'p-0 overflow-hidden',
      tone === 'accent' ? 'border-signal-amber/25' : '',
    ]"
  >
    <header
      v-if="title || $slots.meta || $slots.actions"
      class="flex items-center justify-between mb-4 select-none"
      :class="padding === 'none' ? 'px-5 pt-5' : ''"
    >
      <h3 class="mono-label" :class="tone === 'accent' ? 'text-signal-amber' : 'text-fg-muted'">
        <!-- Dimmed `//` matches MonoLabel, which the page-level cards already
             used. Two conventions for the same mark is one too many. -->
        <template v-if="title"><span class="opacity-60">//</span>{{ title }}</template>
        <span v-if="$slots.meta" class="opacity-60"> <slot name="meta" /></span>
      </h3>
      <slot name="actions" />
    </header>

    <slot />
  </section>
</template>
