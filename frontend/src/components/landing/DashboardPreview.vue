<script setup lang="ts">
/**
 * DashboardPreview — browser-chrome frame around a real screenshot of the
 * Vibecell dashboard. The image lives at /landing-dashboard.png (public
 * dir) — save a high-res screenshot of a real project page there and the
 * landing picks it up on next build.
 *
 * If the image is missing (dev, first-deploy) the <img> will show its alt
 * text and the frame still looks intentional. No hard crash.
 */
import { ref } from "vue";

// Toggle-on-error so the placeholder shows only when the screenshot is
// actually missing instead of flashing during slow loads.
const imgFailed = ref(false);
</script>

<template>
  <div class="preview-frame" aria-hidden="true">
    <!-- Browser chrome — macOS-ish -->
    <div class="browser-chrome">
      <div class="traffic">
        <span style="background: #ff6b6b" />
        <span style="background: #f5b84a" />
        <span style="background: #5cc8a4" />
      </div>
      <div class="url">
        <span class="url-proto">vibecell.dev</span><span class="url-path">/p/vibecell</span>
      </div>
      <div class="url-meta">
        <span class="kbd">⌘K</span>
      </div>
    </div>

    <!-- Screenshot slot — replace with your own crisp dashboard capture -->
    <div class="screen">
      <img
        v-if="!imgFailed"
        src="/landing-dashboard.png"
        alt="Vibecell project dashboard showing sidebar with projects, project header, and cards for health, environments, stack, current focus, sessions and decisions"
        loading="lazy"
        @error="imgFailed = true"
      />
      <div v-else class="placeholder">
        <p class="placeholder-label">//dashboard</p>
        <p class="placeholder-body">
          Save a dashboard screenshot to
          <code>frontend/public/landing-dashboard.png</code>
        </p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.preview-frame {
  width: 100%;
  max-width: 1280px;
  margin: 0 auto;
  border-radius: 16px;
  overflow: hidden;
  background: rgba(7, 11, 16, 0.92);
  border: 1px solid rgba(138, 180, 255, 0.14);
  box-shadow:
    0 60px 120px rgba(0, 0, 0, 0.55),
    0 0 80px rgba(92, 200, 164, 0.04),
    0 0 0 1px rgba(138, 180, 255, 0.06);
  transform: perspective(1800px) rotateX(2deg);
  transform-origin: center top;
  transition: transform 600ms cubic-bezier(0.22, 1, 0.36, 1);
}
.preview-frame:hover {
  transform: perspective(1800px) rotateX(0deg);
}

/* ─── Browser chrome ────────────────────────────────────────────────── */
.browser-chrome {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 12px 16px;
  background: rgba(20, 33, 50, 0.55);
  border-bottom: 1px solid rgba(138, 180, 255, 0.08);
}
.traffic {
  display: flex;
  gap: 7px;
}
.traffic span {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  display: block;
}
.url {
  flex: 1;
  text-align: center;
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 12px;
  color: #8ba1bd;
  background: rgba(7, 11, 16, 0.65);
  padding: 6px 14px;
  border-radius: 6px;
  border: 1px solid rgba(138, 180, 255, 0.08);
  max-width: 440px;
  margin: 0 auto;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.url-proto { color: #5cc8a4; }
.url-path { color: #cfd4dc; }
.url-meta {
  min-width: 50px;
  display: flex;
  justify-content: flex-end;
}
.kbd {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 10px;
  color: #5e7088;
  background: rgba(7, 11, 16, 0.5);
  border: 1px solid rgba(138, 180, 255, 0.1);
  padding: 3px 7px;
  border-radius: 4px;
}

/* ─── Screen ───────────────────────────────────────────────────────── */
.screen {
  position: relative;
  background: #070b10;
  min-height: 300px;
}
.screen img {
  display: block;
  width: 100%;
  height: auto;
}

.placeholder {
  padding: 80px 40px;
  text-align: center;
}
.placeholder-label {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 12px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #5cc8a4;
  margin: 0 0 14px;
}
.placeholder-body {
  font-size: 13px;
  color: #8ba1bd;
  max-width: 480px;
  margin: 0 auto;
  line-height: 1.6;
}
.placeholder code {
  font-family: ui-monospace, "Geist Mono", monospace;
  font-size: 12px;
  color: #cfd4dc;
  background: rgba(138, 180, 255, 0.08);
  padding: 2px 6px;
  border-radius: 4px;
  border: 1px solid rgba(138, 180, 255, 0.1);
}
</style>
