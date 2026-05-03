<script setup lang="ts">
/**
 * 2FA-prompt modal for every admin write action. Renders the right
 * input fields based on `state.kind` (days picker for trial extend,
 * full form for create-coupon, etc.) so pages don't need to teleport
 * extra inputs into a placeholder slot.
 *
 * Form values are bound to the composable's reactive state — the
 * request-body builder reads them at run-time. Pages prefill via
 * useAdminActions.open(config, prefill).
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
    <div
      class="glass rounded-xl w-full max-w-[460px] p-6 space-y-4 max-h-[90vh] overflow-y-auto"
      style="background: var(--bg-chrome)"
    >
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

      <!-- ── Action-specific form fields ───────────────────────── -->

      <!-- Extend trial -->
      <div v-if="state.kind === 'extend-trial'" class="space-y-2">
        <label class="block">
          <span class="mono-label">// days to add</span>
          <input
            v-model.number="state.extendTrial.days"
            type="number"
            min="1"
            max="180"
            class="mt-1 h-10 w-32 px-3 rounded-md font-mono text-section text-center bg-bg-surface border border-border text-fg-primary"
          />
        </label>
      </div>

      <!-- Comp days -->
      <div v-else-if="state.kind === 'comp-days'" class="space-y-3">
        <label class="block">
          <span class="mono-label">// days to comp</span>
          <input
            v-model.number="state.compDays.days"
            type="number"
            min="1"
            max="365"
            class="mt-1 h-10 w-32 px-3 rounded-md font-mono text-section text-center bg-bg-surface border border-border text-fg-primary"
          />
        </label>
        <label class="block">
          <span class="mono-label">// reason (audit log)</span>
          <input
            v-model="state.compDays.reason"
            type="text"
            maxlength="200"
            placeholder="support refund / launch promo / …"
            class="mt-1 h-10 w-full px-3 rounded-md font-sans bg-bg-surface border border-border text-fg-primary"
          />
        </label>
      </div>

      <!-- Cancel subscription -->
      <div v-else-if="state.kind === 'cancel-sub'" class="space-y-3">
        <label class="flex items-center gap-2 text-small text-fg-body">
          <input v-model="state.cancelSub.immediate" type="checkbox" class="accent-signal-red" />
          cancel immediately (default: cancel at period end)
        </label>
        <label class="block">
          <span class="mono-label">// reason</span>
          <input
            v-model="state.cancelSub.reason"
            type="text"
            maxlength="200"
            placeholder="user request / fraud / …"
            class="mt-1 h-10 w-full px-3 rounded-md font-sans bg-bg-surface border border-border text-fg-primary"
          />
        </label>
      </div>

      <!-- Toggle admin (read-only display of new value) -->
      <div v-else-if="state.kind === 'toggle-admin'" class="text-small text-fg-muted">
        Setting <code>users.is_admin = {{ state.toggleAdmin.is_admin ? "true" : "false" }}</code>.
      </div>

      <!-- Create coupon -->
      <div v-else-if="state.kind === 'create-coupon'" class="space-y-3">
        <label class="block">
          <span class="mono-label">// code (becomes the Stripe ID)</span>
          <input
            v-model="state.createCoupon.code"
            type="text"
            maxlength="40"
            placeholder="LAUNCH69"
            class="mt-1 h-10 w-full px-3 rounded-md font-mono uppercase bg-bg-surface border border-border text-fg-primary"
          />
        </label>
        <label class="block">
          <span class="mono-label">// display name (optional)</span>
          <input
            v-model="state.createCoupon.name"
            type="text"
            maxlength="40"
            placeholder="Vibecell Launch"
            class="mt-1 h-10 w-full px-3 rounded-md font-sans bg-bg-surface border border-border text-fg-primary"
          />
        </label>
        <div class="flex items-center gap-3">
          <label class="flex items-center gap-2 text-small text-fg-body">
            <input v-model="state.createCoupon.use_amount" type="checkbox" class="accent-signal-green" />
            fixed amount
          </label>
          <label v-if="!state.createCoupon.use_amount" class="flex-1 block">
            <span class="mono-label">// percent off</span>
            <input
              v-model.number="state.createCoupon.percent_off"
              type="number" min="1" max="100"
              class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
            />
          </label>
          <label v-else class="flex-1 block">
            <span class="mono-label">// cents (eur)</span>
            <input
              v-model.number="state.createCoupon.amount_off_cents"
              type="number" min="50" max="100000"
              class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
            />
          </label>
        </div>
        <label class="block">
          <span class="mono-label">// duration</span>
          <select
            v-model="state.createCoupon.duration"
            class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
          >
            <option value="once">once</option>
            <option value="repeating">repeating</option>
            <option value="forever">forever</option>
          </select>
        </label>
        <label v-if="state.createCoupon.duration === 'repeating'" class="block">
          <span class="mono-label">// duration in months</span>
          <input
            v-model.number="state.createCoupon.duration_in_months"
            type="number" min="1" max="24"
            class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
          />
        </label>
        <label class="block">
          <span class="mono-label">// max redemptions (0 = unlimited)</span>
          <input
            v-model.number="state.createCoupon.max_redemptions"
            type="number" min="0" max="10000"
            class="mt-1 h-10 w-full px-3 rounded-md font-mono bg-bg-surface border border-border text-fg-primary"
          />
        </label>
      </div>

      <!-- ── 2FA prompt (always visible) ──────────────────────── -->
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
