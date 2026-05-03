<script setup lang="ts">
/**
 * 2FA / TOTP setup + management card.
 *
 * Three states (server-driven via /api/v1/2fa/status):
 *   • disabled  — show "Set up 2FA" button. Click triggers /setup which
 *     persists an unconfirmed secret and returns a QR + the raw secret
 *     for manual entry. Then we collect a 6-digit code and call /verify.
 *   • pending   — secret was provisioned but the user never confirmed
 *     a code (closed the page mid-setup). Same path as disabled — they
 *     hit "Set up" again, server overwrites with a fresh secret.
 *   • enabled   — show "Disable 2FA" with a code prompt. Disabling
 *     requires a fresh code so a stolen session can't strip 2FA.
 *
 * Designed for the cockpit aesthetic — mono labels, single accent
 * (green when enabled, amber while pending). No marketing copy.
 */
import { computed, onMounted, ref } from "vue";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useToastStore } from "@/stores/toast";

const toast = useToastStore();

interface StatusResponse {
  enabled: boolean;
  enabled_at: string | null;
}
interface SetupResponse {
  secret: string;
  qr_data_uri: string;
  otpauth: string;
}

const statusLoading = ref(true);
const enabled = ref(false);
const enabledAt = ref<string | null>(null);

// While in setup mode, we hold the QR + raw secret so the user can scan
// or paste into their authenticator. Cleared on verify success / cancel.
const setupData = ref<SetupResponse | null>(null);
const code = ref("");
const verifying = ref(false);
const setupErr = ref<string | null>(null);

// Disable flow
const showDisable = ref(false);
const disableCode = ref("");
const disabling = ref(false);

async function loadStatus() {
  statusLoading.value = true;
  try {
    const res = await fetch("/api/v1/2fa/status", { credentials: "include" });
    if (res.ok) {
      const data = (await res.json()) as StatusResponse;
      enabled.value = data.enabled;
      enabledAt.value = data.enabled_at;
    }
  } catch {
    /* silent */
  } finally {
    statusLoading.value = false;
  }
}

onMounted(loadStatus);

async function startSetup() {
  setupErr.value = null;
  code.value = "";
  try {
    const res = await fetch("/api/v1/2fa/setup", {
      method: "POST",
      credentials: "include",
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    setupData.value = (await res.json()) as SetupResponse;
  } catch (e) {
    setupErr.value = e instanceof Error ? e.message : "Couldn't start 2FA setup";
  }
}

async function verifyCode() {
  if (!setupData.value || code.value.length < 6) return;
  verifying.value = true;
  setupErr.value = null;
  try {
    const res = await fetch("/api/v1/2fa/verify", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: code.value }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      throw new Error(body.detail || "Invalid code");
    }
    toast.push("2FA enabled — write your secret somewhere safe!", "success");
    setupData.value = null;
    code.value = "";
    await loadStatus();
  } catch (e) {
    setupErr.value = e instanceof Error ? e.message : "Verification failed";
  } finally {
    verifying.value = false;
  }
}

function cancelSetup() {
  setupData.value = null;
  code.value = "";
  setupErr.value = null;
}

async function disable2fa() {
  if (disableCode.value.length < 6) return;
  disabling.value = true;
  try {
    const res = await fetch("/api/v1/2fa/disable", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: disableCode.value }),
    });
    if (!res.ok) {
      const body = (await res.json().catch(() => ({}))) as { detail?: string };
      throw new Error(body.detail || "Couldn't disable 2FA");
    }
    toast.push("2FA disabled", "success");
    showDisable.value = false;
    disableCode.value = "";
    await loadStatus();
  } catch (e) {
    toast.push(e instanceof Error ? e.message : "Couldn't disable 2FA", "error");
  } finally {
    disabling.value = false;
  }
}

const codeValid = computed(() => /^\d{6}$/.test(code.value));
const disableValid = computed(() => /^\d{6}$/.test(disableCode.value));
</script>

