/**
 * @version 1.0.0
 * @changelog Introduced capability selection panel powering toolsets routing and telemetry.
 * @license MIT; offline-safe with no external dependencies.
 */

export type CapabilityKey =
  | "reasoning_planning"
  | "data_rag"
  | "orchestration"
  | "analysis_modeling"
  | "communication_reporting"
  | "risk_safety_compliance"
  | "quality_evaluation";

export type ConnectorName =
  | "email"
  | "calendar"
  | "make"
  | "notion"
  | "gdrive"
  | "sharepoint"
  | "github";

export interface ConnectorInstance {
  label: string;
  secret_ref: string;
}

export interface ToolsetConnector {
  name: ConnectorName;
  scopes: string[];
  instances?: ConnectorInstance[];
}

export interface GovernanceSettings {
  storage: "kv" | "vector" | "none";
  redaction: ["mask_pii", "never_store_secrets"];
  retention: "default_365" | "episodic_180";
  data_residency: "auto" | "ca" | "us" | "eu";
}

export interface OpsSettings {
  env: "dev" | "staging" | "prod";
  dry_run: boolean;
  latency_slo_ms: number;
  cost_budget_usd: number;
}

export interface ToolsetsPayload {
  capabilities: CapabilityKey[];
  connectors: ToolsetConnector[];
  governance: GovernanceSettings;
  ops: OpsSettings;
}

export type ToolsetsTelemetryEvent = {
  ts: number;
  agent_id?: string;
  step: "toolsets";
  action: string;
  value: unknown;
};

export type CapabilityMetadata = {
  key: CapabilityKey;
  label: string;
  description: string;
  tooltip: string;
  role: string;
  workflows: string[];
};

export interface CapabilitiesPanelOptions {
  initial?: CapabilityKey[] | ToolsetsPayload | null;
  telemetry?: (event: ToolsetsTelemetryEvent) => void;
  onChange?: (capabilities: CapabilityKey[]) => void;
  agentId?: string;
}

const CAPABILITY_LABELS: Record<CapabilityKey, CapabilityMetadata> = Object.freeze({
  reasoning_planning: {
    key: "reasoning_planning",
    label: "Reasoning & Planning",
    description: "Planner and evaluator decomposition",
    tooltip: "Planner routes to goal decomposition",
    role: "Planner",
    workflows: ["goal_decomposition", "risk_projection"],
  },
  data_rag: {
    key: "data_rag",
    label: "Data + RAG",
    description: "Retrieval, RAG and synthesis",
    tooltip: "RAG workflows to knowledge graph",
    role: "Researcher",
    workflows: ["retrieve_context", "synthesize_findings"],
  },
  orchestration: {
    key: "orchestration",
    label: "Workflow Orchestration",
    description: "Task graphs and automations",
    tooltip: "Builder dispatches DefaultFlow",
    role: "Builder",
    workflows: ["construct_task_graph", "dispatch_tools"],
  },
  analysis_modeling: {
    key: "analysis_modeling",
    label: "Analysis & Modeling",
    description: "Financial and scenario modeling",
    tooltip: "Evaluator hooks enable modeling",
    role: "Modeler",
    workflows: ["scenario_model", "sensitivity_check"],
  },
  communication_reporting: {
    key: "communication_reporting",
    label: "Communication & Reporting",
    description: "Briefs, slides, publishing",
    tooltip: "Routes to publishing workflows",
    role: "Communicator",
    workflows: ["draft_brief", "summarize_updates"],
  },
  risk_safety_compliance: {
    key: "risk_safety_compliance",
    label: "Risk & Compliance",
    description: "Policy, refusals, guardrails",
    tooltip: "Routes to policy screening nodes",
    role: "Guardian",
    workflows: ["policy_screen", "issue_flagging"],
  },
  quality_evaluation: {
    key: "quality_evaluation",
    label: "Quality Evaluation",
    description: "Self-checks, regression gates",
    tooltip: "Evaluator regression quality",
    role: "Evaluator",
    workflows: ["critique_iteration", "regression_gate"],
  },
});

export const CAPABILITY_ORDER: CapabilityKey[] = Object.freeze([
  "reasoning_planning",
  "data_rag",
  "orchestration",
  "analysis_modeling",
  "communication_reporting",
  "risk_safety_compliance",
  "quality_evaluation",
]);

