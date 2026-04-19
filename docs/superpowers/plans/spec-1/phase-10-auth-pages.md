# Phase 10 — Auth Pages (`/login` + `/auth/verify`)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** A polished login page and a transparent verify-redirect page. First real Cockpit-themed UI — this sets the tone.

**Prerequisite:** Phase 9 complete (HEAD ≥ `ec8b256`). Design tokens, Pinia stores, Vue Router, API client all in place.

---

## Pages

- `/login` — email input + "Send magic link" button. Two states: (a) form, (b) sent-confirmation.
- `/auth/verify?token=X` — invisible redirect. Immediately navigates to `/api/v1/auth/verify?token=X` (server-side route) which sets the cookie and 303s to `/`.

---

## Files

```
frontend/src/
├── pages/
│   ├── Login.vue                   full replacement of placeholder
│   └── AuthVerify.vue              full replacement of placeholder
└── components/ui/
    ├── InputField.vue              labelled input with error slot
    └── PrimaryButton.vue           phosphor-green CTA
```

---

## Task 10.1 — Base input + button components

**File:** `frontend/src/components/ui/InputField.vue`

```vue
<script setup lang="ts">
interface Props {
  modelValue: string;
  label?: string;
  type?: string;
  placeholder?: string;
  autocomplete?: string;
  autofocus?: boolean;
  error?: string | null;
  disabled?: boolean;
  id?: string;
}

const props = withDefaults(defineProps<Props>(), {
  type: "text",
  autofocus: false,
  disabled: false,
});

defineEmits<{
  (e: "update:modelValue", value: string): void;
  (e: "keydown", ev: KeyboardEvent): void;
}>();

const id = props.id ?? `input-${Math.random().toString(36).slice(2, 8)}`;
</script>

<template>
  <div class="flex flex-col gap-1.5">
    <label
      v-if="label"
      :for="id"
      class="mono-label"
    >
      // {{ label }}
    </label>
    <input
      :id="id"
      :type="type"
      :value="modelValue"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :autofocus="autofocus"
      :disabled="disabled"
      :class="[
        'h-10 px-3 rounded-md font-sans text-body',
        'bg-bg-surface/60 border',
        error ? 'border-signal-red' : 'border-border',
        'text-fg-primary placeholder:text-fg-subtle',
        'transition-colors duration-fast ease-out',
        'hover:bg-bg-surface-hi disabled:opacity-50 disabled:cursor-not-allowed',
      ]"
      @input="$emit('update:modelValue', ($event.target as HTMLInputElement).value)"
      @keydown="$emit('keydown', $event)"
    />
    <p v-if="error" class="text-small text-signal-red">{{ error }}</p>
  </div>
</template>
```

**File:** `frontend/src/components/ui/PrimaryButton.vue`

```vue
<script setup lang="ts">
interface Props {
  type?: "button" | "submit";
  disabled?: boolean;
  loading?: boolean;
  size?: "md" | "lg";
}

withDefaults(defineProps<Props>(), {
  type: "button",
  disabled: false,
  loading: false,
  size: "md",
});
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[
      'inline-flex items-center justify-center gap-2',
      'font-sans font-semibold tracking-tight',
      'rounded-md px-4',
      size === 'lg' ? 'h-11 text-section' : 'h-10 text-body',
      'transition-all duration-fast ease-out',
      'disabled:opacity-50 disabled:cursor-not-allowed',
    ]"
    :style="{
      background: 'var(--signal-green)',
      color: 'var(--bg-body-to)',
      boxShadow: '0 0 0 1px var(--signal-green), 0 0 16px rgba(92, 200, 164, 0.18)',
    }"
  >
    <svg
      v-if="loading"
      class="animate-spin h-4 w-4"
      viewBox="0 0 24 24"
      fill="none"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.3" stroke-width="3" />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        stroke-width="3"
        stroke-linecap="round"
        fill="none"
      />
    </svg>
    <slot />
  </button>
</template>
```

