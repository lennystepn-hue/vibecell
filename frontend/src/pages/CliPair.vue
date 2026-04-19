<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import TextField from "@/components/ui/TextField.vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";
import { useToastStore } from "@/stores/toast";

type DeviceOut = components["schemas"]["DeviceOut"];

const toast = useToastStore();

const rawCode = ref("");
const deviceName = ref(guessDeviceName());
const submitting = ref(false);
const submitted = ref(false);
const error = ref<string | null>(null);

const devices = ref<DeviceOut[]>([]);
const loadingDevices = ref(true);
const revoking = ref<string | null>(null);

function guessDeviceName(): string {
  const ua = (navigator.userAgent || "").toLowerCase();
  if (ua.includes("mac")) return "mac";
  if (ua.includes("windows")) return "windows";
  if (ua.includes("linux")) return "linux";
  return "CLI device";
}

// Auto-format: uppercase, strip non-alphanumeric, insert hyphen after 4 chars.
const formattedCode = computed(() => rawCode.value);

function onCodeInput(value: string) {
  const cleaned = value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8);
  if (cleaned.length > 4) {
    rawCode.value = `${cleaned.slice(0, 4)}-${cleaned.slice(4)}`;
  } else {
    rawCode.value = cleaned;
  }
}

const codeValid = computed(() => /^[A-Z0-9]{4}-[A-Z0-9]{4}$/.test(rawCode.value));

async function loadDevices() {
  loadingDevices.value = true;
  const { data, error: err } = await api.GET("/api/v1/cli/devices");
  loadingDevices.value = false;
  if (err) {
    toast.push("Couldn't load devices", "error");
    return;
  }
  devices.value = data ?? [];
}

async function connect() {
  error.value = null;
  if (!codeValid.value) {
    error.value = "Enter the 8-character code shown in your terminal (XXXX-XXXX).";
    return;
  }
  submitting.value = true;
  const { error: err } = await api.POST("/api/v1/cli/pair/confirm", {
    body: {
      user_code: rawCode.value,
      device_name: deviceName.value.trim() || null,
    },
  });
  submitting.value = false;
  if (err) {
    const detail =
      (err as { detail?: string; title?: string }).detail ||
      (err as { title?: string }).title ||
      "That code isn't valid or has expired.";
    error.value = detail;
    return;
  }
  submitted.value = true;
  toast.push("Device paired", "success");
  await loadDevices();
}

function reset() {
  submitted.value = false;
  rawCode.value = "";
  error.value = null;
}

async function revoke(id: string) {
  if (!confirm("Revoke this device? Its CLI/MCP client will stop working immediately.")) return;
  revoking.value = id;
  const { error: err } = await api.DELETE("/api/v1/cli/devices/{device_id}", {
    params: { path: { device_id: id } },
  });
  revoking.value = null;
  if (err) {
    toast.push("Couldn't revoke device", "error");
    return;
  }
  toast.push("Device revoked", "success");
  await loadDevices();
}

function fmtDate(iso: string | null): string {
  if (!iso) return "—";
  return new Date(iso).toISOString().slice(0, 16).replace("T", " ");
}

