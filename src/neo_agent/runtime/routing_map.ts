/**
 * @version 1.0.0
 * @changelog Introduced trait-aware routing knobs for planner, builder, and evaluator flows.
 * @license MIT; built for offline Project NEO runtime orchestration.
 */

import type { Preferences, PreferenceKnobs } from "../ui/preferences_panel";
import { derivePreferenceKnobs } from "../ui/preferences_panel";
import type { Traits } from "../ui/traits_panel";
import type { ToolsetsPayload, ToolsetConnector } from "../ui/capabilities_panel";
import { DEFAULT_CONNECTOR_SCOPES } from "../ui/connectors_panel";

export type PlannerKnobs = {
  plan_depth: number;
  parallel_branches: number;
};

export type BuilderKnobs = {
  draft_verbosity: "concise" | "balanced" | "detailed";
  strictness: "lenient" | "balanced" | "strict";
};

export type EvaluatorKnobs = {
  eval_style: "direct" | "supportive";
  alt_paths: boolean;
};

export type TraitRoutingKnobs = PlannerKnobs & BuilderKnobs & EvaluatorKnobs;

export type PreferencesRoutingKnobs = PreferenceKnobs;

export type CombinedRoutingKnobs = TraitRoutingKnobs & PreferencesRoutingKnobs;

export type ToolsetRoutes = {
  roles: string[];
  workflows: string[];
  connectors: string[];
  approvals: string[];
  warnings: string[];
};

export const CAPABILITY_ROUTES: Record<string, { role: string; workflows: string[] }> = Object.freeze({
  reasoning_planning: { role: "Planner", workflows: ["goal_decomposition", "risk_projection"] },
  data_rag: { role: "Researcher", workflows: ["retrieve_context", "synthesize_findings"] },
  orchestration: { role: "Builder", workflows: ["construct_task_graph", "dispatch_tools"] },
  analysis_modeling: { role: "Modeler", workflows: ["scenario_model", "sensitivity_check"] },
  communication_reporting: { role: "Communicator", workflows: ["draft_brief", "summarize_updates"] },
  risk_safety_compliance: { role: "Guardian", workflows: ["policy_screen", "issue_flagging"] },
  quality_evaluation: { role: "Evaluator", workflows: ["critique_iteration", "regression_gate"] },
});

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

function scaled(value: number, min: number, max: number): number {
  const bounded = clamp(value, 0, 100);
  const span = max - min;
  return Math.round(min + (span * bounded) / 100);
}

export function applyTraitsKnobs(traits: Traits): TraitRoutingKnobs {
  const strategic = traits.strategic ?? 50;
  const proactive = traits.proactive ?? 50;
  const detail = traits.detail_oriented ?? 50;
  const efficient = traits.efficient ?? 50;
  const empathetic = traits.empathetic ?? 50;
  const experimental = traits.experimental ?? 50;

  const plan_depth = clamp(scaled((strategic + proactive) / 2, 3, 7), 3, 7);
  const parallel_branches = clamp(Math.floor((proactive + experimental) / 50), 1, 4);

  const detailWeight = (detail + strategic) / 2;
  let draft_verbosity: BuilderKnobs["draft_verbosity"] = "balanced";
  if (detailWeight >= 70) {
    draft_verbosity = "detailed";
  } else if (efficient <= 40) {
    draft_verbosity = "concise";
  }

  let strictness: BuilderKnobs["strictness"] = "balanced";
  if (detail >= 70 && efficient >= 70) {
    strictness = "strict";
  } else if (efficient <= 40) {
    strictness = "lenient";
  }

  const eval_style: EvaluatorKnobs["eval_style"] = empathetic >= 65 ? "supportive" : "direct";
  const alt_paths = experimental >= 60;

  return {
    plan_depth,
    parallel_branches,
    draft_verbosity,
    strictness,
    eval_style,
    alt_paths,
  };
}

