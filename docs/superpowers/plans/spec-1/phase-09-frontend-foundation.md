# Phase 9 — Frontend Foundation (Cockpit tokens + SPA shell)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development.

**Goal:** Vue-3 SPA with full Cockpit design system wired: phosphor-green palette, glass surfaces, Geist typography, Tailwind + CSS custom properties, Pinia stores, Vue Router, typed API client generated from the staging backend's OpenAPI, all layout primitives needed by Phase 10-15.

**Prerequisite:** Phase 8 complete (HEAD ≥ `e343760`). Backend 112 tests green on staging.

**Craft goal:** this is the base layer for "richtig krass" — every token, every font weight, every transition duration matches the spec exactly. We make it impossible to ship ugly.

---

## File structure

```
frontend/
├── package.json                       (modify) add deps
├── tailwind.config.ts                 (new) extends with Cockpit tokens
├── postcss.config.js                  (new)
├── src/
│   ├── main.ts                        (modify) wire Pinia + Router + global CSS
│   ├── App.vue                        (modify) shell with RouterView
│   ├── assets/
│   │   ├── tokens.css                 Cockpit design tokens (CSS custom properties)
│   │   ├── base.css                   @tailwind directives + resets + body styles
│   │   └── fonts.css                  Geist + Geist Mono via @font-face or npm pkg
│   ├── router/
│   │   └── index.ts                   routes with lazy-loaded pages
│   ├── stores/
│   │   ├── auth.ts                    useAuthStore (user, workspaces, active)
│   │   ├── toast.ts                   useToastStore
│   │   ├── projects.ts                useProjectsStore (list + active + CRUD calls)
│   │   └── command-palette.ts         useCommandPaletteStore
│   ├── api/
│   │   ├── types.gen.ts               auto-generated from staging OpenAPI
│   │   ├── client.ts                  typed fetch wrapper (Result pattern)
│   │   └── index.ts                   re-exports
│   ├── components/
│   │   ├── app/
│   │   │   ├── TopBar.vue             glass top bar with workspace/slug path + Cmd+K hint
│   │   │   └── AppLayout.vue          three-pane shell (sidebar + main + rail)
│   │   └── ui/
│   │       ├── StatusPill.vue         status → pill with signal-dot
│   │       ├── MonoLabel.vue          // UPPERCASE cockpit label
│   │       ├── SignalDot.vue          colored dot with glow
│   │       ├── KbdHint.vue            <kbd> shortcut pill
│   │       ├── DataRow.vue            label/value two-column row
│   │       └── EmptyState.vue         centered prompt with CTAs
│   ├── pages/
│   │   ├── IndexRedirect.vue          / → /p or /login based on auth
│   │   └── NotFound.vue               404
│   └── composables/
│       └── useShortcut.ts             global keyboard shortcut registration
├── index.html                         (modify) preload fonts + dark base bg
└── .eslintrc.cjs                      (new) Vue + TS strict lint
```

---

## Task 9.1 — Install frontend dependencies

**File:** `frontend/package.json` (modify)

Replace the `dependencies` / `devDependencies` blocks with:

```json
{
  "name": "hangar-frontend",
  "version": "0.1.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vue-tsc -b && vite build",
    "preview": "vite preview",
    "test": "vitest",
    "typecheck": "vue-tsc --noEmit",
    "lint": "eslint . --ext .ts,.vue --max-warnings 0",
    "gen:api": "openapi-typescript http://89.167.111.89:8000/api/v1/openapi.json -o src/api/types.gen.ts"
  },
  "dependencies": {
    "vue": "^3.5.13",
    "vue-router": "^4.5.0",
    "pinia": "^2.3.0",
    "openapi-fetch": "^0.13.0",
    "geist": "^1.3.1",
    "lucide-vue-next": "^0.468.0",
    "@vueuse/core": "^11.3.0"
  },
  "devDependencies": {
    "@types/node": "^22.10.0",
    "@vitejs/plugin-vue": "^5.2.1",
    "@vue/tsconfig": "^0.7.0",
    "autoprefixer": "^10.4.20",
    "eslint": "^9.16.0",
    "eslint-plugin-vue": "^9.32.0",
    "jsdom": "^25.0.1",
    "msw": "^2.6.8",
    "openapi-typescript": "^7.4.4",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.16",
    "typescript": "~5.7.2",
    "vite": "^6.0.0",
    "vitest": "^2.1.6",
    "vue-tsc": "^2.1.10"
  }
}
```

