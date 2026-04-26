<script setup lang="ts">
import { computed, onMounted, ref } from "vue";

import SettingsNav from "@/components/settings/SettingsNav.vue";

import { useToastStore } from "@/stores/toast";

const toast = useToastStore();

interface SubscriptionResponse {
  status: string;
  plan_slug: string;
  plan_name: string;
  monthly_price_eur_cents: number;
  trial_ends_at: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
}

const sub = ref<SubscriptionResponse | null>(null);
const loadingSub = ref(false);
const checkingOut = ref(false);
const openingPortal = ref(false);
/** True when the API failed for any reason (no Stripe configured, no
 *  subscription row, network blip, etc). The UI falls back to the
 *  "Pro plan + start trial" pitch with the same Add-card CTA — better
 *  than rendering an apologetic empty state. */
const fellBack = ref(false);

async function loadSubscription() {
  loadingSub.value = true;
  try {
    const r = await fetch("/api/v1/me/subscription", { credentials: "include" });
    if (r.ok) {
      sub.value = await r.json();
    } else {
      fellBack.value = true;
    }
  } catch {
    fellBack.value = true;
  } finally {
    loadingSub.value = false;
  }
}

async function startCheckout() {
  checkingOut.value = true;
  try {
    const r = await fetch("/api/v1/billing/checkout", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ plan_id: "pro" }),
    });
    if (r.status === 503) {
      toast.push("Stripe is not configured on this deployment yet", "error");
      return;
    }
    if (!r.ok) {
      toast.push(`Couldn't start checkout (HTTP ${r.status})`, "error");
      return;
    }
    const { url } = await r.json();
    window.location.assign(url);
  } catch (e) {
    toast.push(`Network error: ${e instanceof Error ? e.message : String(e)}`, "error");
  } finally {
    checkingOut.value = false;
  }
}

async function openPortal() {
  openingPortal.value = true;
  try {
    const r = await fetch("/api/v1/billing/portal", {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ return_url: "/settings/billing" }),
    });
    if (!r.ok) {
      toast.push(`Couldn't open portal (HTTP ${r.status})`, "error");
      return;
    }
    const { url } = await r.json();
    window.location.assign(url);
  } finally {
    openingPortal.value = false;
  }
}

const trialDaysLeft = computed(() => {
  if (!sub.value?.trial_ends_at) return null;
  const ms = new Date(sub.value.trial_ends_at).getTime() - Date.now();
  if (ms <= 0) return 0;
  return Math.ceil(ms / (24 * 60 * 60 * 1000));
});

/** Fraction of trial used — between 0 (just started) and 1 (over). */
const trialProgress = computed(() => {
  if (!sub.value?.trial_ends_at) return 0;
  const TRIAL_DAYS = 7;
  const left = trialDaysLeft.value ?? 0;
  return Math.max(0, Math.min(1, (TRIAL_DAYS - left) / TRIAL_DAYS));
});

const formattedPrice = computed(() => {
  if (!sub.value) return "€8.99";
  return `€${(sub.value.monthly_price_eur_cents / 100).toFixed(2)}`;
});

const statusBadge = computed(() => {
  const s = sub.value?.status;
  if (fellBack.value || !s) {
    return { label: "Pro plan", color: "#5cc8a4", bg: "rgba(92,200,164,0.1)" };
  }
  switch (s) {
    case "trialing":
      return { label: "Trialing", color: "#5cc8a4", bg: "rgba(92,200,164,0.1)" };
    case "active":
      return { label: "Active", color: "#5cc8a4", bg: "rgba(92,200,164,0.1)" };
    case "past_due":
    case "unpaid":
      return { label: "Payment failed", color: "#ff7e6c", bg: "rgba(255,126,108,0.1)" };
    case "canceled":
      return { label: "Canceled", color: "#8ba1bd", bg: "rgba(138,180,255,0.08)" };
    default:
      return { label: s, color: "#8ba1bd", bg: "rgba(138,180,255,0.08)" };
  }
});

