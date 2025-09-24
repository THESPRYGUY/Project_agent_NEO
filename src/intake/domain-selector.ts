/**
 * @version 1.0.0
 * @changelog Introduced three-level domain selector with NAICS validation and telemetry wiring.
 * @license Licensed under the Statistics Canada Open Licence; NAICS 2022 v1.0 reference data.
 */

export type PrimaryDomainTopLevel = "Strategic Functions" | "Sector Domains" | "Technical Domains" | "Support Domains";
export type NaicsNode = { code: string; title: string; level: 2 | 3 | 4 | 5 | 6; version: "NAICS 2022 v1.0"; path: string[] };
export type PrimaryDomain = { topLevel: PrimaryDomainTopLevel; subdomain: string; tags: string[]; naics?: NaicsNode };
export type TelemetryEvent = { ts: number; actor: "intake"; step: string; action: string; value: unknown };
export type DomainSelectorOptions = { initial?: Partial<PrimaryDomain>; telemetry?: (event: TelemetryEvent) => void };
export type ValidationResult = { valid: boolean; errors: { topLevel?: string; subdomain?: string; tags?: string; naics?: string } };

const SME_OVERLAY = "Multi-Sector SME Overlay";

const PRIMARY_DOMAIN_HIERARCHY = Object.freeze({
  "Strategic Functions": [
    "AI Strategy & Governance",
    "Prompt Architecture & Evaluation",
    "Workflow Orchestration",
    "Observability & Telemetry",
  ],
  "Sector Domains": [
    "Energy & Infrastructure",
    "Economic Intelligence",
    "Environmental Intelligence",
    SME_OVERLAY,
  ],
  "Technical Domains": [
    "Agentic RAG & Knowledge Graphs",
    "Tool & Connector Integrations",
    "Memory & Data Governance",
    "Safety & Privacy Compliance",
  ],
  "Support Domains": [
    "Onboarding & Training",
    "Reporting & Publishing",
    "Lifecycle & Change Mgmt",
  ],
});

const SUBDOMAIN_TAG_HINTS = Object.freeze({
  "AI Strategy & Governance": ["governance-models", "caio-alignment", "policy-guardrails"],
  "Prompt Architecture & Evaluation": ["prompt-testing", "evaluation-harness", "prompt-templates"],
  "Workflow Orchestration": ["automation-routes", "handoff-logic", "dispatch-design"],
  "Observability & Telemetry": ["metrics-streams", "tracing", "compliance-logging"],
  "Energy & Infrastructure": [
    "vpp-grid-services",
    "data-center-strategy",
    "utility-interconnection",
    "tariffs-tve",
    "grid-modernization",
    "capital-projects",
    "reliability",
  ],
  "Economic Intelligence": ["market-watch", "inflation", "supply-chain"],
  "Environmental Intelligence": ["esg", "climate-risk", "carbon-accounting"],
  "VPP & Grid Services": ["demand-response", "load-shaping"],
  "Data Center Strategy": ["hyperscale", "site-selection", "cooling"],
  "Utility Interconnection": ["intertie", "capacity-planning"],
  "Tariffs & TVE": ["tariff-modeling", "valuation"],
  SME_OVERLAY: ["multi-sector", "sme-cohort"],
  "Agentic RAG & Knowledge Graphs": ["retrieval-design", "graph-linking"],
  "Tool & Connector Integrations": ["api-bridges", "connector-library"],
  "Memory & Data Governance": ["retention", "access-controls"],
  "Safety & Privacy Compliance": ["safety-review", "privacy-impact"],
  "Onboarding & Training": ["enablement", "playbooks"],
  "Reporting & Publishing": ["report-automation", "knowledge-publishing"],
  "Lifecycle & Change Mgmt": ["rollout", "change-control"],
});

const TOP_LEVEL_TAG_HINTS = Object.freeze({
  "Strategic Functions": ["strategy-office", "portfolio", "decision-support"],
  "Sector Domains": ["market-entry", "regulatory", "regional-focus"],
  "Technical Domains": ["integration", "platform", "composability"],
  "Support Domains": ["enablement", "ops", "governance"],
});

