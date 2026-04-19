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
