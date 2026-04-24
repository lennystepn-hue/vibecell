<script setup lang="ts">
/**
 * DashboardPreview — a styled mockup of the Vibecell project dashboard.
 * Purely cosmetic (no real data, no links). Lives on the landing page so
 * visitors SEE what they get before they sign up. Uses the same ProjectOrb
 * component as the real app so the visual language is consistent.
 */
import ProjectOrb from "@/components/ui/ProjectOrb.vue";

const sidebarProjects = [
  { seed: "giftmakr", name: "giftmakr", active: false },
  { seed: "clipscribe", name: "clipscribe", active: true },
  { seed: "agentcheck", name: "agentcheck", active: false },
  { seed: "vibecell", name: "vibecell", active: false },
];

const todoItems = [
  { done: true, label: "scaffold FastAPI + db" },
  { done: true, label: "whisper transcription endpoint" },
  { done: false, label: "blog-post generator service", active: true },
  { done: false, label: "vue frontend scaffold" },
];

const sessions = [
  { when: "2m ago", summary: "feat: whisper endpoint live, 8/10 tests green" },
  { when: "1h ago", summary: "refactor: extract audio normalizer" },
  { when: "yesterday", summary: "initial scaffold + docker compose" },
];

const decisions = [
  "use whisper-large-v3 not v2 (accuracy)",
  "blog output = markdown, not html",
  "anthropic haiku for summary step",
];
</script>

<template>
  <div class="preview-frame" aria-hidden="true">
    <!-- Browser chrome -->
    <div class="browser-chrome">
      <div class="traffic">
        <span style="background: #ff6b6b" />
        <span style="background: #f5b84a" />
        <span style="background: #5cc8a4" />
      </div>
      <div class="url">
        <span class="url-proto">vibecell.dev</span><span class="url-path">/p/clipscribe</span>
      </div>
      <div class="url-meta">
        <span class="kbd">⌘K</span>
      </div>
    </div>

    <!-- App chrome: sidebar + main -->
    <div class="app-body">
      <!-- Sidebar -->
      <aside class="sidebar">
        <p class="sidebar-label">4 projects</p>
        <ul class="project-list">
          <li
            v-for="p in sidebarProjects"
            :key="p.seed"
            :class="{ 'project-active': p.active }"
          >
            <ProjectOrb :seed="p.seed" :size="14" />
            <span class="project-name">{{ p.name }}</span>
            <span v-if="p.active" class="live-dot" />
          </li>
        </ul>
      </aside>

      <!-- Main -->
      <main class="main">
        <!-- Project header -->
        <header class="proj-header">
          <ProjectOrb seed="clipscribe" :size="40" />
          <div class="proj-meta">
            <div class="proj-title-row">
              <h3 class="proj-title">Clipscribe</h3>
              <span class="pill pill-building">● building</span>
              <span class="slug">clipscribe</span>
            </div>
            <p class="proj-pitch">
              TikTok clips → long-form blog posts with AI transcription + summary.
            </p>
            <div class="proj-chips">
              <span class="chip">
                <span class="chip-dot" style="background: #5cc8a4" />
                last session 2m ago
              </span>
              <span class="chip">7D 12 sessions</span>
              <span class="chip">7D 18 commits</span>
              <span class="chip chip-green">env catalogued</span>
            </div>
          </div>
        </header>

        <!-- Dashboard grid -->
        <div class="grid">
          <!-- Focus card -->
          <section class="card card-tall">
            <p class="card-label">// current focus</p>
            <p class="focus-text">
              blog-post generator service — haiku prompt,
              <span style="color: #b592ff">1.4s</span> median latency
            </p>
            <p class="card-label" style="margin-top: 14px">// next step</p>
            <p class="card-body">
              ship v0 to staging, hook up analytics, first public demo
            </p>
          </section>

          <!-- Sessions card -->
          <section class="card">
            <p class="card-label">// sessions</p>
            <ul class="sessions">
              <li v-for="s in sessions" :key="s.when">
                <span class="sess-when">{{ s.when }}</span>
                <span class="sess-sum">{{ s.summary }}</span>
              </li>
            </ul>
          </section>

          <!-- Todos card -->
          <section class="card">
            <p class="card-label">// todos &nbsp;<span class="batch">clipscribe-v0</span></p>
            <ul class="todos">
              <li v-for="t in todoItems" :key="t.label" :class="{ 'todo-active': t.active }">
                <span v-if="t.done" class="todo-check done">✓</span>
                <span v-else-if="t.active" class="todo-check active">◉</span>
                <span v-else class="todo-check" />
                <span :class="{ 'todo-strike': t.done }">{{ t.label }}</span>
              </li>
            </ul>
          </section>

          <!-- Decisions card -->
          <section class="card">
            <p class="card-label">// decisions</p>
            <ul class="decisions">
              <li v-for="d in decisions" :key="d">
                <span class="deci-bullet">●</span> {{ d }}
              </li>
            </ul>
          </section>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.preview-frame {
  width: 100%;
  max-width: 1200px;
  margin: 0 auto;
  border-radius: 14px;
  overflow: hidden;
  background: rgba(7, 11, 16, 0.92);
  border: 1px solid rgba(138, 180, 255, 0.14);
  box-shadow:
    0 60px 120px rgba(0, 0, 0, 0.55),
    0 0 0 1px rgba(138, 180, 255, 0.06);
  /* subtle perspective so it sits like an object, not a flat rectangle */
  transform: perspective(1400px) rotateX(2deg);
  transform-origin: center top;
}

