/**
 * @version 1.0.0
 * @changelog Added governance and operations panel enforcing retention defaults and prod guards.
 * @license MIT; offline-safe and telemetry-enabled.
 */

import type {
  GovernanceSettings,
  OpsSettings,
  ToolsetsPayload,
  ToolsetsTelemetryEvent,
} from "./capabilities_panel";

export interface GovernanceOpsPanelOptions {
  initial?: Partial<ToolsetsPayload> | null;
  telemetry?: (event: ToolsetsTelemetryEvent) => void;
  onChange?: (payload: { governance: GovernanceSettings; ops: OpsSettings }) => void;
  agentId?: string;
}

const STORAGE_OPTIONS: GovernanceSettings["storage"][] = ["kv", "vector", "none"];
const RETENTION_OPTIONS: GovernanceSettings["retention"][] = ["default_365", "episodic_180"];
const RESIDENCY_OPTIONS: GovernanceSettings["data_residency"][] = ["auto", "ca", "us", "eu"];
const ENV_OPTIONS: OpsSettings["env"][] = ["dev", "staging", "prod"];
const REDACTION_FLAGS: GovernanceSettings["redaction"] = [
  "mask_pii",
  "never_store_secrets",
];

function now(): number {
  return Date.now();
}

function clampNumber(value: unknown, fallback: number): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }
  return value;
}

export class GovernanceOpsPanel {
  private governance: GovernanceSettings;
  private ops: OpsSettings;
  private readonly telemetry?: (event: ToolsetsTelemetryEvent) => void;
  private readonly agentId?: string;
  private readonly onChange?: (payload: { governance: GovernanceSettings; ops: OpsSettings }) => void;

  constructor(options: GovernanceOpsPanelOptions = {}) {
    this.telemetry = options.telemetry;
    this.agentId = options.agentId;
    this.onChange = options.onChange;

    const initialGov = options.initial && typeof options.initial === "object" ? options.initial.governance : null;
    const initialOps = options.initial && typeof options.initial === "object" ? options.initial.ops : null;

    const storageCandidate =
      initialGov && typeof initialGov.storage === "string" ? (initialGov.storage as GovernanceSettings["storage"]) : "kv";
    const retentionCandidate =
      initialGov && typeof initialGov.retention === "string"
        ? (initialGov.retention as GovernanceSettings["retention"])
        : "default_365";
    const residencyCandidate =
      initialGov && typeof initialGov.data_residency === "string"
        ? (initialGov.data_residency as GovernanceSettings["data_residency"])
        : "auto";

    this.governance = {
      storage: STORAGE_OPTIONS.includes(storageCandidate) ? storageCandidate : "kv",
      redaction: REDACTION_FLAGS,
      retention: RETENTION_OPTIONS.includes(retentionCandidate) ? retentionCandidate : "default_365",
      data_residency: RESIDENCY_OPTIONS.includes(residencyCandidate) ? residencyCandidate : "auto",
    };

    const defaultOps: OpsSettings = {
      env: "staging",
      dry_run: true,
      latency_slo_ms: 1200,
      cost_budget_usd: 5,
    };

    const envCandidate =
      initialOps && typeof initialOps.env === "string" ? (initialOps.env as OpsSettings["env"]) : defaultOps.env;

    this.ops = {
      env: ENV_OPTIONS.includes(envCandidate) ? envCandidate : defaultOps.env,
      dry_run: typeof initialOps?.dry_run === "boolean" ? initialOps!.dry_run : defaultOps.dry_run,
      latency_slo_ms: Math.max(0, clampNumber(initialOps?.latency_slo_ms, defaultOps.latency_slo_ms)),
      cost_budget_usd: Math.max(0, clampNumber(initialOps?.cost_budget_usd, defaultOps.cost_budget_usd)),
    };

    this.emit("toolsets:governance_hint_set", { governance: this.governance });
    this.emit("toolsets:ops_changed", { ops: this.ops });
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
    if (!this.onChange) {
      return;
    }
    this.onChange({
      governance: this.getGovernance(),
      ops: this.getOps(),
    });
  }

  getGovernance(): GovernanceSettings {
    return {
      storage: this.governance.storage,
      redaction: [...REDACTION_FLAGS],
      retention: this.governance.retention,
      data_residency: this.governance.data_residency,
    };
  }

