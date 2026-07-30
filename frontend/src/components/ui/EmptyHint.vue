<script setup lang="ts">
/**
 * An empty state that says how to fill it.
 *
 * Vibecell's whole premise is that the agent does the work. Every card that
 * says "No decisions recorded yet" and stops is a place where the product
 * forgets to mention that — the user is left to infer that a dashboard field
 * is something they now have to go and type.
 *
 * So each empty state names the tool that fills it. Not as documentation, but
 * as the answer to "what do I do about this": say the thing to Claude, and it
 * calls this.
 *
 * The tool name is rendered rather than described because it is copy-pasteable
 * and unambiguous. "Ask Claude to record a decision" is vaguer than
 * `vibecell_decision`, and the second is what actually appears in the session
 * log afterwards.
 *
 * @example
 * <EmptyHint tool="vibecell_decision">
 *   No decisions recorded yet. ADR-style entries help future-you remember why.
 * </EmptyHint>
 */
withDefaults(
  defineProps<{
    /** MCP tool that populates this surface. Omit for read-only surfaces. */
    tool?: string;
    /** `inline` drops the padding, for use inside a dense row. */
    density?: "card" | "inline";
  }>(),
  { density: "card" },
);
</script>

<template>
  <div :class="density === 'card' ? 'py-2' : ''">
    <p class="text-small text-fg-muted">
      <slot />
    </p>
    <p v-if="tool" class="mt-1.5 text-small text-fg-subtle">
      Ask Claude — it calls
      <code class="font-mono text-fg-body select-all">{{ tool }}</code>
    </p>
  </div>
</template>
