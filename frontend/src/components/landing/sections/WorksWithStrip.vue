<template>
<!-- ─── "Works with" logo strip ────────────────────────────────────── -->
<section class="relative px-6 py-8 -mt-8">
  <div class="max-w-5xl mx-auto flex flex-col sm:flex-row items-center justify-center gap-6 sm:gap-10">
    <p class="font-mono text-nano tracking-wide uppercase" style="color: var(--fg-subtle)">
      Works with
    </p>
    <div class="flex flex-wrap items-center justify-center gap-x-8 gap-y-4 opacity-80">
      <!-- Brand logomarks below come from simple-icons.org (CC0 / public
           domain). All rendered fill="currentColor" so they pick up the
           cockpit-grey text color and stay theme-stable in light/dark.
           Stylistically subordinate to the wordmark next to them — the
           icons read as a tiny prefix, not a heavy logo wall. -->
      <!-- Claude / Anthropic — angular A-mark (simple-icons: anthropic) -->
      <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: var(--fg-body); font-size: 14px">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M17.304 3.541h-3.672l6.696 16.918H24Zm-10.608 0L0 20.459h3.744l1.37-3.553h7.005l1.37 3.553h3.744L10.536 3.541Zm-.371 10.223 2.291-5.946 2.292 5.946Z"/>
        </svg>
        <span class="font-mono text-body">Claude</span>
      </span>
      <!-- Cursor — official cursor mark (simple-icons: cursor) -->
      <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: var(--fg-body); font-size: 14px">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M11.925 24l10.425-6V6L11.925 0 1.5 6v12l10.425 6zm10.425-6L11.925 12 1.5 18l10.425 6 10.425-6zm0-12L11.925 12V0l10.425 6zM1.5 6v12l10.425-6V0L1.5 6z"/>
        </svg>
        <span class="font-mono text-body">Cursor</span>
      </span>
      <!-- OpenAI — petal/knot logomark (simple-icons: openai) -->
      <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: var(--fg-body); font-size: 14px">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M22.282 9.821a5.985 5.985 0 0 0-.516-4.91 6.046 6.046 0 0 0-6.51-2.9A6.065 6.065 0 0 0 4.981 4.18a5.985 5.985 0 0 0-3.998 2.9 6.046 6.046 0 0 0 .743 7.097 5.98 5.98 0 0 0 .51 4.911 6.051 6.051 0 0 0 6.515 2.9A5.985 5.985 0 0 0 13.26 24a6.056 6.056 0 0 0 5.772-4.206 5.99 5.99 0 0 0 3.998-2.9 6.056 6.056 0 0 0-.747-7.073zM13.26 22.43a4.476 4.476 0 0 1-2.876-1.04l.142-.08 4.778-2.758a.795.795 0 0 0 .393-.681v-6.737l2.02 1.168a.07.07 0 0 1 .038.052v5.583a4.504 4.504 0 0 1-4.495 4.494zM3.6 18.304a4.47 4.47 0 0 1-.535-3.014l.142.085 4.783 2.759a.771.771 0 0 0 .781 0l5.843-3.369v2.332a.08.08 0 0 1-.033.062L9.74 19.95a4.5 4.5 0 0 1-6.14-1.646zM2.34 7.896a4.485 4.485 0 0 1 2.366-1.973V11.6a.766.766 0 0 0 .388.677l5.815 3.354-2.02 1.168a.076.076 0 0 1-.071 0l-4.83-2.786A4.504 4.504 0 0 1 2.34 7.872zm16.597 3.855L13.103 8.364 15.12 7.2a.076.076 0 0 1 .07 0l4.83 2.792a4.494 4.494 0 0 1-.676 8.104V12.42a.79.79 0 0 0-.407-.667zm2.01-3.024-.142-.085-4.774-2.782a.776.776 0 0 0-.785 0L9.409 9.23V6.897a.066.066 0 0 1 .028-.062l4.83-2.787a4.5 4.5 0 0 1 6.681 4.66zM8.307 12.863l-2.02-1.164a.08.08 0 0 1-.038-.057V6.074a4.5 4.5 0 0 1 7.376-3.454l-.142.081L8.704 5.46a.795.795 0 0 0-.393.681zm1.098-2.366 2.602-1.5 2.607 1.5v3l-2.598 1.5-2.607-1.5Z"/>
        </svg>
        <span class="font-mono text-body">OpenAI</span>
      </span>
      <!-- Zed — angular Z arrow (simple-icons: zedindustries) -->
      <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: var(--fg-body); font-size: 14px">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M11.999 0a11.999 11.999 0 1 0 0 23.998A11.999 11.999 0 0 0 12 0Zm5.997 5.987-7.992 7.991h7.992v3.998H5.962v-3.998l7.991-7.991H5.962V1.989h12.034Z"/>
        </svg>
        <span class="font-mono text-body">Zed</span>
      </span>
      <!-- Continue.dev — chevron continuation mark. Their actual logo
           is a stylised "carrot/play" pair; this is a faithful inline
           approximation since they don't ship a CC0 SVG. -->
      <span class="flex items-center gap-2 transition-opacity hover:opacity-100" style="color: var(--fg-body); font-size: 14px">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
          <path d="M3 5.5v13a1 1 0 0 0 1.546.838l8.5-5.5a1 1 0 0 0 0-1.676l-8.5-5.5A1 1 0 0 0 3 5.5Z" opacity=".5"/>
          <path d="M11 5.5v13a1 1 0 0 0 1.546.838l8.5-5.5a1 1 0 0 0 0-1.676l-8.5-5.5A1 1 0 0 0 11 5.5Z"/>
        </svg>
        <span class="font-mono text-body">Continue</span>
      </span>
    </div>
  </div>
</section>
</template>
