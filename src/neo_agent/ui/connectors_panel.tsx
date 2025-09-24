/**
 * @version 1.0.0
 * @changelog Added connectors and scopes panel with approval banners and telemetry.
 * @license MIT; offline registry mirrors bundled JSON packs.
 */

import type {
  CapabilityKey,
  ConnectorInstance,
  ConnectorName,
  ToolsetConnector,
  ToolsetsPayload,
  ToolsetsTelemetryEvent,
} from "./capabilities_panel";

export interface ConnectorDefinition {
  name: ConnectorName;
  label: string;
  description: string;
  defaultScopes: readonly string[];
  optionalScopes: readonly string[];
  allowInstances?: boolean;
}

export const CONNECTOR_CATALOG: readonly ConnectorDefinition[] = Object.freeze([
  {
    name: "email",
    label: "Enterprise Email",
    description: "Read and draft internal mail via vaulted identity.",
    defaultScopes: ["read/*", "send:internal"],
    optionalScopes: ["send:external"],
    allowInstances: true,
  },
  {
    name: "calendar",
    label: "Calendar",
    description: "Access scheduling and hold placement.",
    defaultScopes: ["read/*", "write:holds"],
    optionalScopes: ["write:events"],
  },
  {
    name: "make",
    label: "Make.com",
    description: "Trigger automation scenarios.",
    defaultScopes: ["run:scenario"],
    optionalScopes: ["manage:scenario"],
  },
  {
    name: "notion",
    label: "Notion",
    description: "Read databases and update task boards.",
    defaultScopes: ["read:db/*", "write:tasks"],
    optionalScopes: ["write:pages"],
  },
  {
    name: "gdrive",
    label: "Google Drive",
    description: "Read folders and publish reports.",
    defaultScopes: ["read:folders/*", "write:reports"],
    optionalScopes: ["write:any"],
  },
  {
    name: "sharepoint",
    label: "SharePoint",
    description: "Access policies and deliverables.",
    defaultScopes: ["read:policies/*", "write:reports"],
    optionalScopes: ["write:libraries"],
  },
  {
    name: "github",
    label: "GitHub",
    description: "Read and write repositories for automation hooks.",
    defaultScopes: ["repo:read", "repo:write"],
    optionalScopes: ["repo:admin"],
  },
]);

export const DEFAULT_CONNECTOR_SCOPES: Record<ConnectorName, readonly string[]> = CONNECTOR_CATALOG.reduce(
  (acc, connector) => ({ ...acc, [connector.name]: connector.defaultScopes }),
  {} as Record<ConnectorName, readonly string[]>,
);

export interface ConnectorsPanelOptions {
  initial?: Partial<ToolsetsPayload> | ToolsetConnector[] | null;
  telemetry?: (event: ToolsetsTelemetryEvent) => void;
  onChange?: (connectors: ToolsetConnector[], approvalsRequired: boolean) => void;
  agentId?: string;
}

type ConnectorState = {
  scopes: Set<string>;
  instances: ConnectorInstance[];
};

function now(): number {
  return Date.now();
}

function sanitizeInstance(instance: ConnectorInstance): ConnectorInstance {
  const label = instance.label.trim();
  const secret = instance.secret_ref.trim();
  if (!label) {
    throw new Error("Instance label is required.");
  }
  if (!secret.startsWith("vault://")) {
    throw new Error("secret_ref must reference a vault path.");
  }
  return { label, secret_ref: secret };
}

function sortScopes(scopes: Iterable<string>): string[] {
  return Array.from(new Set(scopes)).sort();
}

function sortConnectors(connectors: Iterable<ToolsetConnector>): ToolsetConnector[] {
  return Array.from(connectors).sort((a, b) => a.name.localeCompare(b.name));
}

export class ConnectorsPanel {
  private readonly telemetry?: (event: ToolsetsTelemetryEvent) => void;
  private readonly agentId?: string;
  private readonly onChange?: (connectors: ToolsetConnector[], approvalsRequired: boolean) => void;
  private readonly registry = new Map<ConnectorName, ConnectorDefinition>();
  private state: Map<ConnectorName, ConnectorState> = new Map();

  constructor(options: ConnectorsPanelOptions = {}) {
    for (const connector of CONNECTOR_CATALOG) {
      this.registry.set(connector.name, connector);
    }
    this.telemetry = options.telemetry;
    this.agentId = options.agentId;
    this.onChange = options.onChange;

    const initial = Array.isArray(options.initial)
      ? options.initial
      : options.initial && typeof options.initial === "object"
      ? (options.initial as ToolsetsPayload).connectors
      : [];

    for (const connector of initial ?? []) {
      try {
        this.applyInitialConnector(connector);
      } catch {
        // ignore invalid legacy entries
      }
    }
    this.emit("toolsets:connector_scope_requested", { connectors: this.getConnectors() });
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
    this.onChange(this.getConnectors(), this.requiresApproval());
  }

  private ensureState(name: ConnectorName): ConnectorState {
    const connector = this.registry.get(name);
    if (!connector) {
      throw new Error(`Connector ${name} is not registered.`);
    }
    if (!this.state.has(name)) {
      this.state.set(name, {
        scopes: new Set(connector.defaultScopes),
        instances: [],
      });
    }
    return this.state.get(name)!;
  }

