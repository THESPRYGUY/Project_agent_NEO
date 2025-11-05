import priorsData from "./priors_by_domain_role.json";
import rolePriorsData from "./priors_role_only.json";
import domainMapData from "../../data/domain_map.json";

export type MbtiCode = string;

export interface CompatibilityBreakdown {
  axis: string;
  operator: string;
  agent: string;
  match: boolean;
}

export interface CompatibilityResult {
  score: number;
  breakdown: CompatibilityBreakdown[];
  matches: number;
  mismatches: number;
}

export type DomainSource = "override" | "derived" | "none";

export interface RoleFitResult {
  score: number;
  factors: string[];
  domain: string | null;
  domainSource: DomainSource;
}

export type PriorsMap = Record<string, Record<string, string[]>>;
export type RolePriorsMap = Record<string, string[]>;
export type DomainMap = Record<string, string>;

const AXES: Array<{ axis: string; index: number; description: string }> = [
  { axis: "Mind", index: 0, description: "How energy is directed (Introversion vs Extraversion)." },
  { axis: "Information", index: 1, description: "Preferred data intake (Sensing vs iNtuition)." },
  { axis: "Decisions", index: 2, description: "Decision lens (Thinking vs Feeling)." },
  { axis: "Structure", index: 3, description: "Lifestyle preference (Judging vs Perceiving)." },
];

export const PRIORS: PriorsMap = priorsData as PriorsMap;
export const ROLE_PRIORS: RolePriorsMap = normaliseRolePriors(rolePriorsData as RolePriorsMap);
export const DOMAIN_MAP: DomainMap = normaliseDomainMap(domainMapData as DomainMap);

export function clamp(value: number, lower: number, upper: number): number {
  return Math.max(lower, Math.min(upper, value));
}

export function normaliseType(code: string | null | undefined): MbtiCode {
  if (!code) {
    return "";
  }
  return code.toUpperCase().replace(/[^EINFTSPJ]/g, "");
}

export function compatibilityScore(operatorCode: string, agentCode: string): CompatibilityResult {
  const operator = normaliseType(operatorCode);
  const agent = normaliseType(agentCode);

  if (operator.length !== 4 || agent.length !== 4) {
    return {
      score: 0,
      breakdown: [],
      matches: 0,
      mismatches: 0,
    };
  }

  const breakdown: CompatibilityBreakdown[] = [];
  let matches = 0;
  let mismatches = 0;

  AXES.forEach(({ axis, index }) => {
    const operatorLetter = operator[index];
    const agentLetter = agent[index];
    const match = operatorLetter === agentLetter;
    if (match) {
      matches += 1;
    } else {
      mismatches += 1;
    }
    breakdown.push({ axis, operator: operatorLetter, agent: agentLetter, match });
  });

  const base = 40;
  const score = clamp(base + matches * 15 - mismatches * 5, 20, 100);

  return {
    score: Math.round(score),
    breakdown,
    matches,
    mismatches,
  };
}

export interface RoleFitScoreInput {
  domain?: string | null;
  role?: string | null;
  agentCode: string;
  businessFunction?: string | null;
  businessFunctionKey?: string | null;
  priors?: PriorsMap;
  rolePriors?: RolePriorsMap;
  domainMap?: DomainMap;
}

export function roleFitScore({
  domain,
  role,
  agentCode,
  businessFunction,
  businessFunctionKey,
  priors = PRIORS,
  rolePriors = ROLE_PRIORS,
  domainMap = DOMAIN_MAP,
}: RoleFitScoreInput): RoleFitResult {
  const agent = normaliseType(agentCode);
  if (agent.length !== 4) {
    return { score: 0, factors: [], domain: null, domainSource: "none" };
  }

  const factors: string[] = [];
  let score = 55;

  const { resolvedDomain, source } = resolveDomain({
    override: domain,
    businessFunction,
    businessFunctionKey,
    domainMap,
  });

  const hasFunctionContext =
    Boolean((businessFunctionKey ?? "").trim()) || Boolean((businessFunction ?? "").trim());

  const domainLookup = resolvedDomain ? priors[resolvedDomain] ?? {} : {};
  const domainBaseline = resolvedDomain ? flattenPriors(domainLookup) : [];
  const roleKey = normaliseRoleKey(role);
  const rolePriorList = roleKey ? rolePriors[roleKey] ?? [] : [];
  const defaultRolePriors = rolePriors["_DEFAULT"] ?? rolePriors["_default"] ?? [];
  const hasRoleContext = Boolean(roleKey);

  if (source === "derived" && resolvedDomain) {
    factors.push(`Domain inferred from Business Function: ${resolvedDomain}.`);
  }

  if (resolvedDomain) {
    const roleCodes = normaliseList(domainLookup[role ?? ""]);
    const defaultCodes = normaliseList(domainLookup["_default"]);

    if (role && roleCodes.includes(agent)) {
      score = 95;
      factors.push(`Strong prior: ${agent} excels for ${role} in ${resolvedDomain}.`);
    } else if (defaultCodes.includes(agent)) {
      score = 82;
      factors.push(`Domain match: ${agent} is a reliable fit within ${resolvedDomain}.`);
    } else if (domainBaseline.length > 0) {
      score = 68;
      factors.push(`Adjacent fit: ${agent} aligns with neighbouring personas for ${resolvedDomain}.`);
    } else if (rolePriorList.length > 0 || defaultRolePriors.length > 0) {
      score = 70;
      appendRoleFallback({ factors, agent, role, fallbackOnly: true });
    } else {
      score = 60;
      factors.push(`No explicit prior for ${resolvedDomain}; using balanced baseline.`);
    }

    return {
      score: Math.round(clamp(score, 0, 100)),
      factors,
      domain: resolvedDomain,
      domainSource: source,
    };
  }

  const roleCodes = normaliseList(rolePriorList);
  const defaultCodes = normaliseList(defaultRolePriors);

  if (roleCodes.includes(agent)) {
    score = 90;
    appendRoleFallback({ factors, agent, role, emphasis: "strong" });
  } else if (defaultCodes.includes(agent)) {
    score = 78;
    appendRoleFallback({ factors, agent, role });
  } else if (roleCodes.length > 0 || defaultCodes.length > 0) {
    score = 68;
    appendRoleFallback({ factors, agent, role });
  } else {
    score = 60;
    if (hasFunctionContext || hasRoleContext) {
      factors.push("Role prior unavailable; using balanced baseline.");
    } else {
      factors.push("Domain not provided; using generic persona baseline.");
    }
  }

  return {
    score: Math.round(clamp(score, 0, 100)),
    factors,
    domain: null,
    domainSource: "none",
  };
}

