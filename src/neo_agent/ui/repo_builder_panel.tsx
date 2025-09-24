/**
 * @version 1.0.0
 * @changelog Introduced repository builder panel with dry-run preview, telemetry, and packaging flow.
 * @license MIT; operates offline with local API hooks only.
 */

export type RepoBuildOptions = {
  include_examples: boolean;
  git_init: boolean;
  zip: boolean;
  overwrite: "safe" | "force" | "abort";
};

export type RepoBuildPlanEntry = {
  path: string;
  action: "create" | "update" | "skip";
  sha256_after: string;
};

export type RepoBuildPlan = {
  files: RepoBuildPlanEntry[];
  inputs_sha256: string;
};

export type RepoBuildResult = {
  status: "ok" | "error";
  repo_path?: string | null;
  zip_path?: string | null;
  manifest?: Record<string, unknown>;
  timings_ms?: Record<string, number>;
  issues?: Array<Record<string, unknown>>;
};

export type RepoBuilderTelemetry = {
  ts: number;
  actor: "intake" | string;
  step: "repo";
  action: string;
  value: unknown;
};

export type RepoBuilderApi = {
  validateProfile(profile: unknown): Promise<{ status: "ok" | "error"; issues: unknown[] }>;
  dryRun(payload: { profile: unknown; options: RepoBuildOptions }): Promise<{ status: "ok" | "error"; plan?: RepoBuildPlan; issues?: unknown[] }>;
  build(payload: { profile: unknown; options: RepoBuildOptions }): Promise<RepoBuildResult>;
};

export type RepoBuilderPanelOptions = {
  api: RepoBuilderApi;
  telemetry?: (event: RepoBuilderTelemetry) => void;
  agentId?: string;
};

type ProgressStage = "idle" | "validating" | "dry_run" | "render" | "package" | "done" | "error";

type InternalState = {
  profile: unknown;
  profileValid: boolean;
  lastIssues: unknown[];
  plan: RepoBuildPlan | null;
  buildResult: RepoBuildResult | null;
  progress: ProgressStage;
};

function now(): number {
  return Date.now();
}

export class RepoBuilderPanel {
  private readonly api: RepoBuilderApi;
  private readonly telemetry?: (event: RepoBuilderTelemetry) => void;
  private readonly agentId?: string;
  private state: InternalState;

  constructor(options: RepoBuilderPanelOptions) {
    this.api = options.api;
    this.telemetry = options.telemetry;
    this.agentId = options.agentId;
    this.state = {
      profile: null,
      profileValid: false,
      lastIssues: [],
      plan: null,
      buildResult: null,
      progress: "idle",
    };
  }

  private emit(action: string, value: unknown): void {
    if (!this.telemetry) return;
    const enriched =
      value && typeof value === "object"
        ? { ...(value as Record<string, unknown>), agent_id: this.agentId }
        : { value, agent_id: this.agentId };
    this.telemetry({
      ts: now(),
      actor: "intake",
      step: "repo",
      action,
      value: enriched,
    });
  }

  setProfile(profile: unknown): void {
    this.state.profile = profile;
    this.state.profileValid = false;
    this.state.plan = null;
    this.state.buildResult = null;
    this.state.lastIssues = [];
    this.state.progress = "idle";
  }

  async validate(): Promise<boolean> {
    if (!this.state.profile) {
      this.state.profileValid = false;
      return false;
    }
    this.state.progress = "validating";
    this.emit("repo:validate", { stage: "start" });
    const response = await this.api.validateProfile(this.state.profile);
    const ok = response.status === "ok";
    this.state.profileValid = ok;
    this.state.lastIssues = ok ? [] : response.issues;
    this.state.progress = ok ? "idle" : "error";
    this.emit("repo:validate", { stage: "end", issues: response.issues ?? [] });
    return ok;
  }

  isGenerateEnabled(): boolean {
    return this.state.profileValid;
  }

  getIssues(): unknown[] {
    return this.state.lastIssues;
  }

  getPlan(): RepoBuildPlan | null {
    return this.state.plan;
  }

  getResult(): RepoBuildResult | null {
    return this.state.buildResult;
  }

  getProgress(): ProgressStage {
    return this.state.progress;
  }

  async dryRun(options: RepoBuildOptions): Promise<RepoBuildPlan | null> {
    if (!this.state.profileValid || !this.state.profile) {
      return null;
    }
    this.state.progress = "dry_run";
    this.emit("repo:render", { stage: "dry_run", options });
    const response = await this.api.dryRun({ profile: this.state.profile, options });
    if (response.status === "ok" && response.plan) {
      this.state.plan = response.plan;
      this.state.progress = "idle";
      this.emit("repo:render", { stage: "dry_run_complete", files: response.plan.files.length });
      return response.plan;
    }
    this.state.plan = null;
    this.state.progress = "error";
    this.state.lastIssues = response.issues ?? [];
    this.emit("repo:error", { stage: "dry_run", issues: response.issues ?? [] });
    return null;
  }

  async build(options: RepoBuildOptions): Promise<RepoBuildResult> {
    if (!this.state.profileValid || !this.state.profile) {
      return { status: "error", issues: [{ message: "Profile not validated" }] };
    }
    this.state.progress = "render";
    this.emit("repo:render", { stage: "build", options });
    const result = await this.api.build({ profile: this.state.profile, options });
    if (result.status === "ok") {
      this.state.progress = "package";
      this.emit("repo:package", { zip_path: result.zip_path, repo_path: result.repo_path });
      this.state.buildResult = result;
      this.state.progress = "done";
      this.emit("repo:done", { manifest_sha: result.manifest?.manifest_sha, inputs: result.manifest?.inputs_sha256 });
      return result;
    }
    this.state.progress = "error";
    this.state.buildResult = result;
    this.emit("repo:error", { stage: "build", issues: result.issues ?? [] });
    return result;
  }

  reset(): void {
    this.state.progress = "idle";
    this.state.plan = null;
    this.state.buildResult = null;
    this.state.lastIssues = [];
    this.emit("repo:reset", {});
  }
}
