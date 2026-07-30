<template>
<!-- ─── Session in action: terminal mockup ───────────────────────────── -->
<section class="relative py-16 md:py-28 px-6 overflow-hidden">
  <div class="max-w-5xl mx-auto relative z-10">
    <div class="text-center mb-12">
      <p class="font-mono text-micro uppercase tracking-caps mb-3" style="color: var(--signal-green)">
        A session, in the real
      </p>
      <h2 class="font-semibold leading-tight"
        style="font-size: clamp(1.6rem, 3vw, 2.4rem); letter-spacing: -0.03em; color: var(--fg-primary)">
        This is what shipping with Vibecell looks like
      </h2>
    </div>

    <!-- Terminal-ish pane -->
    <div
      class="rounded-xl overflow-hidden"
      style="background: rgb(var(--scrim-rgb) / 0.72); border: 1px solid var(--border-default); backdrop-filter: blur(8px); box-shadow: 0 20px 60px rgb(var(--scrim-rgb) / 0.35)"
    >
      <!-- Chrome bar -->
      <div class="flex items-center justify-between px-4 py-2.5 border-b"
        style="border-color: var(--border-subtle); background: rgb(var(--bg-surface-rgb) / 0.4)">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full" style="background: var(--signal-red)"></span>
          <span class="w-2.5 h-2.5 rounded-full" style="background: var(--signal-amber)"></span>
          <span class="w-2.5 h-2.5 rounded-full" style="background: var(--signal-green)"></span>
        </div>
        <span class="font-mono text-nano tracking-widest" style="color: var(--fg-subtle)">
          claude code · vibecell mcp
        </span>
        <span class="font-mono text-nano" style="color: var(--fg-subtle)">⌥⌘K</span>
      </div>

      <!-- Body -->
      <div class="p-6 md:p-8 font-mono text-[12.5px] space-y-4"
        style="line-height: 1.65; color: var(--fg-body)">

        <!-- user message -->
        <div>
          <p class="mb-1" style="color: var(--fg-subtle)">&gt; you</p>
          <p>lass uns ein tool bauen das tiktok clips zu blog posts
            macht. name: <span style="color:var(--signal-green)">clipscribe</span></p>
        </div>

        <!-- tool call 1 -->
        <div class="pl-4 border-l-2" style="border-color: rgb(var(--signal-green-rgb) / 0.3)">
          <p style="color: var(--signal-green)">● vibecell_create_project</p>
          <p class="ml-3" style="color: var(--fg-muted)">
            {<br>
            &nbsp;&nbsp;name: <span style="color:var(--code-string)">"Clipscribe"</span>,<br>
            &nbsp;&nbsp;pitch: <span style="color:var(--code-string)">"TikTok clips → long-form blog posts with AI"</span>,<br>
            &nbsp;&nbsp;stack: [python, fastapi, whisper, vue-3, openai],<br>
            &nbsp;&nbsp;tags: [ai, content-tool, saas]<br>
            }
          </p>
          <p class="mt-2" style="color: var(--signal-green)">
            → https://vibecell.dev/p/clipscribe &nbsp;·&nbsp; pre-filled
            <span style="color:var(--signal-violet)">5 stack items</span>,
            <span style="color:var(--signal-violet)">3 tags</span>,
            active project = clipscribe
          </p>
        </div>

        <!-- assistant response -->
        <div>
          <p class="mb-1" style="color: var(--fg-subtle)">● claude</p>
          <p>
            Created <span style="color: var(--signal-green)">clipscribe</span> ✓
            I&rsquo;ll start with the FastAPI scaffold + a Whisper
            endpoint. Logging 4 todos &hellip;
          </p>
        </div>

        <!-- tool call 2 -->
        <div class="pl-4 border-l-2" style="border-color: rgb(var(--signal-violet-rgb) / 0.3)">
          <p style="color: var(--signal-violet)">● vibecell_todo_batch_add</p>
          <p class="ml-3" style="color: var(--fg-muted)">
            batch: <span style="color:var(--code-string)">"clipscribe-v0"</span>,
            titles: [
              <span style="color:var(--code-string)">"scaffold fastapi"</span>,
              <span style="color:var(--code-string)">"whisper transcribe endpoint"</span>,
              <span style="color:var(--code-string)">"blog-post generator"</span>,
              <span style="color:var(--code-string)">"vue frontend"</span>
            ]
          </p>
          <p class="mt-2" style="color: var(--signal-violet)">→ 4 todos visible on dashboard, Claude ticks as it ships</p>
        </div>

        <!-- cursor tick animation hint -->
        <div class="flex items-center gap-2 pt-2" style="color: var(--fg-subtle)">
          <span>&gt; _</span>
          <span class="inline-block w-1.5 h-3.5 animate-pulse" style="background: var(--signal-green)"></span>
          <span class="ml-3 text-micro">live &middot; 0 manual clicks</span>
        </div>
      </div>
    </div>

    <!-- Closer line -->
    <p class="text-center mt-10 max-w-xl mx-auto leading-relaxed"
      style="font-size: 13px; color: var(--fg-muted)">
      No switching to the dashboard, no forms, no copy-paste.
      <span style="color:var(--fg-body)">The project exists before the conversation even ends.</span>
    </p>
  </div>
</section>
</template>