const features = [
  {
    icon: "∞",
    title: "Unlimited projects",
    body: "Track as many side-projects, side-side-projects and full apps as you want — no caps.",
  },
  {
    icon: "✦",
    title: "AI enrichment from GitHub",
    body: "Drop a repo URL → get pitch + stack + infra + tags + emoji auto-filled in seconds.",
  },
  {
    icon: "◇",
    title: "MCP server access",
    body: "Connect Claude Desktop, Claude Code, Cursor, Zed, Continue or any MCP-compatible client.",
  },
  {
    icon: "↺",
    title: "Cron jobs running for you",
    body: "Auto-screenshots, commit-sync from GitHub, env-drift detection — your dashboard stays in sync without lifting a finger.",
  },
  {
    icon: "○",
    title: "Workspace secrets vault",
    body: "Store API keys inline (AES-256-GCM) or as 1Password / Bitwarden references. Claude reads them silently when needed.",
  },
  {
    icon: "▤",
    title: "365-day session history",
    body: "Every Claude session, decision, ship and idea logged forever — searchable, filterable, exportable as JSON.",
  },
  {
    icon: "✉",
    title: "Magic-link + Passkey login",
    body: "No passwords. Touch ID, Face ID, security key — whatever your device offers.",
  },
  {
    icon: "🇪🇺",
    title: "EU VAT & GDPR ready",
    body: "Stripe Tax handles invoicing per country. Full data export + one-click account delete (Art. 17 + 20).",
  },
];

const showWillingCancel = computed(
  () => sub.value?.status === "active" && sub.value.cancel_at_period_end
);

const ctaPrimary = computed(() => {
  if (fellBack.value || !sub.value) return { label: "Start 7-day trial", action: startCheckout };
  switch (sub.value.status) {
    case "trialing":
      return {
        label: trialDaysLeft.value !== null && trialDaysLeft.value <= 0
          ? "Add payment method to continue"
          : "Add payment method",
        action: startCheckout,
      };
    case "past_due":
    case "unpaid":
      return { label: "Update payment method", action: startCheckout };
    case "canceled":
      return { label: "Re-subscribe", action: startCheckout };
    case "active":
      return { label: "Manage subscription", action: openPortal };
    default:
      return { label: "Open billing portal", action: openPortal };
  }
});

onMounted(loadSubscription);
</script>

