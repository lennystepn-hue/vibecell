<script setup lang="ts">
/**
 * "Connect an editor" — the same setup flow `/welcome` shows, in a dialog.
 *
 * This used to be 357 lines of its own: six editor tabs, per-editor copy
 * blocks, one-click deep links, manual instructions. All of it survived the
 * rewrite of `/welcome` in #7, because the two were separate copies of the
 * same job. The result was that a brand-new signup got one screen and one
 * line, while every existing account — the ones most likely to have an
 * unpaired editor lying around — still got the six tabs.
 *
 * Now both render `SetupFlow`. There is one setup flow, and it cannot drift
 * from itself.
 *
 * The stream and the pairing code are owned here rather than inside
 * `SetupFlow`, because a modal opens and closes: restarting the stream on
 * every reopen would drop frames from an install already in progress.
 */
import { onBeforeUnmount, watch } from "vue";

import SetupFlow from "@/components/onboarding/SetupFlow.vue";
import Modal from "@/components/ui/Modal.vue";
import { useConnectionsStore } from "@/stores/connections";
import { useOnboardingStore } from "@/stores/onboarding";

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ close: [] }>();

const onboarding = useOnboardingStore();
const connections = useConnectionsStore();

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      onboarding.open();
      void onboarding.mintCode();
    } else {
      onboarding.close();
    }
  },
  { immediate: true },
);

// A finished install means a new device exists; refresh so the list behind
// the dialog is not stale the moment it closes.
watch(
  () => onboarding.done,
  (isDone) => {
    if (isDone) void connections.refresh();
  },
);

onBeforeUnmount(() => onboarding.close());
</script>

<template>
  <Modal :open="props.open" title="Connect an editor" width="620px" @close="emit('close')">
    <SetupFlow variant="modal" @finish="emit('close')" />
  </Modal>
</template>