<template>
  <div>
    <!-- ── ENABLED STATE ───────────────────────────────────────────── -->
    <div v-if="enabled && !showDisable" class="space-y-3">
      <div class="flex items-center gap-3">
        <span
          class="font-mono text-section leading-none"
          aria-hidden="true"
          :style="{ color: 'var(--signal-green)' }"
        >●</span>
        <div>
          <p class="text-body text-fg-primary font-medium">2FA enabled</p>
          <p
            v-if="enabledAt"
            class="text-small text-fg-muted mt-0.5 font-mono"
          >since {{ new Date(enabledAt).toLocaleDateString() }}</p>
        </div>
      </div>
      <p class="text-small text-fg-muted max-w-prose">
        Every admin write action requires a fresh 6-digit code from your
        authenticator app — even with a stolen session cookie, an attacker
        couldn't issue coupons, extend trials, or modify subscriptions.
      </p>
      <button
        type="button"
        class="text-small text-fg-subtle hover:text-signal-red transition-colors"
        @click="showDisable = true"
      >Disable 2FA</button>
    </div>

    <!-- ── DISABLE FLOW ────────────────────────────────────────────── -->
    <div v-else-if="showDisable" class="space-y-4">
      <p class="text-small text-fg-muted">
        Enter a current code to disable 2FA. Your authenticator entry can
        be deleted afterwards.
      </p>
      <input
        v-model="disableCode"
        type="text"
        inputmode="numeric"
        autocomplete="one-time-code"
        maxlength="6"
        placeholder="000000"
        class="h-10 w-32 px-3 rounded-md font-mono text-section tracking-[0.2em] text-center bg-bg-surface border border-border text-fg-primary"
      />
      <div class="flex items-center gap-3">
        <button
          type="button"
          class="text-small text-fg-muted hover:text-fg-body transition-colors"
          :disabled="disabling"
          @click="showDisable = false; disableCode = ''"
        >cancel</button>
        <button
          type="button"
          class="px-4 py-2 rounded-md text-small font-mono transition-opacity hover:opacity-90 disabled:opacity-50"
          :style="{ background: 'var(--signal-red)', color: 'var(--bg-body-to)' }"
          :disabled="!disableValid || disabling"
          @click="disable2fa"
        >{{ disabling ? "disabling…" : "Disable 2FA" }}</button>
      </div>
    </div>

    <!-- ── SETUP IN PROGRESS ───────────────────────────────────────── -->
    <div v-else-if="setupData" class="space-y-4">
      <div class="flex flex-col sm:flex-row gap-5 items-start">
        <img
          :src="setupData.qr_data_uri"
          alt="Scan with your authenticator app"
          class="w-44 h-44 shrink-0 rounded-md bg-white p-2"
          style="image-rendering: pixelated"
        />
        <div class="space-y-3 flex-1 min-w-0">
          <p class="text-small text-fg-muted leading-relaxed">
            Scan this QR with Google Authenticator, 1Password, Authy,
            Bitwarden — anything that speaks TOTP. Or paste the secret
            below into the app manually.
          </p>
          <div class="flex items-center gap-2 p-2 rounded-md font-mono text-small select-all"
               style="background: rgba(20,33,50,0.5); border: 1px solid var(--border)">
            <code class="flex-1 break-all text-fg-body">{{ setupData.secret }}</code>
          </div>
          <p class="text-[11px] text-fg-subtle font-mono">
            // write the secret somewhere safe — losing your authenticator means re-setup
          </p>
        </div>
      </div>

      <div class="space-y-2 pt-2 border-t border-border">
        <label class="mono-label">// confirm with a code</label>
        <input
          v-model="code"
          type="text"
          inputmode="numeric"
          autocomplete="one-time-code"
          maxlength="6"
          placeholder="000000"
          class="h-10 w-32 px-3 rounded-md font-mono text-section tracking-[0.2em] text-center bg-bg-surface border border-border text-fg-primary"
          @keydown.enter="codeValid && verifyCode()"
        />
      </div>

      <p
        v-if="setupErr"
        class="text-small p-3 rounded-md"
        :style="{ background: 'var(--signal-red-bg)', color: 'var(--signal-red)', border: '1px solid var(--signal-red)' }"
      >{{ setupErr }}</p>

      <div class="flex items-center gap-3">
        <button
          type="button"
          class="text-small text-fg-muted hover:text-fg-body transition-colors"
          :disabled="verifying"
          @click="cancelSetup"
        >cancel</button>
        <PrimaryButton :loading="verifying" :disabled="!codeValid || verifying" @click="verifyCode">
          Verify and enable
        </PrimaryButton>
      </div>
    </div>

    <!-- ── DISABLED + LOADING ──────────────────────────────────────── -->
    <div v-else-if="statusLoading" class="text-small text-fg-subtle font-mono">
      loading…
    </div>
    <div v-else class="space-y-3">
      <div class="flex items-center gap-3">
        <span class="font-mono text-section leading-none text-fg-subtle" aria-hidden="true">○</span>
        <div>
          <p class="text-body text-fg-primary font-medium">2FA not enabled</p>
          <p class="text-small text-fg-muted mt-0.5">
            Required for admin actions. Highly recommended for everyone.
          </p>
        </div>
      </div>
      <PrimaryButton @click="startSetup">Set up 2FA</PrimaryButton>
    </div>
  </div>
</template>
