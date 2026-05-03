/**
 * Registry of every card type that can appear on the project dashboard.
 *
 * Adding a new card:
 *   1. Write the card component (must accept `project` OR `slug` prop).
 *   2. Add a WidgetDef entry below.
 *   3. If you want it shown by default, add it to DEFAULT_LAYOUT.
 *
 * Existing layouts in localStorage merge with DEFAULT_LAYOUT on hydrate, so
 * a newly-added widget automatically appears at the bottom of users' pages
 * instead of silently going missing.
 */
import type { Component } from "vue";

import ProjectBriefCard from "@/components/projects/ProjectBriefCard.vue";
import ProjectDecisionsCard from "@/components/projects/ProjectDecisionsCard.vue";
import ProjectEnvironmentsCard from "@/components/projects/ProjectEnvironmentsCard.vue";
import ProjectFocusCard from "@/components/projects/ProjectFocusCard.vue";
import ProjectHealthCard from "@/components/projects/ProjectHealthCard.vue";
import ProjectInfraCard from "@/components/projects/ProjectInfraCard.vue";
import ProjectLaunchesCard from "@/components/projects/ProjectLaunchesCard.vue";
import ProjectLinksCommands from "@/components/projects/ProjectLinksCommands.vue";
import ProjectNotesCard from "@/components/projects/ProjectNotesCard.vue";
import ProjectPrimerCard from "@/components/projects/ProjectPrimerCard.vue";
import ProjectSecretsCard from "@/components/projects/ProjectSecretsCard.vue";
import ProjectSessionsCard from "@/components/projects/ProjectSessionsCard.vue";
import ProjectStackEditor from "@/components/projects/ProjectStackEditor.vue";
import ProjectTagsEditor from "@/components/projects/ProjectTagsEditor.vue";
import ProjectTodosCard from "@/components/projects/ProjectTodosCard.vue";
import ProjectActivityTimeline from "@/components/projects/ProjectActivityTimeline.vue";

import type { WidgetLayout } from "@/stores/dashboard-layout";

export type PropBuilder = (project: any) => Record<string, unknown>;

export interface WidgetDef {
  id: string;
  title: string;
  /** Short hint shown in the "add widget" menu. */
  hint: string;
  component: Component;
  props: PropBuilder;
  /** Emoji/glyph for the add-widget menu. */
  icon: string;
  /** Minimum grid size. Grid is 12 columns. */
  minW: number;
  minH: number;
}