/* ─── Browser chrome ─────────────────────────────────────────────────── */
.browser-chrome {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 14px;
  background: rgba(20, 33, 50, 0.55);
  border-bottom: 1px solid rgba(138, 180, 255, 0.08);
}
.traffic {
  display: flex;
  gap: 6px;
}
.traffic span {
  width: 11px;
  height: 11px;
  border-radius: 50%;
  display: block;
}
.url {
  flex: 1;
  text-align: center;
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 11.5px;
  color: #8ba1bd;
  background: rgba(7, 11, 16, 0.65);
  padding: 5px 14px;
  border-radius: 6px;
  border: 1px solid rgba(138, 180, 255, 0.08);
  max-width: 420px;
  margin: 0 auto;
}
.url-proto {
  color: #5cc8a4;
}
.url-path {
  color: #cfd4dc;
}
.url-meta {
  min-width: 44px;
  display: flex;
  justify-content: flex-end;
}
.kbd {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 10px;
  color: #5e7088;
  background: rgba(7, 11, 16, 0.5);
  border: 1px solid rgba(138, 180, 255, 0.1);
  padding: 2px 6px;
  border-radius: 4px;
}

/* ─── App body ───────────────────────────────────────────────────────── */
.app-body {
  display: grid;
  grid-template-columns: 180px 1fr;
  min-height: 380px;
}

/* ─── Sidebar ────────────────────────────────────────────────────────── */
.sidebar {
  padding: 16px 10px;
  border-right: 1px solid rgba(138, 180, 255, 0.06);
  background: rgba(20, 33, 50, 0.2);
}
.sidebar-label {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 10px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #5e7088;
  padding: 0 8px 10px;
}
.project-list {
  list-style: none;
  padding: 0;
  margin: 0;
}
.project-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 8px;
  margin-bottom: 2px;
  border-radius: 6px;
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 12px;
  color: #8ba1bd;
}
.project-active {
  background: rgba(20, 33, 50, 0.65);
  color: #ffffff !important;
}
.project-name {
  flex: 1;
}
.live-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #5cc8a4;
  box-shadow: 0 0 8px rgba(92, 200, 164, 0.8);
}

/* ─── Main ───────────────────────────────────────────────────────────── */
.main {
  padding: 20px 24px 24px;
  overflow: hidden;
}

