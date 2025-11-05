import typesData from "./mbti_types.json";
import priorsData from "./priors_by_domain_role.json";
import {
  compatibilityScore,
  blendedScore,
  normaliseType,
  PriorsMap,
  roleFitScore,
  RoleFitResult,
  DomainSource,
  DOMAIN_MAP,
} from "./math";

export interface PersonaDefinition {
  code: string;
  name: string;
  nickname: string;
  strengths: string[];
  summary: string;
}

export interface PersonaPreferences {
  autonomy?: number;
  confidence?: number;
  collaboration?: number;
}

export interface SuggestPersonaInput {
  domain?: string | null;
  role?: string | null;
  businessFunction?: string | null;
  businessFunctionKey?: string | null;
  operatorType?: string | null;
  preferences?: PersonaPreferences | null;
}

export interface PersonaSuggestion {
  code: string;
  label: string;
  rationale: string[];
  compatibilityScore: number;
  roleFitScore: number;
  blendedScore: number;
  compatibilityNarrative: string[];
  roleFitNarrative: string[];
  preferenceNotes: string[];
  alternates: Array<{ code: string; blendedScore: number }>;
  domain: string | null;
  domainSource: DomainSource;
}

const TYPES: PersonaDefinition[] = typesData as PersonaDefinition[];
const PRIORS_MAP: PriorsMap = priorsData as PriorsMap;

interface CandidateScore {
  definition: PersonaDefinition;
  compatibility: number;
  roleFit: RoleFitResult;
  preferenceBonus: number;
  preferenceNotes: string[];
  blended: number;
}

export function listMbtiCodes(): string[] {
  return TYPES.map((item) => item.code);
}

function preferenceBias(code: string, preferences?: PersonaPreferences | null): {
  bonus: number;
  notes: string[];
} {
  if (!preferences) {
    return { bonus: 0, notes: [] };
  }

  const notes: string[] = [];
  let bonus = 0;
  const upper = normaliseType(code);
  const autonomy = preferences.autonomy ?? 50;
  const collaboration = preferences.collaboration ?? 50;
  const confidence = preferences.confidence ?? 50;

  if (autonomy >= 65 && ["I", "P"].some((letter) => upper.includes(letter))) {
    bonus += 4;
    notes.push("High autonomy preference favours independent (I/P) personas.");
  } else if (autonomy <= 40 && upper.includes("E")) {
    bonus += 2;
    notes.push("Lower autonomy leans toward collaborative (E) personas.");
  }

  if (collaboration >= 60 && upper.includes("F")) {
    bonus += 3;
    notes.push("Collaboration slider boosts feeling-oriented personas.");
  } else if (collaboration <= 40 && upper.includes("T")) {
    bonus += 2;
    notes.push("Analytical collaboration preference favours thinking (T) personas.");
  }

  if (confidence >= 65 && upper.includes("J")) {
    bonus += 4;
    notes.push("Confidence preference rewards decisive (J) personas.");
  } else if (confidence <= 40 && upper.includes("P")) {
    bonus += 2;
    notes.push("Discovery-oriented confidence slider gives perceiving (P) personas room.");
  }

  return { bonus, notes };
}

function candidateScore(definition: PersonaDefinition, input: SuggestPersonaInput): CandidateScore {
  const compatibilityResult = compatibilityScore(input.operatorType ?? "", definition.code);
  const roleFit = roleFitScore({
    domain: input.domain ?? null,
    role: input.role ?? null,
    agentCode: definition.code,
    businessFunction: input.businessFunction ?? null,
    businessFunctionKey: input.businessFunctionKey ?? null,
  });
  const { bonus, notes } = preferenceBias(definition.code, input.preferences);

  const weight = input.operatorType ? 0.62 : 0.5;
  const composite = blendedScore({
    compatibility: compatibilityResult.score + bonus,
    roleFit: roleFit.score,
    preferenceWeight: weight,
  });

  return {
    definition,
    compatibility: compatibilityResult.score,
    roleFit,
    preferenceBonus: bonus,
    preferenceNotes: notes,
    blended: composite,
  };
}

export function suggestPersona(input: SuggestPersonaInput): PersonaSuggestion {
  const domainHint = resolveDomainHint(input);
  const candidates = deriveCandidates(domainHint, input.role);
  const scored = candidates.map((definition) => candidateScore(definition, input));
  scored.sort((a, b) => b.blended - a.blended);
  const best = scored[0];
  const alternates = scored.slice(1, 4).map((candidate) => ({
    code: candidate.definition.code,
    blendedScore: candidate.blended,
  }));

  const rationale = [
    `Compatibility with operator: ${best.compatibility}%`,
    ...best.preferenceNotes,
    ...best.roleFit.factors,
  ];

  return {
    code: best.definition.code,
    label: `${best.definition.code} - ${best.definition.nickname}`,
    rationale,
    compatibilityScore: best.compatibility,
    roleFitScore: best.roleFit.score,
    blendedScore: best.blended,
    compatibilityNarrative: rationale,
    roleFitNarrative: best.roleFit.factors,
    preferenceNotes: best.preferenceNotes,
    alternates,
    domain: best.roleFit.domain,
    domainSource: best.roleFit.domainSource,
  };
}

function deriveCandidates(domain?: string | null, role?: string | null): PersonaDefinition[] {
  const uniqueCodes = new Set<string>();
  if (domain) {
    const domainMap = PRIORS_MAP[domain] ?? {};
    const roleCodes = collectCodes(domainMap[role ?? ""]);
    const defaultCodes = collectCodes(domainMap["_default"]);
    [...roleCodes, ...defaultCodes].forEach((code) => uniqueCodes.add(code));
  }

  if (uniqueCodes.size === 0) {
    TYPES.forEach((definition) => uniqueCodes.add(normaliseType(definition.code)));
  }

  return TYPES.filter((definition) => uniqueCodes.has(normaliseType(definition.code)));
}

function collectCodes(codes: string[] | undefined): string[] {
  return (codes ?? []).map((code) => normaliseType(code)).filter((code) => code.length === 4);
}

function resolveDomainHint(input: SuggestPersonaInput): string | null {
  const override = sanitiseDomainLabel(input.domain);
  if (override) {
    return override;
  }
  const key =
    normaliseFunctionKey(input.businessFunctionKey) ||
    normaliseFunctionKey(input.businessFunction);
  if (key && DOMAIN_MAP[key]) {
    return DOMAIN_MAP[key];
  }
  return null;
}

function normaliseFunctionKey(value?: string | null): string {
  return (value ?? "")
    .replace(/&/g, " AND ")
    .replace(/\+/g, " AND ")
    .replace(/[^A-Z0-9]+/gi, "_")
    .replace(/_{2,}/g, "_")
    .replace(/^_|_$/g, "")
    .toUpperCase();
}

function sanitiseDomainLabel(value?: string | null): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed ? trimmed : null;
}
