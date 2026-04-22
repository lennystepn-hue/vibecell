<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRouter } from "vue-router";

import { useAuthStore } from "@/stores/auth";
import { useThemeStore, type ThemeName } from "@/stores/theme";

const props = defineProps<{
  /** Visual variant — "light" for dark marketing pages, "chrome" for the app chrome. */
  variant?: "light" | "chrome";
}>();

const auth = useAuthStore();
const router = useRouter();
const theme = useThemeStore();

function applyTheme(name: ThemeName) {
  theme.apply(name);
  // Keep the menu open so the user can see the switch take effect + try
  // another preset without re-opening. Only toggle switcher submenu if
  // explicitly clicked outside.
}

const open = ref(false);
const menuRef = ref<HTMLElement | null>(null);

const variant = computed(() => props.variant ?? "chrome");

const initials = computed(() => {
  const email = auth.user?.email ?? "";
  if (!email) return "??";
  const [local] = email.split("@");
  const parts = local.split(/[._-]/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return (local.slice(0, 2) || "??").toUpperCase();
});

const avatarColors = computed(() => {
  // Deterministic colour from email hash
  const s = auth.user?.email ?? "";
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) | 0;
  const hue = Math.abs(h) % 360;
  return {
    bg: `hsl(${hue} 55% 22%)`,
    ring: `hsl(${hue} 55% 35%)`,
    text: `hsl(${hue} 55% 85%)`,
  };
});

function toggle() { open.value = !open.value; }

function close(e?: MouseEvent) {
  if (!open.value) return;
  if (e && menuRef.value && menuRef.value.contains(e.target as Node)) return;
  open.value = false;
}

async function signOut() {
  await auth.logout();
  open.value = false;
  router.push("/");
}

function goDashboard() {
  open.value = false;
  router.push("/p");
}

function goSettings() {
  open.value = false;
  router.push("/settings");
}

onMounted(() => {
  document.addEventListener("click", close);
  document.addEventListener("keydown", onKey);
});
onBeforeUnmount(() => {
  document.removeEventListener("click", close);
  document.removeEventListener("keydown", onKey);
});

function onKey(e: KeyboardEvent) {
  if (e.key === "Escape") open.value = false;
}
</script>

<template>
  <div ref="menuRef" class="relative" v-if="auth.isAuthed && auth.user">
    <button
      type="button"
      class="flex items-center gap-2 rounded-full transition-all focus:outline-none"
      :class="variant === 'light'
        ? 'pl-1 pr-3 py-1 hover:bg-white/5 border border-white/10'
        : 'h-8 px-1 hover:bg-bg-surface-hi'"
      :style="variant === 'light' ? 'color:#cfd4dc' : ''"
      @click.stop="toggle"
      :aria-expanded="open"
      aria-haspopup="menu"
    >
      <span
        class="flex items-center justify-center w-7 h-7 rounded-full font-mono text-[11px] font-semibold ring-1"
        :style="{ background: avatarColors.bg, color: avatarColors.text, boxShadow: `inset 0 0 0 1px ${avatarColors.ring}` }"
      >{{ initials }}</span>
      <span v-if="variant === 'light'" class="font-mono text-[11px] tracking-[0.08em]">
        {{ auth.activeWorkspace?.slug ?? 'workspace' }}
      </span>
      <svg class="w-3 h-3 opacity-60" viewBox="0 0 12 12" fill="none">
        <path d="M3 4.5L6 7.5L9 4.5" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </button>

    <transition
      enter-active-class="transition ease-out duration-100"
      enter-from-class="opacity-0 translate-y-[-4px]"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition ease-in duration-75"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        role="menu"
        class="absolute right-0 mt-2 w-60 rounded-lg overflow-hidden z-50 border shadow-xl"
        style="background: rgba(10, 16, 24, 0.96); border-color: rgba(138,180,255,0.12); backdrop-filter: blur(12px)"
      >
        <div class="px-3 py-3 border-b" style="border-color: rgba(138,180,255,0.08)">
          <p class="font-mono text-[10px] uppercase tracking-[0.12em]" style="color:#5e7088">Signed in as</p>
          <p class="text-small truncate mt-0.5" style="color:#cfd4dc">{{ auth.user.email }}</p>
          <p v-if="auth.activeWorkspace" class="font-mono text-[10px] mt-1.5" style="color:#5cc8a4">
            ◈ {{ auth.activeWorkspace.slug }}
          </p>
        </div>
        <div class="py-1">
          <button
            class="w-full text-left px-3 py-2 text-small hover:bg-white/5 flex items-center gap-2.5 transition-colors"
            style="color:#cfd4dc"
            role="menuitem"
            @click="goDashboard"
          >
            <span class="font-mono text-signal-green">→</span>
            Dashboard
          </button>
          <button
            class="w-full text-left px-3 py-2 text-small hover:bg-white/5 flex items-center gap-2.5 transition-colors"
            style="color:#cfd4dc"
            role="menuitem"
            @click="goSettings"
          >
            <span class="font-mono" style="color:#8ba1bd">⚙</span>
            Settings
          </button>
        </div>
        <!-- Theme switcher. Clicks keep the menu open so you can try presets. -->
        <div class="py-2 border-t" style="border-color: rgba(138,180,255,0.08)">
          <p class="font-mono text-[10px] uppercase tracking-[0.12em] px-3 mb-1.5" style="color:#5e7088">Theme</p>
          <div class="grid grid-cols-3 gap-1 px-2" @click.stop>
            <button
              v-for="[name, meta] in theme.options"
              :key="name"
              :title="meta.hint"
              class="rounded px-2 py-1.5 text-[11px] font-mono transition-all"
              :class="theme.active === name
                ? 'bg-signal-green/15 text-signal-green ring-1 ring-signal-green/40'
                : 'text-fg-muted hover:text-fg-body hover:bg-white/[0.04]'"
              @click="applyTheme(name)"
            >{{ meta.label.split(' ')[0] }}</button>
          </div>
        </div>
        <div class="py-1 border-t" style="border-color: rgba(138,180,255,0.08)">
          <button
            class="w-full text-left px-3 py-2 text-small hover:bg-white/5 flex items-center gap-2.5 transition-colors"
            style="color:#e3a5a5"
            role="menuitem"
            @click="signOut"
          >
            <span class="font-mono">×</span>
            Sign out
          </button>
        </div>
      </div>
    </transition>
  </div>
</template>