export const WIDGETS: Record<string, WidgetDef> = {
  brief: {
    id: "brief",
    title: "Morning brief (AI)",
    hint: "Funny catch-up from Claude using your key.",
    icon: "✨",
    component: ProjectBriefCard,
    props: (p) => ({ slug: p.slug }),
    minW: 3, minH: 3,
  },
  primer: {
    id: "primer",
    title: "Primer",
    hint: "Long-form README aimed at AIs joining cold. Fetched via vibecell_primer.",
    icon: "▤",
    component: ProjectPrimerCard,
    props: (p) => ({ project: p }),
    minW: 4, minH: 4,
  },
  health: {
    id: "health",
    title: "Health",
    hint: "Uptime + latency for the live site.",
    icon: "◎",
    component: ProjectHealthCard,
    props: (p) => ({ slug: p.slug }),
    minW: 3, minH: 3,
  },
  focus: {
    id: "focus",
    title: "Current focus",
    hint: "What you're working on · next step · open questions.",
    icon: "◆",
    component: ProjectFocusCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  todos: {
    id: "todos",
    title: "Todos",
    hint: "Task list Claude can tick off.",
    icon: "☑",
    component: ProjectTodosCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  sessions: {
    id: "sessions",
    title: "Sessions",
    hint: "Coding block history.",
    icon: "◎",
    component: ProjectSessionsCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  decisions: {
    id: "decisions",
    title: "Decisions",
    hint: "ADR-lite log.",
    icon: "⟁",
    component: ProjectDecisionsCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  launches: {
    id: "launches",
    title: "Launches",
    hint: "Release events.",
    icon: "▲",
    component: ProjectLaunchesCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  notes: {
    id: "notes",
    title: "Notes",
    hint: "Markdown scratchpad.",
    icon: "✎",
    component: ProjectNotesCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  infra: {
    id: "infra",
    title: "Infra",
    hint: "Hosting, DNS, DB details.",
    icon: "◇",
    component: ProjectInfraCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  stack: {
    id: "stack",
    title: "Stack",
    hint: "Tech stack tags.",
    icon: "≡",
    component: ProjectStackEditor,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  tags: {
    id: "tags",
    title: "Tags",
    hint: "Taxonomy tags.",
    icon: "#",
    component: ProjectTagsEditor,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  "links-commands": {
    id: "links-commands",
    title: "Links + commands",
    hint: "External URLs + shell recipes.",
    icon: "↗",
    component: ProjectLinksCommands,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  environments: {
    id: "environments",
    title: "Environments",
    hint: "Local / staging / prod URLs.",
    icon: "⌁",
    component: ProjectEnvironmentsCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  secrets: {
    id: "secrets",
    title: "Secrets",
    hint: "API keys + references. Claude-readable.",
    icon: "🔐",
    component: ProjectSecretsCard,
    props: (p) => ({ project: p }),
    minW: 3, minH: 3,
  },
  activity: {
    id: "activity",
    title: "Activity timeline",
    hint: "Chronological event feed.",
    icon: "⟐",
    component: ProjectActivityTimeline,
    props: (p) => ({ projectSlug: p.slug }),
    minW: 3, minH: 3,
  },
};

/**
 * Factory layout — what every new project sees before the user customises.
 * Grid is 12 columns. h units are ~ 40px each (16px gutter between rows).
 *
 * Design goals (set 2026-04-26):
 *   1. Zero visible gaps for a freshly-created project. Empty cards
 *      ("0 ships · 0 launches", "no infra configured") get small h so
 *      they don't reserve 250px of grey real-estate.
 *   2. Above-the-fold: brief, health, focus, todos. The first
 *      thing a new user sees should be CTA-shaped, not "no data".
 *   3. Metadata cluster (stack, tags, infra) sits right under work zone
 *      as a single 3-card row — looks intentional whether populated or
 *      empty.
 *   4. Row heights chosen so a typical empty card hugs its placeholder
 *      ("Empty" / "no X recorded") and a typical populated card has
 *      breathing room, but neither over-reserves.
 */
export const DEFAULT_LAYOUT: WidgetLayout[] = [
  // Hero row — project identity + health badges
  { i: "brief",          x: 0,  y: 0,  w: 8, h: 4, minW: 5, minH: 3 },
  { i: "health",         x: 8,  y: 0,  w: 4, h: 4, minW: 3, minH: 3 },
  // Daily-driver row — what's the user supposed to do next
  { i: "focus",          x: 0,  y: 4,  w: 12, h: 3, minW: 4, minH: 3 },
  // Primer — full-width long-form README aimed at AIs. Sits high in the
  // layout because writing it once unlocks instant onboarding for every
  // future session via the vibecell_primer MCP tool.
  { i: "primer",         x: 0,  y: 7,  w: 12, h: 5, minW: 6, minH: 4 },
  // Work zone — todos always render full-bleed
  { i: "todos",          x: 0,  y: 12, w: 12, h: 5, minW: 5, minH: 4 },
  // Project metadata triplet — always 3 cards in one row, fills cleanly
  { i: "stack",          x: 0,  y: 17, w: 4, h: 3, minW: 3, minH: 3 },
  { i: "tags",           x: 4,  y: 17, w: 4, h: 3, minW: 3, minH: 3 },
  { i: "infra",          x: 8,  y: 17, w: 4, h: 3, minW: 3, minH: 3 },
  // Recent activity pair
  { i: "sessions",       x: 0,  y: 20, w: 6, h: 4, minW: 4, minH: 3 },
  { i: "decisions",      x: 6,  y: 20, w: 6, h: 4, minW: 4, minH: 3 },
  // Operational links + envs
  { i: "links-commands", x: 0,  y: 24, w: 8, h: 4, minW: 4, minH: 3 },
  { i: "environments",   x: 8,  y: 24, w: 4, h: 4, minW: 3, minH: 3 },
  // Notes + launches paired so empty-launch doesn't dominate
  { i: "notes",          x: 0,  y: 28, w: 6, h: 4, minW: 4, minH: 3 },
  { i: "launches",       x: 6,  y: 28, w: 6, h: 4, minW: 4, minH: 3 },
  // Secrets full-width — visually dense once populated, h=4 keeps it
  // under-the-fold for empty case
  { i: "secrets",        x: 0,  y: 32, w: 12, h: 4, minW: 5, minH: 3 },
  // Activity timeline closes out — full width, taller because it's the
  // narrative of the project
  { i: "activity",       x: 0,  y: 36, w: 12, h: 6, minW: 6, minH: 5 },
];

export function widgetById(id: string): WidgetDef | undefined {
  return WIDGETS[id];
}