  private applyInitialConnector(connector: ToolsetConnector): void {
    if (!this.registry.has(connector.name)) {
      return;
    }
    const definition = this.registry.get(connector.name)!;
    const allowed = new Set([...definition.defaultScopes, ...definition.optionalScopes]);
    const scopes = connector.scopes.filter((scope) => allowed.has(scope));
    const state: ConnectorState = {
      scopes: new Set(scopes.length ? scopes : definition.defaultScopes),
      instances: [],
    };
    if (definition.allowInstances && Array.isArray(connector.instances)) {
      for (const instance of connector.instances) {
        try {
          state.instances.push(sanitizeInstance(instance));
        } catch {
          // drop invalid instance
        }
      }
    }
    this.state.set(connector.name, state);
  }

  getDefinitions(): ConnectorDefinition[] {
    return CONNECTOR_CATALOG.map((item) => ({ ...item }));
  }

  getConnectors(): ToolsetConnector[] {
    const connectors: ToolsetConnector[] = [];
    for (const [name, state] of this.state.entries()) {
      if (!state.scopes.size) {
        continue;
      }
      const connector: ToolsetConnector = {
        name,
        scopes: sortScopes(state.scopes),
      };
      if (state.instances.length) {
        connector.instances = state.instances.map((instance) => ({ ...instance }));
      }
      connectors.push(connector);
    }
    return sortConnectors(connectors);
  }

  hasConnector(name: ConnectorName): boolean {
    return this.state.has(name) && this.state.get(name)!.scopes.size > 0;
  }

  toggleConnector(name: ConnectorName): void {
    if (!this.registry.has(name)) {
      return;
    }
    if (this.state.has(name)) {
      this.state.delete(name);
    } else {
      this.state.set(name, {
        scopes: new Set(this.registry.get(name)!.defaultScopes),
        instances: [],
      });
    }
    this.emit("toolsets:connector_scope_requested", { name, scopes: this.state.get(name)?.scopes ?? [] });
    this.notifyChange();
  }

  setScope(name: ConnectorName, scope: string, enabled: boolean): void {
    const definition = this.registry.get(name);
    if (!definition) {
      throw new Error(`Connector ${name} is not registered.`);
    }
    const allowed = new Set([...definition.defaultScopes, ...definition.optionalScopes]);
    if (!allowed.has(scope)) {
      throw new Error(`Scope ${scope} is not available for ${name}.`);
    }
    const state = this.ensureState(name);
    if (enabled) {
      state.scopes.add(scope);
    } else if (!definition.defaultScopes.includes(scope)) {
      state.scopes.delete(scope);
    }
    if (!state.scopes.size) {
      this.state.delete(name);
    }
    this.emit("toolsets:connector_scope_requested", { name, scope, enabled });
    this.notifyChange();
  }

  addInstance(name: ConnectorName, instance: ConnectorInstance): void {
    const definition = this.registry.get(name);
    if (!definition || !definition.allowInstances) {
      throw new Error(`Connector ${name} does not support instances.`);
    }
    const state = this.ensureState(name);
    const sanitized = sanitizeInstance(instance);
    state.instances.push(sanitized);
    this.emit("toolsets:connector_instance_added", { name, instance: sanitized });
    this.notifyChange();
  }

  removeInstance(name: ConnectorName, label: string): void {
    if (!this.state.has(name)) {
      return;
    }
    const state = this.state.get(name)!;
    state.instances = state.instances.filter((instance) => instance.label !== label);
    this.notifyChange();
  }

  requiresApproval(): boolean {
    if (!this.state.size) {
      return false;
    }
    for (const [name, state] of this.state.entries()) {
      const defaults = new Set(DEFAULT_CONNECTOR_SCOPES[name]);
      for (const scope of state.scopes) {
        if (!defaults.has(scope)) {
          return true;
        }
      }
    }
    return false;
  }

  hasAnyConnector(): boolean {
    for (const state of this.state.values()) {
      if (state.scopes.size) {
        return true;
      }
    }
    return false;
  }

  getApprovalBanner(): string | null {
    if (!this.hasAnyConnector()) {
      return null;
    }
    return this.requiresApproval()
      ? "Connector scopes pending CAIO approval."
      : "Connector usage requires CAIO change control.";
  }

  save(): { valid: boolean; connectors?: ToolsetConnector[]; approvalsRequired: boolean } {
    const connectors = this.getConnectors();
    return { valid: true, connectors, approvalsRequired: this.requiresApproval() };
  }
}

export function detectOrchestrationWarning(
  capabilities: CapabilityKey[],
  connectors: ToolsetConnector[],
): string | null {
  const hasOrchestration = capabilities.includes("orchestration");
  if (!hasOrchestration) {
    return null;
  }
  for (const connector of connectors) {
    if (connector.scopes.length) {
      return null;
    }
  }
  return "Orchestration requires at least one connector scope.";
}

export function summarizeConnectorScopes(connectors: ToolsetConnector[]): Record<ConnectorName, string[]> {
  const summary: Partial<Record<ConnectorName, string[]>> = {};
  for (const connector of connectors) {
    summary[connector.name] = [...connector.scopes];
  }
  return summary as Record<ConnectorName, string[]>;
}
