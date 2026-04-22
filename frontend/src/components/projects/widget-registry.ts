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
    minW: 5, minH: 4,
  },
  health: {
    id: "health",
    title: "Health",
    hint: "Uptime + latency for the live site.",
    icon: "◎",
    component: ProjectHealthCard,
    props: (p) => ({ slug: p.slug }),
    minW: 3, minH: 4,
  },
  focus: {
    id: "focus",
    title: "Current focus",
    hint: "What you're working on · next step · open questions.",
    icon: "◆",
    component: ProjectFocusCard,
    props: (p) => ({ project: p }),
    minW: 4, minH: 4,
  },
  todos: {
    id: "todos",
    title: "Todos",
    hint: "Task list Claude can tick off.",
    icon: "☑",
    component: ProjectTodosCard,
    props: (p) => ({ project: p }),
    minW: 5, minH: 5,
  },
  sessions: {
    id: "sessions",
    title: "Sessions",
    hint: "Coding block history.",
    icon: "◎",
    component: ProjectSessionsCard,
    props: (p) => ({ project: p }),
    minW: 4, minH: 4,
  },
  decisions: {
    id: "decisions",
    title: "Decisions",
    hint: "ADR-lite log.",
    icon: "⟁",
    component: ProjectDecisionsCard,
    props: (p) => ({ project: p }),
    minW: 4, minH: 4,
  },
  launches: {
    id: "launches",
    title: "Launches",
    hint: "Release events.",
    icon: "▲",
    component: ProjectLaunchesCard,
    props: (p) => ({ project: p }),
    minW: 4, minH: 4,
  },
  notes: {
    id: "notes",
    title: "Notes",
    hint: "Markdown scratchpad.",
    icon: "✎",
    component: ProjectNotesCard,
    props: (p) => ({ project: p }),
    minW: 4, minH: 4,
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
    minW: 4, minH: 4,
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
    minW: 5, minH: 4,
  },
  activity: {
    id: "activity",
    title: "Activity timeline",
    hint: "Chronological event feed.",
    icon: "⟐",
    component: ProjectActivityTimeline,
    props: (p) => ({ projectSlug: p.slug }),
    minW: 6, minH: 6,
  },
};

/**
 * Factory layout — what every new project sees before the user customises.
 * Grid is 12 columns. h units are ~ 40px each.
 */
export const DEFAULT_LAYOUT: WidgetLayout[] = [
  // Top row: brief (wide) + health (narrow)
  { i: "brief",          x: 0,  y: 0,  w: 8, h: 5, minW: 5, minH: 4 },
  { i: "health",         x: 8,  y: 0,  w: 4, h: 5, minW: 3, minH: 4 },
  // Current focus: full width
  { i: "focus",          x: 0,  y: 5,  w: 12, h: 4, minW: 4, minH: 4 },
  // Todos: full width (the hero of the work zone)
  { i: "todos",          x: 0,  y: 9,  w: 12, h: 6, minW: 5, minH: 5 },
  // Sessions + decisions
  { i: "sessions",       x: 0,  y: 15, w: 6, h: 5, minW: 4, minH: 4 },
  { i: "decisions",      x: 6,  y: 15, w: 6, h: 5, minW: 4, minH: 4 },
  // Launches + notes
  { i: "launches",       x: 0,  y: 20, w: 6, h: 5, minW: 4, minH: 4 },
  { i: "notes",          x: 6,  y: 20, w: 6, h: 5, minW: 4, minH: 4 },
  // Config row: infra / stack / tags
  { i: "infra",          x: 0,  y: 25, w: 4, h: 4, minW: 3, minH: 3 },
  { i: "stack",          x: 4,  y: 25, w: 4, h: 4, minW: 3, minH: 3 },
  { i: "tags",           x: 8,  y: 25, w: 4, h: 4, minW: 3, minH: 3 },
  // Links + environments
  { i: "links-commands", x: 0,  y: 29, w: 8, h: 5, minW: 4, minH: 4 },
  { i: "environments",   x: 8,  y: 29, w: 4, h: 5, minW: 3, minH: 3 },
  // Secrets full-width
  { i: "secrets",        x: 0,  y: 34, w: 12, h: 5, minW: 5, minH: 4 },
  // Activity timeline at the bottom
  { i: "activity",       x: 0,  y: 39, w: 12, h: 8, minW: 6, minH: 6 },
];

export function widgetById(id: string): WidgetDef | undefined {
  return WIDGETS[id];
}