Commit: `feat(frontend): InputField + PrimaryButton Cockpit primitives`

---

## Task 10.2 — Login page

**File:** `frontend/src/pages/Login.vue` (full replacement)

```vue
<script setup lang="ts">
import { ref } from "vue";

import InputField from "@/components/ui/InputField.vue";
import PrimaryButton from "@/components/ui/PrimaryButton.vue";
import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();

const email = ref("");
const submitting = ref(false);
const submitted = ref(false);
const error = ref<string | null>(null);

function isValidEmail(value: string): boolean {
  // Minimal syntactic check; server is authoritative.
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

async function onSubmit() {
  error.value = null;
  if (!isValidEmail(email.value)) {
    error.value = "That doesn't look like an email.";
    return;
  }
  submitting.value = true;
  try {
    const ok = await auth.requestMagicLink(email.value);
    if (ok) {
      submitted.value = true;
    } else {
      error.value = "Couldn't send the link. Try again in a minute.";
    }
  } finally {
    submitting.value = false;
  }
}

function reset() {
  submitted.value = false;
  email.value = "";
  error.value = null;
}
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] flex items-center justify-center px-6">
    <div class="w-full max-w-[380px]">
      <div class="flex items-center gap-2 mb-10 text-fg-subtle">
        <span class="text-signal-green font-mono text-section">◈</span>
        <span class="font-mono text-small tracking-[0.08em] uppercase">Hangar</span>
      </div>

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
          class="flex flex-col gap-6"
          @submit.prevent="onSubmit"
        >
          <div>
            <h1 class="text-display text-fg-primary mb-2">Sign in</h1>
            <p class="text-fg-muted text-body">
              We'll email you a one-time link. No passwords, nothing to forget.
            </p>
          </div>

          <InputField
            v-model="email"
            label="email"
            type="email"
            placeholder="you@example.com"
            autocomplete="email"
            :autofocus="true"
            :error="error"
            :disabled="submitting"
          />

          <PrimaryButton
            type="submit"
            size="lg"
            :loading="submitting"
            :disabled="submitting"
          >
            <span>Send magic link</span>
            <span
              v-if="!submitting"
              class="font-mono text-small opacity-70"
              aria-hidden="true"
            >⏎</span>
          </PrimaryButton>

          <p class="text-small text-fg-subtle text-center">
            By continuing, you agree to our terms — which don't exist yet.
          </p>
        </form>

        <div v-else key="sent" class="flex flex-col gap-5 text-center">
          <div
            class="mx-auto w-10 h-10 rounded-full flex items-center justify-center"
            :style="{ background: 'var(--signal-green-bg)', color: 'var(--signal-green)' }"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
              <path d="M22 6l-10 7L2 6" />
              <rect x="2" y="4" width="20" height="16" rx="2" />
            </svg>
          </div>
          <div>
            <h1 class="text-title text-fg-primary">Check your email</h1>
            <p class="text-fg-muted mt-2">
              We sent a link to <span class="font-mono text-fg-body">{{ email }}</span>.
              Click it from the same browser and you're in.
            </p>
          </div>
          <p class="text-small text-fg-subtle">
            The link expires in 15 minutes. Can only be used once.
          </p>
          <button
            type="button"
            class="text-small text-fg-muted hover:text-fg-body transition-colors"
            @click="reset"
          >
            ← use a different email
          </button>
        </div>
      </transition>
    </div>
  </div>
</template>
```

Commit: `feat(frontend): /login page with magic-link request + sent-confirmation state`

---

## Task 10.3 — Auth-verify redirect page

**File:** `frontend/src/pages/AuthVerify.vue` (full replacement)