Run `cd frontend && pnpm install`. Expected success.

Commit: `chore(frontend): install Cockpit deps (tailwind, geist, lucide, pinia, openapi-fetch)`

---

## Task 9.2 — Tailwind + PostCSS + base CSS

**File:** `frontend/postcss.config.js`

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

**File:** `frontend/tailwind.config.ts`

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{vue,ts}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Map Tailwind names onto Cockpit CSS custom properties. This lets us
        // write `bg-surface` while keeping tokens.css as the single source of truth.
        bg: {
          body: "var(--bg-body)",
          surface: "var(--bg-surface)",
          "surface-hi": "var(--bg-surface-hi)",
          overlay: "var(--bg-overlay)",
          chrome: "var(--bg-chrome)",
        },
        fg: {
          primary: "var(--fg-primary)",
          body: "var(--fg-body)",
          muted: "var(--fg-muted)",
          subtle: "var(--fg-subtle)",
          disabled: "var(--fg-disabled)",
        },
        signal: {
          green: "var(--signal-green)",
          amber: "var(--signal-amber)",
          red: "var(--signal-red)",
          blue: "var(--signal-blue)",
        },
        border: {
          subtle: "var(--border-subtle)",
          DEFAULT: "var(--border-default)",
          strong: "var(--border-strong)",
        },
      },
      fontFamily: {
        sans: ["Geist", "-apple-system", "BlinkMacSystemFont", "Segoe UI", "sans-serif"],
        mono: ["Geist Mono", "ui-monospace", "SFMono-Regular", "Menlo", "monospace"],
      },
      fontSize: {
        display: ["28px", { lineHeight: "1.1", letterSpacing: "-0.03em", fontWeight: "600" }],
        title: ["20px", { lineHeight: "1.2", letterSpacing: "-0.02em", fontWeight: "600" }],
        section: ["14px", { lineHeight: "1.4", letterSpacing: "-0.01em", fontWeight: "600" }],
        body: ["13px", { lineHeight: "1.5" }],
        small: ["12px", { lineHeight: "1.4" }],
        micro: ["11px", { lineHeight: "1.3", letterSpacing: "0.08em", fontWeight: "500" }],
        code: ["12px", { lineHeight: "1.5" }],
      },
      spacing: {
        "space-1": "4px",
        "space-2": "8px",
        "space-3": "12px",
        "space-4": "16px",
        "space-5": "24px",
        "space-6": "32px",
        "space-7": "48px",
        "space-8": "64px",
      },
      borderRadius: {
        sm: "3px",
        md: "6px",
        lg: "8px",
        xl: "12px",
      },
      transitionTimingFunction: {
        out: "cubic-bezier(0.22, 1, 0.36, 1)",
        in: "cubic-bezier(0.64, 0, 0.78, 0)",
      },
      transitionDuration: {
        fast: "120ms",
        med: "200ms",
        slow: "300ms",
      },
      backdropBlur: {
        glass: "10px",
      },
      boxShadow: {
        card: "0 0 0 1px var(--border-default)",
        "card-hi": "0 0 0 1px var(--border-strong), 0 4px 20px rgba(0,0,0,0.3)",
        modal: "0 24px 48px rgba(0,0,0,0.6), 0 0 0 1px var(--border-default)",
      },
    },
  },
  plugins: [],
} satisfies Config;
```

**File:** `frontend/src/assets/tokens.css`

```css
:root {
  /* base */
  --bg-body-from: #142132;
  --bg-body-to: #070b10;
  --bg-body: radial-gradient(ellipse at 20% -10%, var(--bg-body-from) 0%, var(--bg-body-to) 55%);
  --bg-surface: rgba(20, 33, 50, 0.45);
  --bg-surface-hi: rgba(20, 33, 50, 0.65);
  --bg-overlay: rgba(7, 11, 16, 0.8);
  --bg-chrome: rgba(13, 18, 26, 0.7);

  /* foreground */
  --fg-primary: #ffffff;
  --fg-body: #cfd4dc;
  --fg-muted: #8ba1bd;
  --fg-subtle: #5e7088;
  --fg-disabled: #3d4a5c;

  /* signal */
  --signal-green: #5cc8a4;
  --signal-green-bg: rgba(92, 200, 164, 0.12);
  --signal-amber: #f5b84a;
  --signal-amber-bg: rgba(245, 184, 74, 0.12);
  --signal-red: #ff5b5b;
  --signal-red-bg: rgba(255, 91, 91, 0.12);
  --signal-blue: #8ab4ff;
  --signal-blue-bg: rgba(138, 180, 255, 0.08);

  /* borders */
  --border-subtle: rgba(138, 180, 255, 0.08);
  --border-default: rgba(138, 180, 255, 0.12);
  --border-strong: rgba(138, 180, 255, 0.18);

  /* depth */
  --glow-signal: 0 0 6px currentColor;

  /* motion */
  --ease-out: cubic-bezier(0.22, 1, 0.36, 1);
  --ease-in: cubic-bezier(0.64, 0, 0.78, 0);
  --dur-fast: 120ms;
  --dur-med: 200ms;
  --dur-slow: 300ms;
}