.proj-header {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  margin-bottom: 20px;
  padding-bottom: 18px;
  border-bottom: 1px solid rgba(138, 180, 255, 0.06);
}
.proj-title-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.proj-title {
  font-size: 20px;
  font-weight: 600;
  color: #ffffff;
  letter-spacing: -0.02em;
  margin: 0;
}
.pill {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 10px;
  padding: 2px 8px;
  border-radius: 4px;
}
.pill-building {
  background: rgba(79, 200, 214, 0.12);
  color: #4fc8d6;
  border: 1px solid rgba(79, 200, 214, 0.25);
}
.slug {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 11px;
  color: #5e7088;
}
.proj-pitch {
  font-size: 12.5px;
  color: #8ba1bd;
  margin: 6px 0 10px;
  line-height: 1.5;
}
.proj-chips {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}
.chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 10.5px;
  padding: 3px 9px;
  border-radius: 999px;
  border: 1px solid rgba(138, 180, 255, 0.1);
  color: #8ba1bd;
  background: rgba(20, 33, 50, 0.4);
}
.chip-dot {
  width: 4px;
  height: 4px;
  border-radius: 50%;
}
.chip-green {
  border-color: rgba(92, 200, 164, 0.28);
  color: #a9e5cc;
  background: rgba(92, 200, 164, 0.06);
}

/* ─── Grid of cards ──────────────────────────────────────────────────── */
.grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}
.card {
  padding: 14px 16px;
  border-radius: 8px;
  background: rgba(20, 33, 50, 0.4);
  border: 1px solid rgba(138, 180, 255, 0.08);
  min-height: 100px;
}
.card-tall {
  grid-row: span 1;
}
.card-label {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 10px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: #5e7088;
  margin: 0 0 8px;
}
.card-body {
  font-size: 12px;
  color: #8ba1bd;
  line-height: 1.55;
  margin: 0;
}
.focus-text {
  font-size: 13px;
  color: #cfd4dc;
  line-height: 1.5;
  margin: 0;
}

.sessions, .todos, .decisions {
  list-style: none;
  padding: 0;
  margin: 0;
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.sessions li {
  display: flex;
  gap: 10px;
  font-size: 11.5px;
  line-height: 1.45;
}
.sess-when {
  font-family: ui-monospace, "Geist Mono", monospace;
  color: #5e7088;
  white-space: nowrap;
  min-width: 68px;
}
.sess-sum {
  color: #cfd4dc;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.todos li {
  display: flex;
  align-items: center;
  gap: 9px;
  font-size: 12px;
  color: #cfd4dc;
}
.todo-check {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  border: 1px solid rgba(138, 180, 255, 0.2);
  text-align: center;
  font-size: 10px;
  line-height: 12px;
  color: transparent;
}
.todo-check.done {
  background: rgba(92, 200, 164, 0.18);
  border-color: rgba(92, 200, 164, 0.4);
  color: #5cc8a4;
}
.todo-check.active {
  border-color: #b592ff;
  color: #b592ff;
  animation: pulse-active 2s ease-in-out infinite;
}
.todo-strike {
  color: #5e7088;
  text-decoration: line-through;
  text-decoration-color: rgba(92, 200, 164, 0.3);
}
.todo-active span:not(.todo-check) {
  color: #ffffff;
}
.batch {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 9px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(181, 146, 255, 0.12);
  color: #b592ff;
  text-transform: none;
  letter-spacing: 0;
}

.decisions li {
  font-size: 11.5px;
  color: #cfd4dc;
  line-height: 1.5;
}
.deci-bullet {
  color: #ff6b9d;
  margin-right: 6px;
}

@keyframes pulse-active {
  0%, 100% { opacity: 0.8; }
  50% { opacity: 1; }
}

/* Smaller viewport: stack the sidebar on top */
@media (max-width: 640px) {
  .app-body {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: none;
    border-bottom: 1px solid rgba(138, 180, 255, 0.06);
  }
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