```vue
<script setup lang="ts">
import { onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const router = useRouter();
const state = ref<"verifying" | "error">("verifying");

onMounted(() => {
  const token = route.query.token;
  if (typeof token !== "string" || !token) {
    state.value = "error";
    return;
  }
  // Hand off to the backend route which sets the cookie and 303s back to /.
  // Cross-origin fetch can't follow 303+Set-Cookie for session auth, so we
  // redirect the browser itself.
  window.location.replace(`/api/v1/auth/verify?token=${encodeURIComponent(token)}`);
});

function goLogin() {
  router.replace({ name: "login" });
}
</script>

<template>
  <div class="min-h-[calc(100vh-44px)] flex items-center justify-center px-6">
    <div v-if="state === 'verifying'" class="flex flex-col items-center gap-3 text-fg-muted">
      <svg
        class="animate-spin h-6 w-6 text-signal-green"
        viewBox="0 0 24 24"
        fill="none"
      >
        <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.3" stroke-width="2" />
        <path d="M12 2a10 10 0 0 1 10 10" stroke="currentColor" stroke-width="2" stroke-linecap="round" fill="none" />
      </svg>
      <p class="mono-label">// signing in</p>
    </div>
    <div v-else class="flex flex-col items-center gap-5 max-w-sm text-center">
      <h1 class="text-title text-fg-primary">Bad link</h1>
      <p class="text-fg-muted">
        The token is missing or malformed. It may have already been used — try requesting a new magic link.
      </p>
      <button
        type="button"
        class="text-body text-signal-blue link"
        @click="goLogin"
      >
        ← back to sign in
      </button>
    </div>
  </div>
</template>
```

Commit: `feat(frontend): /auth/verify redirect page (browser-level handoff to backend)`

---

## Task 10.4 — Auth smoke test (manual + vitest)

**File:** `frontend/src/pages/__tests__/Login.spec.ts`

```ts
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { mount } from "@vue/test-utils";
import { createRouter, createMemoryHistory } from "vue-router";

import Login from "../Login.vue";
import { useAuthStore } from "@/stores/auth";

describe("Login page", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
  });

  function makeRouter() {
    return createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: "/", name: "index", component: { template: "<div/>" } },
        { path: "/login", name: "login", component: Login },
      ],
    });
  }

  it("shows the email form initially", async () => {
    const router = makeRouter();
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(Login, { global: { plugins: [router] } });
    expect(wrapper.text()).toContain("Sign in");
    expect(wrapper.find("input[type=email]").exists()).toBe(true);
  });

  it("rejects malformed email client-side", async () => {
    const router = makeRouter();
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(Login, { global: { plugins: [router] } });
    const input = wrapper.find("input[type=email]");
    await input.setValue("not-an-email");
    await wrapper.find("form").trigger("submit.prevent");
    expect(wrapper.text()).toContain("doesn't look like an email");
  });

  it("shows the sent-confirmation after a successful request", async () => {
    const router = makeRouter();
    await router.push("/login");
    await router.isReady();
    const wrapper = mount(Login, { global: { plugins: [router] } });
    const auth = useAuthStore();
    vi.spyOn(auth, "requestMagicLink").mockResolvedValue(true);
    await wrapper.find("input[type=email]").setValue("user@example.com");
    await wrapper.find("form").trigger("submit.prevent");
    // Let the transition settle
    await new Promise((r) => setTimeout(r, 20));
    expect(wrapper.text()).toContain("Check your email");
    expect(wrapper.text()).toContain("user@example.com");
  });
});
```

Run:
```bash
cd frontend && pnpm test --run
```

Expected: 3 passed. (We use `--run` to avoid Vitest's watch mode.)

Commit: `test(frontend): Login page smoke tests (form state, validation, sent state)`

---

## Phase 10 complete when

- [ ] Both pages render Cockpit-themed (dark bg, Geist font, phosphor-green accent).
- [ ] Malformed email shows inline error immediately.
- [ ] Successful submit transitions to "Check your email" state.
- [ ] `/auth/verify?token=X` browser-redirects to backend route.
- [ ] `pnpm typecheck` + `pnpm build` + `pnpm test --run` all green.
- [ ] 4 commits on main (10.1–10.4).
