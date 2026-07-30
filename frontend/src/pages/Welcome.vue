<script setup lang="ts">
/**
 * Onboarding page — a thin host around `SetupFlow`.
 *
 * The flow itself moved into `components/onboarding/SetupFlow.vue` because it
 * has a second home: the connect modal, reachable by every account that
 * already has projects. Keeping the markup here meant only brand-new signups
 * ever saw the rebuilt setup, while everyone else kept the old six-tab
 * dialog — which is exactly how that dialog survived the rewrite of this
 * screen.
 *
 * Routing contract:
 *   • reachable at /welcome for anyone authed
 *   • ProjectsIndex redirects here when the account has never paired a device
 *     and has no projects
 */
import { onBeforeUnmount, onMounted, watch } from "vue";
import { useRouter } from "vue-router";

import SetupFlow from "@/components/onboarding/SetupFlow.vue";
import { useAuthStore } from "@/stores/auth";
import { useOnboardingStore } from "@/stores/onboarding";

const auth = useAuthStore();
const onboarding = useOnboardingStore();
const router = useRouter();

const ONBOARDING_FLAG = "vibecell_onboarding_done";

function markDone() {
  try {
    localStorage.setItem(ONBOARDING_FLAG, "1");
  } catch {
    /* private mode */
  }
}

function finish() {
  markDone();
  // Straight into the first project we just built, or the portfolio if
  // something went sideways.
  const first = onboarding.projects[0]?.slug;
  router.replace(first ? `/p/${first}` : "/p");
}

function skipAll() {
  markDone();
  router.replace("/p");
}

// The completion screen with triage is #8. Until it lands, `done` surfaces
// inline rather than auto-navigating — dropping the user somewhere the moment
// the last event arrives would rob them of the payoff they just watched.
watch(
  () => onboarding.done,
  (isDone) => {
    if (isDone) markDone();
  },
);

onMounted(() => {
  if (!auth.isAuthed) {
    router.replace({ path: "/login", query: { next: "/welcome" } });
    return;
  }
  onboarding.open();
  void onboarding.mintCode();
});

onBeforeUnmount(() => onboarding.close());
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] px-6 py-12">
    <div class="w-full max-w-[620px] mx-auto">
      <div class="flex items-center gap-2 mb-10 text-fg-subtle">
        <span class="text-signal-green font-mono text-section">◈</span>
        <span class="font-mono text-micro tracking-label uppercase">Vibecell · setup</span>
      </div>

      <SetupFlow variant="page" @finish="finish" />

      <div class="flex justify-end mt-4">
        <button
          type="button"
          class="text-small text-fg-subtle hover:text-fg-body transition-colors"
          @click="skipAll"
        >
          Skip setup →
        </button>
      </div>
    </div>
  </div>
</template>