  getOps(): OpsSettings {
    return { ...this.ops };
  }

  setStorage(storage: GovernanceSettings["storage"]): void {
    if (!STORAGE_OPTIONS.includes(storage)) {
      return;
    }
    this.governance.storage = storage;
    this.emit("toolsets:governance_hint_set", { storage });
    this.notifyChange();
  }

  setRetention(retention: GovernanceSettings["retention"]): void {
    if (!RETENTION_OPTIONS.includes(retention)) {
      return;
    }
    this.governance.retention = retention;
    this.emit("toolsets:governance_hint_set", { retention });
    this.notifyChange();
  }

  setResidency(residency: GovernanceSettings["data_residency"]): void {
    if (!RESIDENCY_OPTIONS.includes(residency)) {
      return;
    }
    this.governance.data_residency = residency;
    this.emit("toolsets:governance_hint_set", { residency });
    this.notifyChange();
  }

  getRedactionFlags(): GovernanceSettings["redaction"] {
    return [...REDACTION_FLAGS];
  }

  setEnvironment(env: OpsSettings["env"]): void {
    if (!ENV_OPTIONS.includes(env)) {
      return;
    }
    this.ops.env = env;
    if (env === "prod" && this.ops.dry_run) {
      this.ops.dry_run = false; // enforce dry-run off in prod
    }
    this.emit("toolsets:ops_changed", { env: this.ops.env });
    this.notifyChange();
  }

  setDryRun(enabled: boolean): void {
    this.ops.dry_run = Boolean(enabled);
    if (this.ops.env === "prod" && this.ops.dry_run) {
      this.ops.dry_run = false;
    }
    this.emit("toolsets:ops_changed", { dry_run: this.ops.dry_run });
    this.notifyChange();
  }

  setLatencySlo(value: number): void {
    this.ops.latency_slo_ms = Math.max(0, clampNumber(value, this.ops.latency_slo_ms));
    this.emit("toolsets:ops_changed", { latency_slo_ms: this.ops.latency_slo_ms });
    this.notifyChange();
  }

  setCostBudget(value: number): void {
    this.ops.cost_budget_usd = Math.max(0, clampNumber(value, this.ops.cost_budget_usd));
    this.emit("toolsets:ops_changed", { cost_budget_usd: this.ops.cost_budget_usd });
    this.notifyChange();
  }

  getOpsBanner(): string | null {
    if (this.ops.env === "prod") {
      return "Prod ops; CAIO approval may be required.";
    }
    return null;
  }

  validate(): { valid: boolean; errors: string[] } {
    const errors: string[] = [];
    if (!STORAGE_OPTIONS.includes(this.governance.storage)) {
      errors.push("Storage selection is invalid.");
    }
    if (!RETENTION_OPTIONS.includes(this.governance.retention)) {
      errors.push("Retention selection is invalid.");
    }
    if (!RESIDENCY_OPTIONS.includes(this.governance.data_residency)) {
      errors.push("Data residency selection is invalid.");
    }
    if (!ENV_OPTIONS.includes(this.ops.env)) {
      errors.push("Ops environment is invalid.");
    }
    if (this.ops.latency_slo_ms < 0) {
      errors.push("Latency SLO must be zero or greater.");
    }
    if (this.ops.cost_budget_usd < 0) {
      errors.push("Cost budget must be zero or greater.");
    }
    if (this.ops.env === "prod" && this.ops.dry_run) {
      errors.push("Prod environment requires dry-run disabled.");
    }
    return { valid: errors.length === 0, errors };
  }

  save(): {
    valid: boolean;
    errors?: string[];
    governance?: GovernanceSettings;
    ops?: OpsSettings;
    approvalsRequired: boolean;
  } {
    const { valid, errors } = this.validate();
    if (!valid) {
      return { valid: false, errors, approvalsRequired: this.ops.env === "prod" };
    }
    return {
      valid: true,
      governance: this.getGovernance(),
      ops: this.getOps(),
      approvalsRequired: this.ops.env === "prod",
    };
  }
}

export function createGovernanceDefaults(): { governance: GovernanceSettings; ops: OpsSettings } {
  const panel = new GovernanceOpsPanel();
  return { governance: panel.getGovernance(), ops: panel.getOps() };
}