function sanitizePreferencesState(prefs: Preferences): {
  autonomy: number;
  confidence: number;
  collaboration: number;
  comm_style: Preferences["comm_style"];
  collab_mode: Preferences["collab_mode"];
} {
  const clampToRange = (value: number): number => {
    if (!Number.isFinite(value)) {
      return 0;
    }
    const bounded = Math.min(100, Math.max(0, value));
    return Math.round(bounded / 5) * 5;
  };

  return {
    autonomy: clampToRange(prefs.autonomy ?? 0),
    confidence: clampToRange(prefs.confidence ?? 0),
    collaboration: clampToRange(prefs.collaboration ?? 0),
    comm_style: prefs.comm_style ?? "formal",
    collab_mode: prefs.collab_mode ?? "solo",
  };
}

export function applyPreferencesKnobs(prefs: Preferences): PreferencesRoutingKnobs {
  const state = sanitizePreferencesState(prefs);
  const knobs = derivePreferenceKnobs(state);
  if (state.autonomy <= 30 && knobs.confirmation_gate === "none") {
    knobs.confirmation_gate = "light";
  }
  return knobs;
}

const DEFAULT_TRAITS: Traits = Object.freeze({
  detail_oriented: 50,
  collaborative: 50,
  proactive: 50,
  strategic: 50,
  empathetic: 50,
  experimental: 50,
  efficient: 50,
});

const DEFAULT_PREFERENCES: Preferences = Object.freeze({
  autonomy: 50,
  confidence: 50,
  collaboration: 50,
  comm_style: "formal",
  collab_mode: "solo",
  prefs_knobs: derivePreferenceKnobs({
    autonomy: 50,
    confidence: 50,
    collaboration: 50,
    comm_style: "formal",
    collab_mode: "solo",
  }),
  provenance: "manual",
  version: "1.0",
});

const BASE_TRAIT_KNOBS = applyTraitsKnobs(DEFAULT_TRAITS);
const BASE_PREF_KNOBS = applyPreferencesKnobs(DEFAULT_PREFERENCES);

export function mergeRoutingKnobs(input: {
  traits?: TraitRoutingKnobs | null;
  preferences?: PreferencesRoutingKnobs | null;
}): CombinedRoutingKnobs {
  return {
    ...BASE_TRAIT_KNOBS,
    ...BASE_PREF_KNOBS,
    ...(input.traits ?? {}),
    ...(input.preferences ?? {}),
  };
}

function unique(values: Iterable<string>): string[] {
  return Array.from(new Set(values));
}

function connectorRequiresApproval(connector: ToolsetConnector): boolean {
  const defaults = new Set(DEFAULT_CONNECTOR_SCOPES[connector.name] ?? []);
  return connector.scopes.some((scope) => !defaults.has(scope));
}

function buildOrchestrationWarning(capabilities: string[], connectors: ToolsetConnector[]): string | null {
  if (!capabilities.includes("orchestration")) {
    return null;
  }
  for (const connector of connectors) {
    if (connector.scopes.length) {
      return null;
    }
  }
  return "Orchestration enabled without connector scopes.";
}

export function applyToolsetsRouting(toolsets: ToolsetsPayload): {
  routes: ToolsetRoutes;
  approvals_required: boolean;
} {
  const roles: string[] = [];
  const workflows: string[] = [];
  for (const capability of toolsets.capabilities) {
    const mapping = CAPABILITY_ROUTES[capability];
    if (mapping) {
      roles.push(mapping.role);
      workflows.push(...mapping.workflows);
    }
  }

  const connectors = toolsets.connectors ?? [];
  const connectorNames = connectors.map((connector) => connector.name);
  const approvals: string[] = [];
  let approvalsRequired = false;
  for (const connector of connectors) {
    if (connectorRequiresApproval(connector)) {
      approvalsRequired = true;
      approvals.push(connector.name);
    }
  }
  if (toolsets.ops?.env === "prod") {
    approvalsRequired = true;
    approvals.push("ops:prod");
  }

  const warning = buildOrchestrationWarning(toolsets.capabilities, connectors);

  const routes: ToolsetRoutes = {
    roles: unique(roles),
    workflows: unique(workflows),
    connectors: unique(connectorNames),
    approvals: unique(approvals),
    warnings: warning ? [warning] : [],
  };

  return { routes, approvals_required: approvalsRequired };
}