function appendRoleFallback({
  factors,
  agent,
  role,
  emphasis,
  fallbackOnly = false,
}: {
  factors: string[];
  agent: string;
  role?: string | null;
  emphasis?: "strong";
  fallbackOnly?: boolean;
}) {
  const baseLine = "Role prior used (no domain).";
  if (!factors.includes(baseLine)) {
    factors.push(baseLine);
  }
  if (fallbackOnly) {
    return;
  }

  const roleLabel = role ? ` for ${role}` : "";
  if (emphasis === "strong") {
    factors.push(`Strong match${roleLabel}: ${agent}.`);
  } else {
    factors.push(`Aligned with expected profile${roleLabel}: ${agent}.`);
  }
}

function normaliseList(values: string[] | undefined): string[] {
  return (values ?? []).map(normaliseType).filter((code) => code.length === 4);
}

function flattenPriors(priors: Record<string, string[]>) {
  return Object.values(priors ?? {}).flatMap((codes) => normaliseList(codes));
}

function normaliseRoleKey(role: string | null | undefined): string {
  return (role ?? "").toUpperCase().trim();
}

function normaliseFunctionKey(value: string | null | undefined): string {
  return (value ?? "")
    .replace(/&/g, " AND ")
    .replace(/\+/g, " AND ")
    .replace(/[^A-Z0-9]+/gi, "_")
    .replace(/_{2,}/g, "_")
    .replace(/^_|_$/g, "")
    .toUpperCase();
}

function normaliseDomainMap(raw: DomainMap): DomainMap {
  const out: DomainMap = {};
  Object.entries(raw ?? {}).forEach(([key, value]) => {
    const normalisedKey = normaliseFunctionKey(key);
    if (!normalisedKey || !value) {
      return;
    }
    out[normalisedKey] = String(value);
  });
  return out;
}

function normaliseRolePriors(raw: RolePriorsMap): RolePriorsMap {
  const out: RolePriorsMap = {};
  Object.entries(raw ?? {}).forEach(([key, value]) => {
    const roleKey = key === "_default" ? "_DEFAULT" : normaliseRoleKey(key);
    if (!roleKey) {
      return;
    }
    out[roleKey] = Array.isArray(value) ? value.map(String) : [];
  });
  return out;
}

function resolveDomain({
  override,
  businessFunction,
  businessFunctionKey,
  domainMap,
}: {
  override?: string | null;
  businessFunction?: string | null;
  businessFunctionKey?: string | null;
  domainMap: DomainMap;
}): { resolvedDomain: string | null; source: DomainSource } {
  const overrideDomain = sanitiseDomainLabel(override);
  if (overrideDomain) {
    return { resolvedDomain: overrideDomain, source: "override" };
  }

  const explicitKey = normaliseFunctionKey(businessFunctionKey);
  const derivedKey = explicitKey || normaliseFunctionKey(businessFunction);
  if (derivedKey && domainMap[derivedKey]) {
    return { resolvedDomain: domainMap[derivedKey], source: "derived" };
  }

  return { resolvedDomain: null, source: "none" };
}

function sanitiseDomainLabel(value: string | null | undefined): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : null;
}

export interface CompositeScoreInput {
  compatibility: number;
  roleFit: number;
  preferenceWeight?: number;
}

export function blendedScore({ compatibility, roleFit, preferenceWeight = 0.5 }: CompositeScoreInput): number {
  const weight = clamp(preferenceWeight, 0, 1);
  const score = weight * compatibility + (1 - weight) * roleFit;
  return Math.round(clamp(score, 0, 100));
}
