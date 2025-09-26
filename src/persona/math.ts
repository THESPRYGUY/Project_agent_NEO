import priorsData from "./priors_by_domain_role.json";

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

export interface RoleFitResult {
  score: number;
  factors: string[];
}

export type PriorsMap = Record<string, Record<string, string[]>>;

const AXES: Array<{ axis: string; index: number; description: string }> = [
  { axis: "Mind", index: 0, description: "How energy is directed (Introversion vs Extraversion)." },
  { axis: "Information", index: 1, description: "Preferred data intake (Sensing vs iNtuition)." },
  { axis: "Decisions", index: 2, description: "Decision lens (Thinking vs Feeling)." },
  { axis: "Structure", index: 3, description: "Lifestyle preference (Judging vs Perceiving)." },
];

export const PRIORS: PriorsMap = priorsData as PriorsMap;

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

function flattenPriors(priors: Record<string, string[]> | undefined): string[] {
  if (!priors) {
    return [];
  }
  const unique = new Set<string>();
  Object.values(priors).forEach((codes) => {
    codes.forEach((code) => unique.add(normaliseType(code)));
  });
  return Array.from(unique);
}

export function roleFitScore(
  domain: string | null | undefined,
  role: string | null | undefined,
  agentCode: string,
  priors: PriorsMap = PRIORS,
): RoleFitResult {
  const agent = normaliseType(agentCode);
  if (agent.length !== 4) {
    return { score: 0, factors: [] };
  }

  const factors: string[] = [];
  let score = 55;

  if (domain) {
    const domainMap = priors[domain] ?? {};
    const roleCodes = normaliseList(domainMap[role ?? ""]);
    const defaultCodes = normaliseList(domainMap["_default"]);
    const domainBaseline = flattenPriors(priors[domain]).length > 0;

    if (role && roleCodes.includes(agent)) {
      score = 95;
      factors.push(`Strong prior: ${agent} excels for ${role} in ${domain}.`);
    } else if (defaultCodes.includes(agent)) {
      score = 82;
      factors.push(`Domain match: ${agent} is a reliable fit within ${domain}.`);
    } else if (domainBaseline) {
      score = 68;
      factors.push(`Adjacent fit: ${agent} aligns with neighbouring personas for ${domain}.`);
    } else {
      score = 60;
      factors.push(`No explicit prior for ${domain}; using balanced baseline.`);
    }
  } else {
    score = 60;
    factors.push("Domain not provided; using generic persona baseline.");
  }

  return { score: Math.round(clamp(score, 0, 100)), factors };
}

function normaliseList(values: string[] | undefined): string[] {
  return (values ?? []).map(normaliseType).filter((code) => code.length === 4);
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
