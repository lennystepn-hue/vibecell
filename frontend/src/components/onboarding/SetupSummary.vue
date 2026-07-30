<script setup lang="ts">
/**
 * What the setup actually produced.
 *
 * The design sketch for this screen promised a health triage — "chati, SSL
 * expires in 9 days, untouched for 4 months". That turned out to be
 * impossible at this exact moment, and it is worth writing down why so
 * nobody rebuilds it: health probes run on a five-minute cron, and every
 * project on this screen was created seconds ago. There is no uptime
 * history, no SSL check, no commit-staleness for any of them yet.
 *
 * Ongoing decay is a dashboard concern, and the console's alert bar covers
 * it. What *is* knowable here is what the agent just did, and where it came
 * up short:
 *
 *   • how many projects it created
 *   • which ones it could not read enough of to describe
 *
 * That second one is the useful part. A project created but never enriched
 * means the agent found a repo and couldn't make sense of it — an empty
 * shell the user should look at rather than discover cold in three weeks.
 */
import { computed } from "vue";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useOnboardingStore } from "@/stores/onboarding";

const onboarding = useOnboardingStore();

defineEmits<{ finish: [] }>();

const total = computed(
  () => onboarding.finalProjectCount ?? onboarding.projects.length,
);

/** Created, but the agent never sent an enrichment frame for them. */
const thin = computed(() => onboarding.projects.filter((p) => !p.enriched));

const enriched = computed(() => onboarding.projects.filter((p) => p.enriched));

/** Where "Open" goes: the first project the agent actually understood. */
const firstGood = computed(() => enriched.value[0] ?? onboarding.projects[0]);
</script>

<template>
  <div class="pt-5 mt-6 border-t border-border-subtle">
    <!-- Nothing found. Not a failure — plenty of people set up a machine
         before they put any code on it — but saying "done" here would be
         a lie the user discovers later. -->
    <template v-if="total === 0">
      <p class="text-body text-fg-primary">No repositories found on this machine.</p>
      <p class="text-small text-fg-muted mt-1">
        Nothing went wrong — there was just nothing to import. Create a project by hand,
        or ask Claude to set one up once you have code here.
      </p>
      <PrimaryButton size="lg" class="mt-4" @click="$emit('finish')">
        Go to dashboard →
      </PrimaryButton>
    </template>

    <template v-else>
      <p class="text-body text-fg-primary">
        {{ total }} project{{ total === 1 ? "" : "s" }}
        {{ total === 1 ? "is" : "are" }} in. You typed nothing.
      </p>

      <!-- The one thing worth acting on right now. -->
      <div v-if="thin.length" class="mt-4">
        <p class="text-small text-fg-muted">
          {{ thin.length }} of them Claude couldn't read well enough to describe —
          worth a look:
        </p>
        <ul class="mt-2 space-y-1">
          <li
            v-for="p in thin"
            :key="p.slug"
            class="flex items-center gap-2 font-mono text-small"
          >
            <span class="text-signal-amber shrink-0" aria-hidden="true">○</span>
            <RouterLink
              :to="`/p/${p.slug}`"
              class="text-fg-body hover:text-fg-primary hover:underline underline-offset-2"
            >{{ p.name }}</RouterLink>
          </li>
        </ul>
      </div>

      <p v-else class="text-small text-fg-muted mt-1">
        Claude read every one of them and filled in the pitch, stack and status.
      </p>

      <footer class="mt-5 flex items-center justify-between gap-4 flex-wrap">
        <p v-if="firstGood" class="text-small text-fg-subtle min-w-0">
          Start with
          <span class="font-mono text-fg-body">{{ firstGood.name }}</span>
        </p>
        <PrimaryButton size="lg" @click="$emit('finish')">
          Open {{ firstGood?.name ?? "dashboard" }} →
        </PrimaryButton>
      </footer>
    </template>
  </div>
</template>