@media (prefers-reduced-motion: reduce) {
  :root {
    --dur-fast: 0ms;
    --dur-med: 0ms;
    --dur-slow: 0ms;
  }
}
```

**File:** `frontend/src/assets/fonts.css`

```css
/* Geist fonts ship via the `geist` npm package. Import its CSS directly. */
@import "geist/font.css";
@import "geist/font-mono.css";
```

**File:** `frontend/src/assets/base.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@import "./tokens.css";
@import "./fonts.css";

@layer base {
  html {
    color-scheme: dark;
  }

  body {
    font-family: "Geist", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    font-size: 13px;
    line-height: 1.5;
    color: var(--fg-body);
    background: var(--bg-body-to);
    background-image: var(--bg-body);
    background-attachment: fixed;
    min-height: 100vh;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
    font-variant-numeric: tabular-nums;
  }

  /* Tabular numerals on any monospace inputs and data displays. */
  .mono, code, kbd, pre, [class*="font-mono"] {
    font-family: "Geist Mono", ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-variant-numeric: tabular-nums;
  }

  /* Default focus ring — phosphor-green. Never outline:none without replacement. */
  :focus-visible {
    outline: 2px solid var(--signal-green);
    outline-offset: 2px;
    border-radius: 3px;
  }

  /* Links default to no underline; dashed bottom-border that firms up on hover. */
  a.link {
    color: var(--signal-blue);
    border-bottom: 1px dashed var(--signal-blue-bg);
    transition: color var(--dur-fast) var(--ease-out), border-color var(--dur-fast) var(--ease-out);
  }

  a.link:hover {
    color: var(--signal-blue);
    border-bottom-color: var(--signal-blue);
  }

  /* Scrollbars subtle. */
  ::-webkit-scrollbar {
    width: 10px;
    height: 10px;
  }
  ::-webkit-scrollbar-thumb {
    background: var(--border-default);
    border-radius: 8px;
  }
  ::-webkit-scrollbar-thumb:hover {
    background: var(--border-strong);
  }
  ::-webkit-scrollbar-track {
    background: transparent;
  }
}

