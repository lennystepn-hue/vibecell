<script setup lang="ts">
/**
 * A `Card` that knows which console widget it is.
 *
 * Takes the widget id, looks up its glyph and family in `widget-identity`,
 * and forwards everything else to `Card` untouched. Card components change
 * from `<Card title="health">` to `<WidgetCard id="health" title="health">`
 * and gain their identity for free.
 *
 * The indirection earns its keep by removing a source of drift. Passing
 * `glyph="◎" accent-var="--signal-teal"` at each of sixteen call sites is
 * exactly the pattern that let two emoji survive an emoji purge and let
 * `health` and `sessions` end up sharing a glyph — nobody looks at sixteen
 * files at once.
 */
import { computed, useSlots } from "vue";

import Card from "@/components/ui/Card.vue";
import { FAMILY_ACCENT, FAMILY_ACCENT_RGB, identityFor } from "./widget-identity";

const props = defineProps<{
  /** Widget id as registered in widget-registry. */
  id: string;
  title?: string;
  padding?: "md" | "none";
}>();

const slots = useSlots();

const identity = computed(() => identityFor(props.id));
const accentVar = computed(() =>
  identity.value ? FAMILY_ACCENT[identity.value.family] : undefined,
);
const accentRgbVar = computed(() =>
  identity.value ? FAMILY_ACCENT_RGB[identity.value.family] : undefined,
);
</script>

<template>
  <Card
    :title="props.title"
    :padding="props.padding"
    :glyph="identity?.glyph"
    :accent-var="accentVar"
    :accent-rgb-var="accentRgbVar"
  >
    <template v-for="(_, name) in slots" #[name]="slotProps">
      <slot :name="name" v-bind="slotProps ?? {}" />
    </template>
  </Card>
</template>
