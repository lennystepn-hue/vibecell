<script setup lang="ts">
/**
 * The 2FA-prompt modal that fires for every admin write. Lives in
 * AdminLayout so it's always available regardless of which sub-page
 * triggers it. Reads from useAdminActions module-state — pages just
 * call open(...) with a config and the modal renders.
 *
 * The body slot is rendered by callers via a teleport — but for v1
 * we keep the action-specific copy inside the modal here, switching
 * on `state.kind`. Pages pass enough context via state.config.targetLabel
 * for the modal to render a sensible "Target: …" line.
 */
import MonoLabel from "@/components/ui/MonoLabel.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useAdminActions } from "@/composables/useAdminActions";

const { state, codeValid, close, run } = useAdminActions();

const TITLES: Record<string, string> = {
  "extend-trial": "Extend trial",
  "comp-days": "Comp days",
  "cancel-sub": "Cancel subscription",
  "mark-verified": "Mark email verified",
  "toggle-admin": "Toggle admin",
  "delete-user": "Delete account (GDPR)",
  "create-coupon": "Create coupon",
  "delete-coupon": "Delete coupon",
};

const CONFIRM_LABELS: Record<string, string> = {
  "delete-user": "Delete account",
  "delete-coupon": "Delete coupon",
  "cancel-sub": "Cancel sub",
};

const SUMMARIES: Record<string, string> = {
  "extend-trial": "Push trial_ends_at forward + reset email-stage so warning emails fire again. Syncs to Stripe.",
  "comp-days": "Comp the user N days of paid-equivalent service. Syncs to Stripe if linked.",
  "cancel-sub": "DB always updates; Stripe sync triggered if linked.",
  "mark-verified": "Stamps email_verified_at = now(). Use when magic-link bounced but the user is verified out-of-band.",
  "toggle-admin": "Flip users.is_admin. HANGAR_ADMIN_EMAILS env list is the OTHER required gate — both must agree.",
  "delete-user": "Irreversible. Deletes all user data per GDPR Art. 17. Stripe subscription canceled best-effort.",
  "create-coupon": "Create a new Stripe coupon. The code becomes the Stripe ID — case-sensitive, must be unique.",
  "delete-coupon": "Permanently delete this Stripe coupon. Existing subs that have it stay applied; only new applications are blocked.",
};
</script>

<template>
  <div
    v-if="state.kind"
    class="fixed inset-0 z-50 flex items-center justify-center px-4"
    style="background: rgba(7,11,16,0.7); backdrop-filter: blur(4px)"
    @click.self="close()"
  >
    <div class="glass rounded-xl w-full max-w-[460px] p-6 space-y-4" style="background: var(--bg-chrome)">
      <header class="flex items-center justify-between">
        <h2 class="text-section text-fg-primary font-semibold">
          {{ TITLES[state.kind] ?? state.kind }}
        </h2>
        <button type="button" class="text-fg-subtle hover:text-fg-body" @click="close()">✕</button>
      </header>

      <p
        v-if="state.config?.targetLabel"
        class="text-small text-fg-muted"
      >Target: <span class="font-mono text-fg-body">{{ state.config.targetLabel }}</span></p>

      <p class="text-small text-fg-muted leading-relaxed">{{ SUMMARIES[state.kind] }}</p>

      <!-- Body slot — pages can teleport in extra fields via the
           AdminActionExtras teleport target. The base modal already
           shows enough context for the action to be meaningful. -->
      <div id="admin-action-extras" />

      <!-- 2FA prompt — required for every admin write. -->
      <div class="space-y-2 pt-3 border-t border-border">
        <MonoLabel>2FA code (TOTP)</MonoLabel>
        <input
          v-model="state.code"
          type="text"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          placeholder="000000"
          class="h-10 w-32 px-3 rounded-md font-mono text-section tracking-[0.2em] text-center bg-bg-surface border border-border text-fg-primary"
          @keydown.enter="codeValid && run()"
        />
      </div>

      <p
        v-if="state.error"
        class="text-small p-3 rounded-md"
        :style="{ background: 'var(--signal-red-bg)', color: 'var(--signal-red)', border: '1px solid var(--signal-red)' }"
      >{{ state.error }}</p>

      <div class="flex items-center justify-end gap-3 pt-1">
        <button
          type="button"
          class="text-small text-fg-muted hover:text-fg-body transition-colors"
          :disabled="state.running"
          @click="close()"
        >cancel</button>
        <PrimaryButton :loading="state.running" :disabled="!codeValid || state.running" @click="run()">
          {{ CONFIRM_LABELS[state.kind] ?? "Confirm" }}
        </PrimaryButton>
      </div>
    </div>
  </div>
</template>