@layer components {
  .glass {
    background: var(--bg-surface);
    backdrop-filter: blur(10px) saturate(1.2);
    -webkit-backdrop-filter: blur(10px) saturate(1.2);
    border: 1px solid var(--border-default);
  }

  .glass-hi {
    background: var(--bg-surface-hi);
    backdrop-filter: blur(10px) saturate(1.2);
    -webkit-backdrop-filter: blur(10px) saturate(1.2);
    border: 1px solid var(--border-strong);
  }

  .chrome {
    background: var(--bg-chrome);
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    border-color: var(--border-subtle);
  }

  /* Cockpit signature: uppercase mono-label above cards. */
  .mono-label {
    font-family: "Geist Mono", ui-monospace, monospace;
    font-size: 11px;
    font-weight: 500;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: var(--fg-muted);
  }
}
```

**File:** `frontend/index.html` (modify — preload bg + lang)

```html
<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="theme-color" content="#070b10" />
    <title>Hangar</title>
    <style>
      html, body { background: #070b10; margin: 0; }
    </style>
  </head>
  <body>
    <div id="app"></div>
    <script type="module" src="/src/main.ts"></script>
  </body>
</html>
```

Run:
```bash
cd frontend && pnpm build
```

Expected: success, `dist/` produced. Body has dark bg immediately (no FOUC).

Commit: `feat(frontend): Cockpit design tokens + Tailwind config + base.css with glass/mono-label utilities`

---

## Task 9.3 — Pinia setup + 4 stores

**File:** `frontend/src/stores/toast.ts`

```ts
import { defineStore } from "pinia";
import { ref } from "vue";

export type ToastKind = "info" | "success" | "warning" | "error";

export interface Toast {
  id: string;
  kind: ToastKind;
  message: string;
  expiresAt: number;
}

export const useToastStore = defineStore("toast", () => {
  const items = ref<Toast[]>([]);

  function push(message: string, kind: ToastKind = "info", ttlMs = 4000) {
    const id = crypto.randomUUID();
    const expiresAt = Date.now() + ttlMs;
    items.value = [...items.value, { id, kind, message, expiresAt }];
    setTimeout(() => dismiss(id), ttlMs);
  }

  function dismiss(id: string) {
    items.value = items.value.filter((t) => t.id !== id);
  }

  function clear() {
    items.value = [];
  }

  return { items, push, dismiss, clear };
});
```

**File:** `frontend/src/stores/auth.ts`

```ts
import { defineStore } from "pinia";
import { computed, ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type User = components["schemas"]["UserOut"];
type Workspace = components["schemas"]["WorkspaceOut"];
type WorkspaceListItem = components["schemas"]["WorkspaceListItem"];

export const useAuthStore = defineStore("auth", () => {
  const user = ref<User | null>(null);
  const activeWorkspace = ref<Workspace | null>(null);
  const workspaces = ref<WorkspaceListItem[]>([]);
  const loading = ref(false);

  const isAuthed = computed(() => user.value !== null);

  async function refresh(): Promise<void> {
    loading.value = true;
    try {
      const { data, error } = await api.GET("/api/v1/me");
      if (error || !data) {
        user.value = null;
        activeWorkspace.value = null;
        workspaces.value = [];
        return;
      }
      user.value = data.user;
      activeWorkspace.value = data.active_workspace;
      workspaces.value = data.workspaces;
    } finally {
      loading.value = false;
    }
  }

  async function requestMagicLink(email: string): Promise<boolean> {
    const { error } = await api.POST("/api/v1/auth/magic-link", {
      body: { email },
    });
    return !error;
  }

  async function logout(): Promise<void> {
    await api.POST("/api/v1/auth/logout", {});
    user.value = null;
    activeWorkspace.value = null;
    workspaces.value = [];
  }

  return {
    user,
    activeWorkspace,
    workspaces,
    isAuthed,
    loading,
    refresh,
    requestMagicLink,
    logout,
  };
});
```

**File:** `frontend/src/stores/projects.ts`

```ts
import { defineStore } from "pinia";
import { ref } from "vue";

import { api } from "@/api/client";
import type { components } from "@/api/types.gen";

type ProjectListItem = components["schemas"]["ProjectListItem"];
type ProjectFullOut = components["schemas"]["ProjectFullOut"];

export const useProjectsStore = defineStore("projects", () => {
  const list = ref<ProjectListItem[]>([]);
  const active = ref<ProjectFullOut | null>(null);
  const loadingList = ref(false);
  const loadingActive = ref(false);

  async function fetchList(): Promise<void> {
    loadingList.value = true;
    try {
      const { data } = await api.GET("/api/v1/projects", {
        params: { query: { limit: 200 } },
      });
      list.value = data?.items ?? [];
    } finally {
      loadingList.value = false;
    }
  }

  async function fetchProject(slug: string): Promise<void> {
    loadingActive.value = true;
    try {
      const { data } = await api.GET("/api/v1/projects/{slug}", {
        params: { path: { slug } },
      });
      active.value = data ?? null;
    } finally {
      loadingActive.value = false;
    }
  }

  async function switchTo(slug: string): Promise<boolean> {
    const { error } = await api.POST("/api/v1/projects/{slug}/switch", {
      params: { path: { slug } },
    });
    if (!error) {
      await fetchProject(slug);
    }
    return !error;
  }

  return {
    list,
    active,
    loadingList,
    loadingActive,
    fetchList,
    fetchProject,
    switchTo,
  };
});
```

**File:** `frontend/src/stores/command-palette.ts`

```ts
import { defineStore } from "pinia";
import { computed, ref } from "vue";

export const useCommandPaletteStore = defineStore("commandPalette", () => {
  const open = ref(false);
  const query = ref("");
  const selectedIndex = ref(0);

  function toggle(): void {
    open.value = !open.value;
    if (!open.value) {
      query.value = "";
      selectedIndex.value = 0;
    }
  }

  function show(): void {
    open.value = true;
    query.value = "";
    selectedIndex.value = 0;
  }

  function hide(): void {
    open.value = false;
    query.value = "";
    selectedIndex.value = 0;
  }

  const hasQuery = computed(() => query.value.trim().length > 0);

  return { open, query, selectedIndex, hasQuery, toggle, show, hide };
});
```

Commit: `feat(frontend): Pinia stores (auth, toast, projects, command-palette) with typed API integration`

---

## Task 9.4 — Typed API client (generated from staging)

**File:** `frontend/src/api/client.ts`

```ts
import createClient from "openapi-fetch";

import type { paths } from "./types.gen";

export const api = createClient<paths>({
  baseUrl: "",
  credentials: "include",
  headers: {
    "Content-Type": "application/json",
  },
});
```

**File:** `frontend/src/api/index.ts`

```ts
export { api } from "./client";
export type { components, paths } from "./types.gen";
```

Generate types from the running staging backend. The backend must be running — use uvicorn on staging:

```bash
# Start backend briefly so openapi-typescript can pull the schema
ssh root@89.167.111.89 'cd /srv/hangar/backend && export HANGAR_DATABASE_URL="postgresql+asyncpg://hangar:hangar_dev@localhost:5432/hangar_dev" HANGAR_REDIS_URL="redis://localhost:6379/0" HANGAR_MASTER_KEY="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" HANGAR_RESEND_API_KEY="test" HANGAR_GITHUB_CLIENT_ID="test" HANGAR_GITHUB_CLIENT_SECRET="test" HANGAR_BASE_URL="http://localhost:3000" HANGAR_DEV_MODE=1 && nohup /root/.local/bin/uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 > /tmp/hangar.log 2>&1 & sleep 3 && curl -s localhost:8000/api/v1/openapi.json | head -c 200'
```

If the backend's port 8000 isn't bound to public IP, run openapi-typescript via ssh pipe:

```bash
ssh root@89.167.111.89 'curl -s http://localhost:8000/api/v1/openapi.json' > frontend/src/api/openapi.json
cd frontend && pnpm exec openapi-typescript src/api/openapi.json -o src/api/types.gen.ts && rm src/api/openapi.json
```

Then run: `cd frontend && pnpm typecheck` — expect success.

Commit: `feat(frontend): typed API client via openapi-fetch + generated types.gen.ts`

---

## Task 9.5 — Layout primitives (6 UI components)

**File:** `frontend/src/components/ui/SignalDot.vue`

```vue
<script setup lang="ts">
interface Props {
  tone: "green" | "amber" | "red" | "blue" | "muted";
  glow?: boolean;
}
const props = withDefaults(defineProps<Props>(), { glow: true });

const toneClass = {
  green: "bg-signal-green text-signal-green",
  amber: "bg-signal-amber text-signal-amber",
  red: "bg-signal-red text-signal-red",
  blue: "bg-signal-blue text-signal-blue",
  muted: "bg-fg-subtle text-fg-subtle",
}[props.tone];
</script>

<template>
  <span
    :class="['inline-block w-1.5 h-1.5 rounded-full', toneClass]"
    :style="glow ? 'box-shadow: 0 0 6px currentColor' : ''"
    aria-hidden="true"
  />
</template>
```

**File:** `frontend/src/components/ui/StatusPill.vue`

```vue
<script setup lang="ts">
import SignalDot from "./SignalDot.vue";

type Status = "idea" | "building" | "live" | "paused" | "shipped" | "archived" | "dead";

interface Props {
  status: Status;
}
const props = defineProps<Props>();

const mapping: Record<Status, { tone: "green" | "amber" | "red" | "blue" | "muted"; label: string }> = {
  idea: { tone: "muted", label: "idea" },
  building: { tone: "green", label: "building" },
  live: { tone: "green", label: "live" },
  paused: { tone: "amber", label: "paused" },
  shipped: { tone: "blue", label: "shipped" },
  archived: { tone: "muted", label: "archived" },
  dead: { tone: "red", label: "dead" },
};

const bgVar: Record<string, string> = {
  green: "var(--signal-green-bg)",
  amber: "var(--signal-amber-bg)",
  red: "var(--signal-red-bg)",
  blue: "var(--signal-blue-bg)",
  muted: "transparent",
};

const colorVar: Record<string, string> = {
  green: "var(--signal-green)",
  amber: "var(--signal-amber)",
  red: "var(--signal-red)",
  blue: "var(--signal-blue)",
  muted: "var(--fg-muted)",
};
</script>

<template>
  <span
    class="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-sm font-mono text-[10px]"
    :style="{ background: bgVar[mapping[status].tone], color: colorVar[mapping[status].tone] }"
  >
    <SignalDot v-if="mapping[status].tone !== 'muted'" :tone="mapping[status].tone" />
    <span>{{ mapping[status].label }}</span>
  </span>
</template>
```

**File:** `frontend/src/components/ui/MonoLabel.vue`

```vue
<script setup lang="ts">
interface Props {
  prefix?: string;
}
withDefaults(defineProps<Props>(), { prefix: "//" });
</script>

<template>
  <div class="mono-label">
    <span class="opacity-60">{{ prefix }}</span>
    <slot />
  </div>
</template>
```

**File:** `frontend/src/components/ui/KbdHint.vue`

```vue
<script setup lang="ts">
defineProps<{ keys: string }>();
</script>

<template>
  <kbd
    class="font-mono text-[10px] px-1.5 py-0.5 rounded-sm"
    style="background: var(--signal-blue-bg); color: var(--fg-muted); border: 1px solid var(--border-subtle)"
  >{{ keys }}</kbd>
</template>
```

**File:** `frontend/src/components/ui/DataRow.vue`

```vue
<script setup lang="ts">
defineProps<{ label: string }>();
</script>

<template>
  <div class="grid grid-cols-[1fr_auto] items-baseline gap-x-2 text-small py-0.5">
    <span class="text-fg-muted">{{ label }}</span>
    <span class="text-fg-body tabular-nums"><slot /></span>
  </div>
</template>
```

**File:** `frontend/src/components/ui/EmptyState.vue`

```vue
<script setup lang="ts">
defineProps<{ title: string; subtitle?: string }>();
</script>

<template>
  <div class="flex flex-col items-center justify-center gap-4 py-16 px-8 text-center">
    <h2 class="font-sans text-title text-fg-primary tracking-tight">{{ title }}</h2>
    <p v-if="subtitle" class="text-fg-muted max-w-sm">{{ subtitle }}</p>
    <div class="flex gap-3 mt-2">
      <slot name="actions" />
    </div>
  </div>
</template>
```

Commit: `feat(frontend): Cockpit UI primitives (SignalDot, StatusPill, MonoLabel, KbdHint, DataRow, EmptyState)`

---

## Task 9.6 — App shell: TopBar + AppLayout

**File:** `frontend/src/components/app/TopBar.vue`

```vue
<script setup lang="ts">
import { useRoute } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { useCommandPaletteStore } from "@/stores/command-palette";
import KbdHint from "@/components/ui/KbdHint.vue";

const route = useRoute();
const auth = useAuthStore();
const palette = useCommandPaletteStore();
</script>

<template>
  <header
    class="chrome sticky top-0 z-30 flex items-center gap-3 px-4 h-11 border-b font-sans text-body"
  >
    <div class="flex items-center gap-2 min-w-0">
      <span class="text-signal-green font-mono tracking-wider" aria-hidden="true">◈</span>
      <span class="font-medium text-fg-primary truncate max-w-[20ch]">
        {{ auth.activeWorkspace?.slug ?? "hangar" }}
      </span>
      <span v-if="route.params.slug" class="text-fg-subtle">/</span>
      <span v-if="route.params.slug" class="font-mono text-fg-body truncate max-w-[24ch]">
        {{ route.params.slug }}
      </span>
    </div>

    <button
      class="ml-auto flex items-center gap-3 h-7 px-3 rounded-md border border-border bg-bg-surface/50 text-fg-muted text-small transition-colors hover:bg-bg-surface-hi"
      @click="palette.toggle"
    >
      <span>switch project…</span>
      <KbdHint keys="⌘K" />
    </button>
  </header>
</template>
```

**File:** `frontend/src/components/app/AppLayout.vue`

```vue
<script setup lang="ts">
import TopBar from "./TopBar.vue";
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <TopBar />
    <main class="flex-1 min-h-0 overflow-hidden">
      <slot />
    </main>
  </div>
</template>
```

Commit: `feat(frontend): app shell — glass TopBar + AppLayout with sticky header`

---

## Task 9.7 — Router + main.ts wire-up

**File:** `frontend/src/router/index.ts`

```ts
import { createRouter, createWebHistory } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/",
      name: "index",
      component: () => import("@/pages/IndexRedirect.vue"),
    },
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/Login.vue"),
      meta: { anonymous: true },
    },
    {
      path: "/auth/verify",
      name: "auth-verify",
      component: () => import("@/pages/AuthVerify.vue"),
      meta: { anonymous: true },
    },
    {
      path: "/p",
      name: "projects-index",
      component: () => import("@/pages/ProjectsIndex.vue"),
    },
    {
      path: "/p/:slug",
      name: "project-detail",
      component: () => import("@/pages/ProjectDetail.vue"),
    },
    {
      path: "/:catchAll(.*)*",
      name: "not-found",
      component: () => import("@/pages/NotFound.vue"),
    },
  ],
});

