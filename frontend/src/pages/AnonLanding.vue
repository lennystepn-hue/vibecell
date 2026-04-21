<script setup lang="ts">
import { ref, onMounted } from "vue";
import { useRouter } from "vue-router";
import DiamondHero from "@/components/landing/DiamondHero.vue";

const router = useRouter();

function goSignIn() {
  router.push("/login");
}

function scrollToDemo() {
  document.getElementById("how-it-works")?.scrollIntoView({ behavior: "smooth" });
}

// Animated counter for stat strip
const counters = ref([
  { value: 0, target: 17, label: "MCP tools", suffix: "" },
  { value: 0, target: 5, label: "IDE clients", suffix: "" },
  { value: 0, target: 2, label: "setup", suffix: "s" },
  { value: 0, target: 0, label: "install", suffix: "" },
]);

onMounted(() => {
  const duration = 1400;
  const step = 16;
  const start = Date.now();
  function tick() {
    const elapsed = Date.now() - start;
    const progress = Math.min(elapsed / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    counters.value.forEach((c) => {
      c.value = Math.round(ease * c.target);
    });
    if (progress < 1) setTimeout(tick, step);
  }
  setTimeout(tick, 400);
});

const features = [
  {
    icon: "terminal",
    label: "Claude + your code, one click",
    body: "Vibecell ships as an MCP server that plugs into Claude Desktop, Claude Code, Cursor, Zed, and any MCP-compatible IDE. No wiring needed.",
    accent: true,
  },
  {
    icon: "brain",
    label: "AI that knows your projects",
    body: "Project context, next steps, open questions, and tech stack are auto-loaded at session start. Your AI starts exactly where you left off.",
    accent: false,
  },
  {
    icon: "scroll",
    label: "Ship log that writes itself",
    body: "Every session end triggers an auto-log: what shipped, what's next, any blockers. Zero cognitive overhead.",
    accent: false,
  },
  {
    icon: "github",
    label: "13 projects in seconds",
    body: "Import your entire GitHub org in one click. AI reads your README and manifests to generate pitch, tags, stack, and infra automatically.",
    accent: false,
  },
  {
    icon: "chart",
    label: "Portfolio intel",
    body: "Activity heatmap across your whole portfolio. Stagnation detection flags what hasn't shipped in weeks before you forget it exists.",
    accent: false,
  },
  {
    icon: "key",
    label: "Workspace-scoped secrets",
    body: "Inline secrets, 1Password, or Bitwarden — all scoped to your workspace. Your credentials never leave your machine in plaintext.",
    accent: false,
  },
];

const steps = [
  {
    num: "01",
    title: "Register your workspace",
    body: "Create a free account with magic-link or passkey. Your workspace is ready in under 10 seconds.",
  },
  {
    num: "02",
    title: "Connect Claude (or any MCP client)",
    body: "Copy one config line into your claude_desktop_config.json. Vibecell appears as a tool server instantly.",
  },
  {
    num: "03",
    title: "Just work — context follows you",
    body: "Switch projects, switch machines, switch AI clients. Your context is always there. Ship more, context-switch less.",
  },
];
</script>

<template>
  <div class="min-h-screen text-fg-primary overflow-x-hidden" style="background: #070b10">

    <!-- ─── Nav ──────────────────────────────────────────────────────────── -->
    <header class="fixed top-0 left-0 right-0 z-50 flex items-center justify-between px-6 py-3"
      style="background: rgba(7,11,16,0.75); backdrop-filter: blur(12px); border-bottom: 1px solid rgba(138,180,255,0.08)">
      <div class="flex items-center gap-2.5">
        <span class="text-signal-green font-mono text-[18px] leading-none select-none">◈</span>
        <span class="font-mono text-[11px] tracking-[0.15em] uppercase text-fg-subtle">Vibecell</span>
      </div>
      <nav class="hidden sm:flex items-center gap-6">
        <router-link to="/pricing"
          class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150">
          Pricing
        </router-link>
        <router-link to="/legal"
          class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150">
          Legal
        </router-link>
        <a href="https://github.com" target="_blank" rel="noopener"
          class="text-small text-fg-muted hover:text-fg-primary transition-colors duration-150">
          GitHub
        </a>
      </nav>
      <button
        class="px-4 py-1.5 rounded text-small font-mono bg-signal-green text-bg-body hover:opacity-90 transition-opacity"
        style="color: #070b10"
        @click="goSignIn">
        Get started →
      </button>
    </header>

    <!-- ─── Hero ─────────────────────────────────────────────────────────── -->
    <section class="relative min-h-screen flex items-center overflow-hidden pt-16">
      <!-- Subtle grid background -->
      <div class="absolute inset-0 pointer-events-none"
        style="background-image: linear-gradient(rgba(138,180,255,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(138,180,255,0.03) 1px, transparent 1px); background-size: 60px 60px" />
      <!-- Top-left gradient bloom -->
      <div class="absolute -top-40 -left-40 w-[700px] h-[700px] rounded-full pointer-events-none"
        style="background: radial-gradient(circle, rgba(92,200,164,0.06) 0%, transparent 70%)" />

      <div class="relative z-10 w-full max-w-7xl mx-auto px-6 grid lg:grid-cols-2 gap-12 items-center py-24">

        <!-- Left: copy -->
        <div>
          <!-- Badge -->
          <div class="inline-flex items-center gap-2 px-3 py-1.5 rounded-full border mb-8 font-mono text-[11px] tracking-[0.08em] uppercase"
            style="border-color: rgba(92,200,164,0.25); color: #5cc8a4; background: rgba(92,200,164,0.07)">
            <span class="w-1.5 h-1.5 rounded-full bg-signal-green animate-pulse" />
            Now in early access
          </div>

          <h1 class="font-sans font-semibold mb-6 leading-[1.07] tracking-tight"
            style="font-size: clamp(2.4rem, 5vw, 4rem); letter-spacing: -0.04em; color: #ffffff">
            Remember every<br>
            project<br>
            <span style="color: #5cc8a4">you ship.</span>
          </h1>

          <p class="mb-10 leading-relaxed max-w-md"
            style="font-size: 1.05rem; color: #8ba1bd; line-height: 1.65">
            Vibecell is the operating system for vibecoders — a context layer, MCP server, and
            ship-log that keeps your AI and your projects in sync across every session.
          </p>

          <div class="flex flex-wrap gap-3 mb-8">
            <button
              class="px-6 py-3 rounded-lg font-mono font-semibold text-[13px] transition-all hover:opacity-90 hover:scale-[1.02] active:scale-[0.99]"
              style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 24px rgba(92,200,164,0.25)"
              @click="goSignIn">
              Get started — free
            </button>
            <button
              class="px-6 py-3 rounded-lg font-mono text-[13px] transition-all hover:border-opacity-60"
              style="border: 1px solid rgba(138,180,255,0.18); color: #cfd4dc; background: rgba(20,33,50,0.4)"
              @click="scrollToDemo">
              See how it works ↓
            </button>
          </div>

          <p class="font-mono text-[11px]" style="color: #5e7088">
            No credit card · free plan included · self-hostable
          </p>
        </div>

        <!-- Right: 3D Diamond -->
        <div class="relative flex items-center justify-center">
          <div class="relative w-full" style="aspect-ratio: 1; max-width: 480px; margin: auto">
            <DiamondHero class="w-full h-full" />
            <!-- ◈ symbol overlay — subtle brand stamp -->
            <div class="absolute inset-0 flex items-center justify-center pointer-events-none select-none">
              <span class="font-mono" style="font-size: 3.5rem; color: rgba(92,200,164,0.12); line-height:1">◈</span>
            </div>
          </div>
          <!-- Decorative glow behind canvas -->
          <div class="absolute inset-0 pointer-events-none rounded-full"
            style="background: radial-gradient(circle at 50% 50%, rgba(92,200,164,0.07) 0%, transparent 65%)" />
        </div>
      </div>
    </section>

    <!-- ─── Stats strip ──────────────────────────────────────────────────── -->
    <div class="border-y" style="border-color: rgba(138,180,255,0.08); background: rgba(20,33,50,0.3)">
      <div class="max-w-4xl mx-auto px-6 py-8 grid grid-cols-2 md:grid-cols-4 gap-6 text-center">
        <div v-for="c in counters" :key="c.label">
          <p class="font-mono font-bold mb-1" style="font-size: 2rem; color: #5cc8a4; letter-spacing: -0.04em">
            {{ c.value }}{{ c.suffix }}
          </p>
          <p class="font-mono text-[11px] uppercase tracking-[0.1em]" style="color: #5e7088">
            {{ c.label }}
          </p>
        </div>
      </div>
    </div>

    <!-- ─── Feature grid ─────────────────────────────────────────────────── -->
    <section class="max-w-6xl mx-auto px-6 py-28">
      <div class="text-center mb-16">
        <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">
          Everything you need
        </p>
        <h2 class="font-semibold leading-tight" style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: #ffffff">
          Built for the way you actually code
        </h2>
      </div>

      <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-5">
        <div
          v-for="(f, i) in features"
          :key="f.label"
          class="rounded-xl p-6 transition-all duration-300 hover:translate-y-[-2px] group cursor-default"
          :style="f.accent
            ? 'background: rgba(92,200,164,0.06); border: 1px solid rgba(92,200,164,0.2); box-shadow: 0 0 32px rgba(92,200,164,0.04)'
            : 'background: rgba(20,33,50,0.45); border: 1px solid rgba(138,180,255,0.1)'"
        >
          <!-- Icon -->
          <div class="w-9 h-9 rounded-lg flex items-center justify-center mb-4"
            :style="f.accent
              ? 'background: rgba(92,200,164,0.15)'
              : 'background: rgba(138,180,255,0.07)'">
            <!-- terminal -->
            <svg v-if="f.icon === 'terminal'" viewBox="0 0 20 20" fill="none" class="w-4.5 h-4.5" style="width:18px;height:18px">
              <path d="M3 5l4 4-4 4M9 13h8" stroke="#5cc8a4" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            <!-- brain -->
            <svg v-if="f.icon === 'brain'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
              <path d="M7 10c0-1.65 1.34-3 3-3s3 1.35 3 3-1.34 3-3 3M10 7V4M10 16v-3M4.93 4.93l2.12 2.12M12.95 12.95l2.12 2.12M4 10H7M13 10h3M4.93 15.07l2.12-2.12M12.95 7.05l2.12-2.12" stroke="#8ba1bd" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
            <!-- scroll -->
            <svg v-if="f.icon === 'scroll'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
              <rect x="4" y="3" width="12" height="14" rx="2" stroke="#8ba1bd" stroke-width="1.4"/>
              <path d="M7 7h6M7 10h6M7 13h4" stroke="#8ba1bd" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
            <!-- github -->
            <svg v-if="f.icon === 'github'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
              <path fill-rule="evenodd" clip-rule="evenodd" d="M10 2C5.58 2 2 5.58 2 10c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38v-1.34c-2.22.48-2.69-1.07-2.69-1.07-.36-.92-.89-1.17-.89-1.17-.73-.5.05-.49.05-.49.8.06 1.22.82 1.22.82.71 1.22 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82A7.69 7.69 0 0 1 10 6.84c.68 0 1.36.09 2 .26 1.52-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48v2.19c0 .21.15.46.55.38A8.013 8.013 0 0 0 18 10c0-4.42-3.58-8-8-8Z" fill="#8ba1bd"/>
            </svg>
            <!-- chart -->
            <svg v-if="f.icon === 'chart'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
              <rect x="3" y="11" width="3" height="5" rx="1" fill="none" stroke="#8ba1bd" stroke-width="1.4"/>
              <rect x="8" y="7" width="3" height="9" rx="1" fill="none" stroke="#8ba1bd" stroke-width="1.4"/>
              <rect x="13" y="4" width="3" height="12" rx="1" fill="none" stroke="#8ba1bd" stroke-width="1.4"/>
            </svg>
            <!-- key -->
            <svg v-if="f.icon === 'key'" viewBox="0 0 20 20" fill="none" style="width:18px;height:18px">
              <circle cx="8" cy="9" r="3" stroke="#8ba1bd" stroke-width="1.4"/>
              <path d="M10.5 11.5l5 5M13 14l1.5 1.5" stroke="#8ba1bd" stroke-width="1.4" stroke-linecap="round"/>
            </svg>
          </div>

          <h3 class="font-semibold mb-2" style="font-size: 14px; color: #ffffff; letter-spacing: -0.01em">
            {{ f.label }}
          </h3>
          <p class="leading-relaxed" style="font-size: 12px; color: #8ba1bd; line-height: 1.6">
            {{ f.body }}
          </p>

          <!-- Accent badge for first card -->
          <div v-if="i === 0" class="mt-4 inline-flex items-center gap-1.5 font-mono"
            style="font-size: 10px; color: #5cc8a4; letter-spacing: 0.08em; text-transform: uppercase">
            <span class="w-1 h-1 rounded-full bg-signal-green" />
            MCP-native
          </div>
        </div>
      </div>
    </section>

    <!-- ─── How it works ─────────────────────────────────────────────────── -->
    <section id="how-it-works" class="py-28 px-6"
      style="background: rgba(20,33,50,0.25); border-top: 1px solid rgba(138,180,255,0.07); border-bottom: 1px solid rgba(138,180,255,0.07)">
      <div class="max-w-5xl mx-auto">
        <div class="text-center mb-16">
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">
            Setup in 3 steps
          </p>
          <h2 class="font-semibold" style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: #ffffff">
            Zero install. Full power.
          </h2>
        </div>

        <div class="grid md:grid-cols-3 gap-8 relative">
          <!-- Connector line (desktop) -->
          <div class="hidden md:block absolute top-8 left-[calc(33.33%+1rem)] right-[calc(33.33%+1rem)] h-px"
            style="background: linear-gradient(90deg, rgba(92,200,164,0.3), rgba(92,200,164,0.3))" />

          <div v-for="step in steps" :key="step.num" class="relative text-center">
            <!-- Number bubble -->
            <div class="w-16 h-16 rounded-full mx-auto mb-6 flex items-center justify-center font-mono font-bold relative"
              style="background: rgba(92,200,164,0.08); border: 1px solid rgba(92,200,164,0.25); color: #5cc8a4; font-size: 18px; box-shadow: 0 0 20px rgba(92,200,164,0.08)">
              {{ step.num }}
              <!-- glow ring pulse -->
              <div class="absolute inset-0 rounded-full animate-ping opacity-10"
                style="background: rgba(92,200,164,0.3); animation-duration: 3s" />
            </div>
            <h3 class="font-semibold mb-3" style="font-size: 15px; color: #ffffff; letter-spacing: -0.01em">
              {{ step.title }}
            </h3>
            <p style="font-size: 12px; color: #8ba1bd; line-height: 1.65">
              {{ step.body }}
            </p>
          </div>
        </div>
      </div>
    </section>

    <!-- ─── Pricing teaser ───────────────────────────────────────────────── -->
    <section class="py-28 px-6">
      <div class="max-w-3xl mx-auto">
        <div class="text-center mb-14">
          <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-3" style="color: #5cc8a4">
            Pricing
          </p>
          <h2 class="font-semibold mb-3" style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: #ffffff">
            Start free. Ship serious.
          </h2>
          <p style="color: #8ba1bd; font-size: 14px">Upgrade only when you outgrow the free tier.</p>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <!-- Free -->
          <div class="rounded-xl p-7 flex flex-col"
            style="background: rgba(20,33,50,0.5); border: 1px solid rgba(138,180,255,0.1)">
            <p class="font-mono text-[11px] uppercase tracking-[0.12em] mb-3" style="color: #5e7088">Free</p>
            <p class="font-bold mb-4" style="font-size: 2.8rem; color: #ffffff; letter-spacing: -0.04em; line-height: 1">
              $0
            </p>
            <ul class="space-y-2.5 mb-8 flex-1" style="font-size: 12px; color: #8ba1bd">
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> 3 active projects</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> 500 MCP calls / month</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> Magic link login</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> GitHub import + AI enrichment</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> Full MCP + CLI access</li>
            </ul>
            <button
              class="w-full py-2.5 rounded-lg font-mono text-[13px] transition-all hover:opacity-80"
              style="border: 1px solid rgba(138,180,255,0.18); color: #cfd4dc"
              @click="goSignIn">
              Get started free
            </button>
          </div>

          <!-- Pro -->
          <div class="rounded-xl p-7 flex flex-col relative overflow-hidden"
            style="background: rgba(92,200,164,0.05); border: 1px solid rgba(92,200,164,0.25); box-shadow: 0 0 40px rgba(92,200,164,0.06)">
            <!-- Most popular ribbon -->
            <div class="absolute top-0 right-0 font-mono text-[10px] uppercase tracking-widest px-3 py-1 rounded-bl"
              style="background: #5cc8a4; color: #070b10">
              Most popular
            </div>
            <p class="font-mono text-[11px] uppercase tracking-[0.12em] mb-3" style="color: #5cc8a4">Pro</p>
            <div class="flex items-end gap-1 mb-1">
              <p class="font-bold" style="font-size: 2.8rem; color: #ffffff; letter-spacing: -0.04em; line-height: 1">$12</p>
              <p class="mb-2" style="color: #8ba1bd; font-size: 13px">/ month</p>
            </div>
            <p class="mb-4" style="font-size: 11px; color: #5e7088">Per workspace · cancel any time</p>
            <ul class="space-y-2.5 mb-8 flex-1" style="font-size: 12px; color: #8ba1bd">
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> <strong style="color:#cfd4dc">Unlimited</strong>&nbsp;projects</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> 10,000 MCP calls / month</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> Passkey (Touch ID / Face ID)</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> Up to 5 workspace seats</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> Auto-signals + Portfolio intel</li>
              <li class="flex gap-2.5 items-start"><span style="color:#5cc8a4;margin-top:1px">✓</span> Priority support</li>
            </ul>
            <button
              class="w-full py-2.5 rounded-lg font-mono font-semibold text-[13px] transition-all hover:opacity-90"
              style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 20px rgba(92,200,164,0.2)"
              @click="goSignIn">
              Start free trial →
            </button>
            <p class="text-center mt-2 font-mono" style="font-size: 10px; color: #5e7088">14-day trial · no credit card</p>
          </div>
        </div>

        <div class="text-center mt-8">
          <router-link to="/pricing"
            class="font-mono transition-colors hover:text-fg-primary"
            style="font-size: 12px; color: #5e7088">
            See full pricing details →
          </router-link>
        </div>
      </div>
    </section>

    <!-- ─── Final CTA ────────────────────────────────────────────────────── -->
    <section class="py-32 px-6 text-center relative overflow-hidden"
      style="background: rgba(20,33,50,0.4); border-top: 1px solid rgba(138,180,255,0.07)">
      <!-- Background glow -->
      <div class="absolute inset-0 pointer-events-none"
        style="background: radial-gradient(ellipse 60% 60% at 50% 50%, rgba(92,200,164,0.05) 0%, transparent 70%)" />

      <div class="relative z-10 max-w-2xl mx-auto">
        <p class="font-mono text-[11px] uppercase tracking-[0.15em] mb-4" style="color: #5cc8a4">
          Ready to ship smarter?
        </p>
        <h2 class="font-semibold mb-5" style="font-size: clamp(1.8rem, 4vw, 3rem); letter-spacing: -0.04em; color: #ffffff; line-height: 1.1">
          Start shipping smarter.<br>
          <span style="color: #5cc8a4">Today.</span>
        </h2>
        <p class="mb-10" style="font-size: 14px; color: #8ba1bd; line-height: 1.65">
          Join the builders who never lose project context again.<br>
          Free forever. No credit card.
        </p>
        <button
          class="px-10 py-4 rounded-xl font-mono font-semibold text-[14px] transition-all hover:opacity-90 hover:scale-[1.02] active:scale-[0.99]"
          style="background: #5cc8a4; color: #070b10; box-shadow: 0 0 40px rgba(92,200,164,0.3), 0 4px 20px rgba(0,0,0,0.3)"
          @click="goSignIn">
          Get started — free →
        </button>
        <p class="mt-4 font-mono" style="font-size: 11px; color: #5e7088">
          vibecell.dev · No install · Free plan · GDPR compliant
        </p>
      </div>
    </section>

    <!-- ─── Footer ───────────────────────────────────────────────────────── -->
    <footer class="px-6 py-10" style="border-top: 1px solid rgba(138,180,255,0.08)">
      <div class="max-w-5xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">
        <!-- Logo -->
        <div class="flex items-center gap-2.5">
          <span class="font-mono" style="font-size: 20px; color: #5cc8a4">◈</span>
          <span class="font-mono text-[11px] tracking-[0.15em] uppercase" style="color: #5e7088">Vibecell</span>
        </div>
        <!-- Links -->
        <nav class="flex flex-wrap justify-center gap-6" style="font-size: 12px; color: #5e7088">
          <router-link to="/pricing" class="hover:text-fg-muted transition-colors">Pricing</router-link>
          <router-link to="/legal" class="hover:text-fg-muted transition-colors">Privacy</router-link>
          <router-link to="/legal?tab=terms" class="hover:text-fg-muted transition-colors">Terms</router-link>
          <a href="https://github.com" target="_blank" rel="noopener" class="hover:text-fg-muted transition-colors">GitHub</a>
          <a href="mailto:hello@vibecell.dev" class="hover:text-fg-muted transition-colors">Contact</a>
        </nav>
        <!-- Copyright -->
        <p class="font-mono" style="font-size: 11px; color: #5e7088">© 2026 Vibecell</p>
      </div>
    </footer>
  </div>
</template>