onMounted(loadDevices);
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] px-6 py-10">
    <div class="w-full max-w-[560px] mx-auto space-y-6">
      <div class="flex items-center gap-2 text-fg-subtle">
        <span class="text-signal-green font-mono text-section">◈</span>
        <span class="font-mono text-small tracking-[0.08em] uppercase">Hangar · CLI</span>
      </div>

      <section class="glass rounded-lg p-6">
        <transition
          enter-from-class="opacity-0 translate-y-1"
          enter-active-class="transition-all duration-med ease-out"
          enter-to-class="opacity-100 translate-y-0"
          leave-from-class="opacity-100"
          leave-active-class="transition-all duration-fast ease-in"
          leave-to-class="opacity-0"
          mode="out-in"
        >
          <form
            v-if="!submitted"
            key="form"
            class="flex flex-col gap-5"
            @submit.prevent="connect"
          >
            <div>
              <h1 class="text-title text-fg-primary tracking-tight">Pair a device</h1>
              <p class="text-fg-muted text-body mt-1">
                Enter the code shown in your terminal to connect a new CLI or MCP client
                to this workspace.
              </p>
            </div>

            <div class="flex flex-col gap-1.5">
              <label for="pair-code" class="mono-label">// code</label>
              <input
                id="pair-code"
                type="text"
                inputmode="text"
                autocomplete="one-time-code"
                spellcheck="false"
                :value="formattedCode"
                placeholder="XXXX-XXXX"
                maxlength="9"
                :disabled="submitting"
                autofocus
                :class="[
                  'h-12 px-3 rounded-md text-section font-mono tracking-[0.18em]',
                  'bg-bg-surface/60 border text-center uppercase',
                  error ? 'border-signal-red' : 'border-border',
                  'text-fg-primary placeholder:text-fg-subtle',
                  'transition-colors duration-fast ease-out hover:bg-bg-surface-hi disabled:opacity-50',
                ]"
                @input="onCodeInput(($event.target as HTMLInputElement).value)"
              />
              <p v-if="error" class="text-small text-signal-red">{{ error }}</p>
            </div>

            <TextField
              v-model="deviceName"
              label="device name"
              placeholder="mac / linux / windows"
              :disabled="submitting"
            />

            <PrimaryButton
              type="submit"
              size="lg"
              :disabled="!codeValid || submitting"
              :loading="submitting"
            >
              Connect device
            </PrimaryButton>
          </form>

          <div v-else key="success" class="flex flex-col gap-5 text-center">
            <div
              class="mx-auto w-10 h-10 rounded-full flex items-center justify-center"
              :style="{
                background: 'var(--signal-green-bg)',
                color: 'var(--signal-green)',
              }"
            >
              <svg
                width="18" height="18" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" stroke-width="2.5"
                stroke-linecap="round" stroke-linejoin="round"
              >
                <path d="M20 6L9 17l-5-5" />
              </svg>
            </div>
            <div>
              <h1 class="text-title text-fg-primary">Device paired</h1>
              <p class="text-fg-muted mt-2">
                You can close this tab and return to your terminal.
              </p>
            </div>
            <button
              type="button"
              class="text-small text-fg-muted hover:text-fg-body transition-colors"
              @click="reset"
            >
              ← pair another device
            </button>
          </div>
        </transition>
      </section>

      <section class="glass rounded-lg p-6">
        <header class="mb-5">
          <h2 class="text-section text-fg-primary tracking-tight">Connected devices</h2>
          <p class="text-small text-fg-muted mt-1">
            CLI and MCP clients that can act on this workspace.
          </p>
        </header>

        <div v-if="loadingDevices" class="mono-label opacity-50">loading…</div>

        <template v-else>
          <p v-if="devices.length === 0" class="text-fg-muted text-small">
            No devices paired yet.
          </p>

          <ul v-else class="divide-y divide-border/60">
            <li
              v-for="d in devices"
              :key="d.id"
              class="py-3 flex items-center gap-4"
            >
              <div class="flex-1 min-w-0">
                <div class="text-body text-fg-primary truncate">
                  {{ d.name || "unnamed device" }}
                </div>
                <div class="mono-label opacity-60 mt-0.5">
                  paired {{ fmtDate(d.paired_at) }} · last seen {{ fmtDate(d.last_seen_at) }}
                </div>
              </div>
              <button
                type="button"
                class="h-8 px-3 rounded-md text-small font-medium transition-colors"
                :style="{
                  background: 'var(--signal-red-bg)',
                  color: 'var(--signal-red)',
                  border: '1px solid var(--signal-red)',
                }"
                :disabled="revoking === d.id"
                @click="revoke(d.id)"
              >
                {{ revoking === d.id ? "revoking…" : "revoke" }}
              </button>
            </li>
          </ul>
        </template>
      </section>
    </div>
  </div>
</template>