const noop = () => {};

function now() {
  return Date.now();
}

/**
 * @param {NaicsNode | null | undefined} node
 * @returns {NaicsNode | undefined}
 */
function cloneNaics(node) {
  if (!node) {
    return undefined;
  }
  return {
    code: node.code,
    title: node.title,
    level: node.level,
    version: node.version,
    path: Array.from(node.path),
  };
}

/**
 * @param {unknown} value
 * @returns {value is Record<string, unknown>}
 */
function isPlainObject(value) {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

/**
 * @param {unknown} value
 * @returns {value is PrimaryDomainTopLevel}
 */
function isValidTopLevel(value) {
  return typeof value === "string" && Object.prototype.hasOwnProperty.call(PRIMARY_DOMAIN_HIERARCHY, value);
}

/**
 * @param {string} tag
 * @returns {string}
 */
export function normalizeTag(tag) {
  if (!tag) {
    return "";
  }
  const replaced = tag
    .toLowerCase()
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return replaced || "";
}

/**
 * @param {string[]} tags
 * @returns {string[]}
 */
export function uniqueNormalizedTags(tags) {
  const seen = new Set();
  const result = [];
  for (const tag of tags) {
    const normalized = normalizeTag(tag);
    if (!normalized || seen.has(normalized)) {
      continue;
    }
    seen.add(normalized);
    result.push(normalized);
  }
  return result;
}

/**
 * @param {unknown} value
 * @returns {value is NaicsNode}
 */
export function isNaicsNode(value) {
  if (!isPlainObject(value)) {
    return false;
  }
  const record = /** @type {Record<string, unknown>} */ (value);
  const { code, title, level, version, path } = record;
  if (typeof code !== "string" || typeof title !== "string" || typeof version !== "string") {
    return false;
  }
  if (version !== "NAICS 2022 v1.0") {
    return false;
  }
  if (typeof level !== "number" || ![2, 3, 4, 5, 6].includes(level)) {
    return false;
  }
  if (!Array.isArray(path) || path.some((segment) => typeof segment !== "string")) {
    return false;
  }
  return true;
}

/**
 * @param {NaicsNode | null | undefined} node
 * @returns {NaicsNode | undefined}
 */
function sanitizeNaics(node) {
  if (!node) {
    return undefined;
  }
  if (!isNaicsNode(node)) {
    throw new Error("Invalid NAICS node payload provided.");
  }
  return cloneNaics(node);
}

/**
 * @param {unknown} input
 * @returns {PrimaryDomain}
 */
export function parsePrimaryDomain(input) {
  if (!isPlainObject(input)) {
    throw new Error("Primary domain payload must be an object.");
  }
  const record = /** @type {Record<string, unknown>} */ (input);
  const topLevel = record.topLevel;
  if (!isValidTopLevel(topLevel)) {
    throw new Error("Primary domain top level is invalid.");
  }
  const subdomain = record.subdomain;
  if (typeof subdomain !== "string" || !PRIMARY_DOMAIN_HIERARCHY[topLevel].includes(subdomain)) {
    throw new Error("Primary domain subdomain is invalid for the selected top level.");
  }
  const tagsValue = record.tags;
  if (!Array.isArray(tagsValue) || tagsValue.some((tag) => typeof tag !== "string")) {
    throw new Error("Primary domain tags must be an array of strings.");
  }
  const tags = uniqueNormalizedTags(/** @type {string[]} */ (tagsValue));
  const naicsValue = record.naics;
  const naics = sanitizeNaics(/** @type {NaicsNode | null | undefined} */ (naicsValue));
  if (topLevel === "Sector Domains" && subdomain !== SME_OVERLAY && !naics) {
    throw new Error("Sector domain selections require a NAICS classification.");
  }
  /** @type {PrimaryDomain} */
  const result = {
    topLevel,
    subdomain,
    tags,
  };
  if (naics) {
    result.naics = naics;
  }
  return result;
}

export class DomainSelector {
  /** @type {{ topLevel: PrimaryDomainTopLevel | ""; subdomain: string; tags: string[]; naics: NaicsNode | null }} */
  privateState;
  /** @type {(event: TelemetryEvent) => void} */
  onTelemetry;

  /**
   * @param {DomainSelectorOptions} [options]
   */
  constructor(options = {}) {
    const initial = options.initial ?? {};
    const topLevel = isValidTopLevel(initial.topLevel) ? initial.topLevel : "";
    const subdomain = typeof initial.subdomain === "string" ? initial.subdomain : "";
    const tags = uniqueNormalizedTags(Array.isArray(initial.tags) ? initial.tags : []);
    const naics = initial.naics && isNaicsNode(initial.naics) ? cloneNaics(initial.naics) : null;
    this.privateState = {
      topLevel,
      subdomain: topLevel && PRIMARY_DOMAIN_HIERARCHY[topLevel].includes(subdomain) ? subdomain : "",
      tags,
      naics,
    };
    this.onTelemetry = typeof options.telemetry === "function" ? options.telemetry : noop;
  }

  /** @returns {PrimaryDomainTopLevel[]} */
  getTopLevelOptions() {
    return /** @type {PrimaryDomainTopLevel[]} */ (Object.keys(PRIMARY_DOMAIN_HIERARCHY));
  }

  /**
   * @param {PrimaryDomainTopLevel} [topLevel]
   * @returns {string[]}
   */
  getSubdomainOptions(topLevel) {
    const level = topLevel ?? this.privateState.topLevel;
    if (!level) {
      return [];
    }
    return PRIMARY_DOMAIN_HIERARCHY[level].slice();
  }

  /** @returns {{ topLevel: PrimaryDomainTopLevel | ""; subdomain: string; tags: string[]; naics: NaicsNode | null }} */
  getState() {
    return {
      topLevel: this.privateState.topLevel,
      subdomain: this.privateState.subdomain,
      tags: Array.from(this.privateState.tags),
      naics: this.privateState.naics ? cloneNaics(this.privateState.naics) ?? null : null,
    };
  }

  /**
   * @param {PrimaryDomainTopLevel | ""} value
   */
  setTopLevel(value) {
    const normalized = value && isValidTopLevel(value) ? value : "";
    const changed = normalized !== this.privateState.topLevel;
    if (!changed) {
      return;
    }
    this.privateState.topLevel = normalized;
    this.privateState.subdomain = "";
    this.privateState.naics = null;
    this.emit({ step: "domain", action: "changed", value: { field: "topLevel", value: normalized } });
  }

  /**
   * @param {string} value
   */
  setSubdomain(value) {
    if (!this.privateState.topLevel) {
      throw new Error("Select a top level before choosing a subdomain.");
    }
    const options = this.getSubdomainOptions();
    if (!options.includes(value)) {
      throw new Error("Subdomain is not available for the selected top level.");
    }
    const changed = value !== this.privateState.subdomain;
    this.privateState.subdomain = value;
    if (changed) {
      if (this.privateState.topLevel !== "Sector Domains" || value === SME_OVERLAY) {
        this.privateState.naics = null;
      }
      this.emit({ step: "domain", action: "changed", value: { field: "subdomain", value } });
    }
  }

  /**
   * @param {string[]} tags
   */
  setTags(tags) {
    const normalized = uniqueNormalizedTags(tags);
    this.privateState.tags = normalized;
    this.emit({ step: "domain", action: "changed", value: { field: "tags", value: normalized } });
  }

  /**
   * @param {string} tag
   */
  addTag(tag) {
    const normalized = normalizeTag(tag);
    if (!normalized) {
      return;
    }
    if (!this.privateState.tags.includes(normalized)) {
      this.privateState.tags.push(normalized);
      this.emit({ step: "domain", action: "changed", value: { field: "tags", value: Array.from(this.privateState.tags) } });
    }
  }

  /**
   * @param {string} input
   */
  ingestFreeformTags(input) {
    if (!input) {
      return;
    }
    const parts = input.split(/[\n,;]+/g).map((piece) => piece.trim()).filter(Boolean);
    const combined = parts.length ? Array.from(new Set([...this.privateState.tags, ...parts])) : this.privateState.tags.slice();
    this.setTags(combined);
  }

  /**
   * @param {NaicsNode | null | undefined} node
   */
  setNaics(node) {
    const sanitized = sanitizeNaics(node);
    this.privateState.naics = sanitized ?? null;
    this.emit({
      step: "naics",
      action: "selected",
      value: sanitized ? { code: sanitized.code, level: sanitized.level } : null,
    });
  }

  /** @returns {string[]} */
  getContextualTags() {
    const suggestions = new Set();
    if (this.privateState.topLevel && TOP_LEVEL_TAG_HINTS[this.privateState.topLevel]) {
      for (const tag of TOP_LEVEL_TAG_HINTS[this.privateState.topLevel]) {
        suggestions.add(tag);
      }
    }
    if (this.privateState.subdomain && SUBDOMAIN_TAG_HINTS[this.privateState.subdomain]) {
      for (const tag of SUBDOMAIN_TAG_HINTS[this.privateState.subdomain]) {
        suggestions.add(tag);
      }
    }
    for (const existing of this.privateState.tags) {
      suggestions.delete(existing);
    }
    return Array.from(suggestions);
  }

  /** @returns {boolean} */
  canSave() {
    return this._performValidation(false).valid;
  }

  /** @returns {ValidationResult} */
  validate() {
    return this._performValidation(true);
  }

  /** @returns {{ domain: PrimaryDomain; industry: { naics: NaicsNode | null } }} */
  toRequestEnvelope() {
    const check = this._performValidation(false);
    if (!check.valid) {
      const error = new Error("Primary domain selection is incomplete.");
      Object.assign(error, { details: check.errors });
      throw error;
    }
    /** @type {PrimaryDomain} */
    const domain = {
      topLevel: this.privateState.topLevel,
      subdomain: this.privateState.subdomain,
      tags: Array.from(this.privateState.tags),
    };
    if (this.privateState.naics) {
      domain.naics = cloneNaics(this.privateState.naics);
    }
    const envelope = {
      domain,
      industry: { naics: this.privateState.naics ? cloneNaics(this.privateState.naics) ?? null : null },
    };
    this.emit({ step: "intake", action: "saved", value: envelope });
    return envelope;
  }

  /**
   * @param {boolean} emitEvent
   * @returns {ValidationResult}
   */
  _performValidation(emitEvent) {
    const errors = {};
    const { topLevel, subdomain, tags, naics } = this.privateState;
    if (!topLevel) {
      errors.topLevel = "Select a primary domain tier.";
    }
    if (!subdomain) {
      errors.subdomain = "Choose a focused subdomain.";
    }
    if (!tags.length) {
      errors.tags = "Add at least one context tag.";
    }
    if (topLevel === "Sector Domains" && subdomain && subdomain !== SME_OVERLAY) {
      if (!naics) {
        errors.naics = "Select an industry classification.";
      } else if (!isNaicsNode(naics)) {
        errors.naics = "Industry classification is invalid.";
      }
    }
    const valid = Object.keys(errors).length === 0;
    if (emitEvent) {
      this.emit({ step: "domain", action: "validated", value: { valid, errors } });
    }
    return { valid, errors };
  }

  /**
   * @param {TelemetryEvent} event
   */
  emit(event) {
    try {
      this.onTelemetry({ ...event, ts: now(), actor: "intake" });
    } catch (error) {
      console.error("Telemetry handler threw an error", error);
    }
  }
}

export { PRIMARY_DOMAIN_HIERARCHY, SME_OVERLAY as SME_OVERLAY_LABEL, TOP_LEVEL_TAG_HINTS, SUBDOMAIN_TAG_HINTS };