router.beforeEach(async (to) => {
  const auth = useAuthStore();
  // Hydrate on first navigation if we don't have state.
  if (auth.user === null && !auth.loading && to.meta.anonymous !== true) {
    await auth.refresh();
  }
  if (!auth.isAuthed && to.meta.anonymous !== true && to.name !== "index") {
    return { name: "login" };
  }
  return true;
});

export default router;
```

**File:** `frontend/src/main.ts`

```ts
import { createPinia } from "pinia";
import { createApp } from "vue";

import App from "./App.vue";
import router from "./router";

import "./assets/base.css";

const app = createApp(App);
app.use(createPinia());
app.use(router);
app.mount("#app");
```

**File:** `frontend/src/App.vue`

```vue
<script setup lang="ts">
import AppLayout from "@/components/app/AppLayout.vue";
</script>

<template>
  <AppLayout>
    <RouterView />
  </AppLayout>
</template>
```

**File:** `frontend/src/pages/IndexRedirect.vue`

```vue
<script setup lang="ts">
import { onMounted } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";

const auth = useAuthStore();
const router = useRouter();

onMounted(async () => {
  if (!auth.isAuthed && !auth.loading) {
    await auth.refresh();
  }
  router.replace(auth.isAuthed ? "/p" : "/login");
});
</script>