<template>
  <div class="flex h-[calc(100vh-44px)]">
    <SettingsNav />
    <div class="flex-1 overflow-y-auto" style="background: var(--bg-canvas)">
      <div class="max-w-[860px] mx-auto px-8 py-8">
        <h1 class="text-display text-fg-primary tracking-tight mb-8">Billing</h1>

        <div v-if="loadingSub" class="text-fg-muted py-12 text-center font-mono text-small">
          Loading…
        </div>

        <template v-else>
          <!-- ─────────────────── Hero / current state ─────────────────── -->
          <div
            class="rounded-xl p-7 mb-6 relative overflow-hidden"
            style="
              background: linear-gradient(135deg, rgba(92,200,164,0.06) 0%, rgba(138,180,255,0.04) 100%);
              border: 1px solid rgba(92,200,164,0.18);
              box-shadow: 0 0 48px rgba(92,200,164,0.06), inset 0 1px 0 rgba(92,200,164,0.1);
            "
          >
            <div class="flex items-start justify-between mb-5 flex-wrap gap-3">
              <div>
                <div class="flex items-center gap-3 mb-2">
                  <span class="font-mono uppercase tracking-widest text-[11px]" style="color: #5cc8a4">
                    Vibecell Pro
                  </span>
                  <span
                    class="px-2 py-0.5 rounded font-mono text-[10px] uppercase tracking-wider font-semibold"
                    :style="{ background: statusBadge.bg, color: statusBadge.color }"
                  >{{ statusBadge.label }}</span>
                </div>
                <div class="flex items-baseline gap-2">
                  <span class="font-bold tracking-tight" style="font-size: 2.5rem; color: var(--fg-primary); line-height: 1">
                    {{ formattedPrice }}
                  </span>
                  <span class="font-mono text-small text-fg-muted">/ month</span>
                </div>
                <p class="text-small text-fg-muted mt-2 max-w-md">
                  One plan, one price. 7-day free trial — no credit card required to start.
                </p>
              </div>

              <button
                class="h-11 px-5 rounded-lg font-mono font-semibold text-[12px] transition-all hover:opacity-90"
                style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 20px rgba(92,200,164,0.25); white-space: nowrap"
                :disabled="checkingOut || openingPortal"
                @click="ctaPrimary.action"
              >
                {{ checkingOut || openingPortal ? "…" : ctaPrimary.label }} →
              </button>
            </div>

            <!-- Trial progress bar -->
            <div v-if="sub?.status === 'trialing' && trialDaysLeft !== null" class="mt-3">
              <div class="flex items-center justify-between mb-2 text-[11px] font-mono">
                <span style="color: #5cc8a4">
                  {{ trialDaysLeft === 0 ? "Trial ended" : `${trialDaysLeft} day${trialDaysLeft === 1 ? "" : "s"} left` }}
                </span>
                <span class="text-fg-subtle">7-day trial</span>
              </div>
              <div class="h-1.5 rounded-full overflow-hidden" style="background: rgba(138,180,255,0.1)">
                <div
                  class="h-full rounded-full transition-all"
                  :style="{
                    width: `${Math.round(trialProgress * 100)}%`,
                    background: trialDaysLeft <= 3 ? '#ffd66b' : '#5cc8a4',
                  }"
                />
              </div>
            </div>

            <p
              v-else-if="sub?.status === 'active' && sub.current_period_end"
              class="font-mono text-[11px] text-fg-subtle"
            >
              <span v-if="showWillingCancel" style="color: #ff7e6c">
                ⚠ Will not renew — access ends {{ new Date(sub.current_period_end).toLocaleDateString() }}
              </span>
              <span v-else>
                Renews {{ new Date(sub.current_period_end).toLocaleDateString() }}
              </span>
            </p>

            <p
              v-else-if="sub?.status === 'past_due' || sub?.status === 'unpaid'"
              class="font-mono text-[11px]" style="color: #ff7e6c"
            >
              Stripe couldn't process your last charge. Update your payment method to keep Pro access.
            </p>

            <p
              v-else-if="sub?.status === 'canceled'"
              class="font-mono text-[11px] text-fg-subtle"
            >
              Subscription canceled. Re-subscribe any time — your data is preserved.
            </p>
          </div>

          <!-- ─────────────────── What you get ─────────────────── -->
          <div class="mb-6">
            <h2 class="font-mono text-[11px] uppercase tracking-widest text-fg-muted mb-4">
              // what's included
            </h2>
            <div class="grid sm:grid-cols-2 gap-3">
              <div
                v-for="f in features"
                :key="f.title"
                class="rounded-lg p-4"
                style="background: var(--bg-surface); border: 1px solid var(--border)"
              >
                <div class="flex items-start gap-3">
                  <span
                    class="font-mono text-[18px] leading-none mt-0.5 select-none"
                    style="color: #5cc8a4; flex-shrink: 0; width: 22px"
                  >{{ f.icon }}</span>
                  <div>
                    <div class="font-semibold text-body text-fg-body mb-1">{{ f.title }}</div>
                    <p class="text-small text-fg-muted leading-snug">{{ f.body }}</p>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <!-- ─────────────────── Manage section (only for paying users) ─── -->
          <div
            v-if="sub?.status === 'active' || sub?.status === 'past_due' || sub?.status === 'canceled'"
            class="rounded-lg p-5 mb-6"
            style="background: var(--bg-surface); border: 1px solid var(--border)"
          >
            <div class="flex items-center justify-between gap-4 flex-wrap">
              <div>
                <div class="font-semibold text-body text-fg-body mb-1">Manage subscription</div>
                <p class="text-small text-fg-muted">
                  Update payment method, view invoices, or cancel — Stripe-hosted portal.
                </p>
              </div>
              <button
                class="h-10 px-4 rounded-md text-small transition-colors hover:bg-bg-surface-hi"
                style="border: 1px solid var(--border); color: var(--fg-body)"
                :disabled="openingPortal"
                @click="openPortal"
              >{{ openingPortal ? "Opening…" : "Open portal →" }}</button>
            </div>
          </div>

          <!-- ─────────────────── Footnote ─────────────────── -->
          <p class="text-[11px] font-mono text-fg-subtle leading-relaxed">
            // VAT applies based on your billing address (handled by Stripe Tax) ·
            cancel any time from the portal · keep access through the end of the
            current period after cancel · we never share or sell your data ·
            full export / delete from
            <router-link to="/settings" class="underline hover:text-fg-muted">/settings</router-link>
          </p>
        </template>
      </div>
    </div>
  </div>
</template>