function now(): number {
  return Date.now();
}

function sanitizeCapabilityList(values: unknown): CapabilityKey[] {
  if (!Array.isArray(values)) {
    return [];
  }
  const unique = new Set<CapabilityKey>();
  for (const value of values) {
    if (typeof value === "string" && (CAPABILITY_ORDER as readonly string[]).includes(value)) {
      unique.add(value as CapabilityKey);
    }
  }
  return CAPABILITY_ORDER.filter((key) => unique.has(key));
}

export class CapabilitiesPanel {
  private selected: CapabilityKey[];
  private readonly telemetry?: (event: ToolsetsTelemetryEvent) => void;
  private readonly agentId?: string;
  private readonly onChange?: (capabilities: CapabilityKey[]) => void;

  constructor(options: CapabilitiesPanelOptions = {}) {
    const initial = Array.isArray(options.initial)
      ? options.initial
      : options.initial && typeof options.initial === "object"
      ? (options.initial as ToolsetsPayload).capabilities
      : undefined;
    const sanitized = sanitizeCapabilityList(initial ?? []);
    this.selected = sanitized.length ? sanitized : ["reasoning_planning"];
    this.telemetry = options.telemetry;
    this.agentId = options.agentId;
    this.onChange = options.onChange;
    this.emit("toolsets:capability_selected", { capabilities: this.selected });
    this.notifyChange();
  }

  private emit(action: string, value: unknown): void {
    if (!this.telemetry) {
      return;
    }
    const event: ToolsetsTelemetryEvent = {
      ts: now(),
      agent_id: this.agentId,
      step: "toolsets",
      action,
      value,
    };
    this.telemetry(event);
  }

  private notifyChange(): void {
    if (this.onChange) {
      this.onChange(this.getSelectedCapabilities());
    }
  }

  getMetadata(): CapabilityMetadata[] {
    return CAPABILITY_ORDER.map((key) => CAPABILITY_LABELS[key]);
  }

  getSelectedCapabilities(): CapabilityKey[] {
    return [...this.selected];
  }

  hasCapability(key: CapabilityKey): boolean {
    return this.selected.includes(key);
  }

  toggleCapability(key: CapabilityKey): void {
    if (!(CAPABILITY_ORDER as readonly string[]).includes(key)) {
      return;
    }
    if (this.hasCapability(key)) {
      if (this.selected.length === 1) {
        return; // must keep at least one capability
      }
      this.selected = this.selected.filter((item) => item !== key);
    } else {
      this.selected = sanitizeCapabilityList([...this.selected, key]);
    }
    this.emit("toolsets:capability_selected", { key, selected: this.getSelectedCapabilities() });
    this.notifyChange();
  }

  setCapabilities(keys: CapabilityKey[]): void {
    const sanitized = sanitizeCapabilityList(keys);
    if (!sanitized.length) {
      return;
    }
    this.selected = sanitized;
    this.emit("toolsets:capability_selected", { capabilities: this.getSelectedCapabilities() });
    this.notifyChange();
  }

  save(): { valid: boolean; errors?: string[]; capabilities?: CapabilityKey[] } {
    if (!this.selected.length) {
      return { valid: false, errors: ["Select at least one capability."] };
    }
    return { valid: true, capabilities: this.getSelectedCapabilities() };
  }
}

export function createDefaultToolsetsPayload(): ToolsetsPayload {
  return {
    capabilities: ["reasoning_planning"],
    connectors: [],
    governance: {
      storage: "kv",
      redaction: ["mask_pii", "never_store_secrets"],
      retention: "default_365",
      data_residency: "auto",
    },
    ops: {
      env: "staging",
      dry_run: true,
      latency_slo_ms: 1200,
      cost_budget_usd: 5,
    },
  };
}

export function emitToolsetsSaved(
  telemetry: ((event: ToolsetsTelemetryEvent) => void) | undefined,
  agentId: string | undefined,
  payload: ToolsetsPayload,
): void {
  if (!telemetry) {
    return;
  }
  telemetry({ ts: now(), agent_id: agentId, step: "toolsets", action: "toolsets:saved", value: payload });
}