<template>
  <div class="flex items-center justify-center h-[50vh]">
    <p class="mono-label">loading…</p>
  </div>
</template>
```

**File:** `frontend/src/pages/NotFound.vue`

```vue
<template>
  <div class="flex flex-col items-center justify-center gap-4 h-[60vh]">
    <h1 class="text-display text-fg-primary">404</h1>
    <p class="text-fg-muted">This hangar bay doesn't exist.</p>
    <RouterLink to="/" class="link mt-4">← back home</RouterLink>
  </div>
</template>
```

**Placeholder stubs for Phase 10+** (so routes resolve and typecheck passes):

```vue
<!-- frontend/src/pages/Login.vue -->
<template><div class="p-8"><h1 class="text-title">Login — Phase 10</h1></div></template>
```

```vue
<!-- frontend/src/pages/AuthVerify.vue -->
<template><div class="p-8"><h1 class="text-title">Auth verify — Phase 10</h1></div></template>
```

```vue
<!-- frontend/src/pages/ProjectsIndex.vue -->
<template><div class="p-8"><h1 class="text-title">Projects index — Phase 11</h1></div></template>
```

```vue
<!-- frontend/src/pages/ProjectDetail.vue -->
<template><div class="p-8"><h1 class="text-title">Project detail — Phase 11</h1></div></template>
```

Run verification:
```bash
cd frontend
pnpm typecheck
pnpm build
pnpm dev &
sleep 3
curl -s http://localhost:3000/ | head -5
kill %1 2>/dev/null
```

Expected: all commands exit 0; HTML response includes `<title>Hangar</title>` and either the dark bg script or the Vue-mounted #app.

Commit: `feat(frontend): Vue Router + main.ts wire-up + placeholder pages for Phases 10-11`

---

## Phase 9 complete when

- [ ] `pnpm install` succeeds; all new deps pinned.
- [ ] `pnpm typecheck` green.
- [ ] `pnpm build` produces a working `dist/`.
- [ ] `pnpm dev` serves the app; navigating to `/` redirects to `/login`; visiting `/login` shows the placeholder.
- [ ] `src/api/types.gen.ts` exists and contains expected schemas (Me, ProjectListItem, ProjectFullOut, etc.).
- [ ] Dark body background, Geist font loaded, `:focus-visible` outline green, scrollbars styled.
- [ ] 7 commits on main (9.1–9.7).
