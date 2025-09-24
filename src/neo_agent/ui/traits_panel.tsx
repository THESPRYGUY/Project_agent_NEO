/**
 * @version 1.0.0
 * @changelog Added weighted traits panel with MBTI suggestions, provenance tracking, and telemetry hooks.
 * @license MIT; MBTI mappings sourced locally without external services.
 */

import seed from "../../../data/persona/mbti_traits.json" assert { type: "json" };

export type TraitKey =
  | "detail_oriented"
  | "collaborative"
  | "proactive"
  | "strategic"
  | "empathetic"
  | "experimental"
  | "efficient";

export type Traits = Record<TraitKey, number>;
export type TraitsProvenance = "manual" | "mbti_suggested" | "mbti_suggested+edited";

export interface TraitsEnvelope {
  traits: Traits;
  provenance: TraitsProvenance;
  mbti?: string;
  version: "1.0";
}

export type TraitsTelemetryEvent = {
  ts: number;
  agent_id?: string;
  step: "traits";
  action: string;
  value: unknown;
};

export type TraitsPanelOptions = {
  initial?: Partial<TraitsEnvelope> | null;
  agentId?: string;
  telemetry?: (event: TraitsTelemetryEvent) => void;
};

export type TraitsSuggestion = {
  mbti: string;
  traits: Traits;
  rationales: Record<TraitKey, string>;
};

const TRAIT_KEYS: TraitKey[] = [
  "detail_oriented",
  "collaborative",
  "proactive",
  "strategic",
  "empathetic",
  "experimental",
  "efficient",
];

const TOOLTIP_COPY: Record<TraitKey, string> = {
  detail_oriented: "Tracks nuance and closes open loops precisely",
  collaborative: "Co-creates decisions, pings stakeholders early",
  proactive: "Surfaces blockers, suggests next moves ahead",
  strategic: "Connects objectives, keeps plan horizon sharp",
  empathetic: "Adapts tone, acknowledges partner constraints",
  experimental: "Proposes tests, compares alternate paths",
  efficient: "Eliminates waste, keeps delivery cadence tight",
};

const RATIONALE_COPY: Record<TraitKey, string> = {
  detail_oriented: "Balances documentation depth with crisp checklists.",
  collaborative: "Prefers open threads and shared context handoffs.",
  proactive: "Moves first on risks and mitigation planning.",
  strategic: "Maps each deliverable to broader objectives.",
  empathetic: "Mirrors partner tone and acknowledges blockers.",
  experimental: "Introduces safe trials to validate alternatives.",
  efficient: "Optimizes flows for throughput and reusable assets.",
};

const DEFAULT_VALUE = 50;

function cloneTraits(traits: Traits): Traits {
  const copy: Partial<Traits> = {};
  for (const key of TRAIT_KEYS) {
    copy[key] = traits[key];
  }
  return copy as Traits;
}

function normalizeMbti(candidate: string | undefined | null): string | undefined {
  if (!candidate) {
    return undefined;
  }
  const normalized = candidate.toLowerCase();
  return /^[ei][ns][tf][jp]$/.test(normalized) ? normalized : undefined;
}

function now(): number {
  return Date.now();
}

function defaultTraits(): Traits {
  const traits: Partial<Traits> = {};
  for (const key of TRAIT_KEYS) {
    traits[key] = DEFAULT_VALUE;
  }
  return traits as Traits;
}

function sanitizeValue(value: unknown): number {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error("Trait values must be numeric.");
  }
  if (!Number.isInteger(value)) {
    throw new Error("Trait values must be whole numbers between 0 and 100.");
  }
  if (value < 0 || value > 100) {
    throw new Error("Trait values must be between 0 and 100.");
  }
  return value;
}

function deriveInitialEnvelope(initial?: Partial<TraitsEnvelope> | null): TraitsEnvelope {
  const traits = defaultTraits();
  let provenance: TraitsProvenance = "manual";
  let mbti: string | undefined;
  if (initial && typeof initial === "object") {
    if (initial.traits) {
      for (const key of TRAIT_KEYS) {
        const value = (initial.traits as Traits)[key];
        if (typeof value === "number" && Number.isInteger(value) && value >= 0 && value <= 100) {
          traits[key] = value;
        }
      }
    }
    if (initial.provenance === "mbti_suggested" || initial.provenance === "mbti_suggested+edited") {
      provenance = initial.provenance;
    }
    if (initial.provenance === "manual") {
      provenance = "manual";
    }
    mbti = normalizeMbti(initial.mbti);
  }
  return { traits, provenance, mbti, version: "1.0" };
}

function seedFor(mbti: string): TraitsSuggestion | null {
  const normalized = normalizeMbti(mbti);
  if (!normalized) {
    return null;
  }
  const entry = (seed as { version: string; mbti: Record<string, Traits> }).mbti[normalized];
  if (!entry) {
    return null;
  }
  const traits = cloneTraits(entry);
  const rationales: Record<TraitKey, string> = {} as Record<TraitKey, string>;
  for (const key of TRAIT_KEYS) {
    rationales[key] = RATIONALE_COPY[key];
  }
  return { mbti: normalized, traits, rationales };
}

export class TraitsPanel {
  private traits: Traits;
  private provenance: TraitsProvenance;
  private mbti?: string;
  private telemetry?: (event: TraitsTelemetryEvent) => void;
  private agentId?: string;
  private suggestion: TraitsSuggestion | null = null;
  private acceptedSuggestion: TraitsSuggestion | null = null;
  private lastSaved: TraitsEnvelope;
  private focusedTrait: TraitKey = TRAIT_KEYS[0];
  private openTrait: TraitKey | null = null;

  constructor(options: TraitsPanelOptions = {}) {
    const envelope = deriveInitialEnvelope(options.initial ?? null);
    this.traits = cloneTraits(envelope.traits);
    this.provenance = envelope.provenance;
    this.mbti = envelope.mbti;
    this.lastSaved = cloneEnvelope(envelope);
    this.telemetry = options.telemetry;
    this.agentId = options.agentId;
  }

  getTraitKeys(): TraitKey[] {
    return TRAIT_KEYS.slice();
  }

  getChipMetadata(): Array<{
    key: TraitKey;
    label: string;
    value: number;
    tooltip: string;
    ariaLabel: string;
    active: boolean;
  }> {
    return TRAIT_KEYS.map((key) => ({
      key,
      label: key.replace(/_/g, " "),
      value: this.traits[key],
      tooltip: TOOLTIP_COPY[key],
      ariaLabel: `${key.replace(/_/g, " ")} ${this.traits[key]} percent`,
      active: this.openTrait === key,
    }));
  }

  focusTrait(key: TraitKey): void {
    if (!TRAIT_KEYS.includes(key)) {
      return;
    }
    this.focusedTrait = key;
    this.openTrait = key;
  }

  getFocusedTrait(): TraitKey {
    return this.focusedTrait;
  }

  moveFocus(delta: number): TraitKey {
    const currentIndex = TRAIT_KEYS.indexOf(this.focusedTrait);
    const nextIndex = (currentIndex + delta + TRAIT_KEYS.length) % TRAIT_KEYS.length;
    this.focusedTrait = TRAIT_KEYS[nextIndex];
    return this.focusedTrait;
  }

  previewSuggestion(mbti?: string): TraitsSuggestion | null {
    const candidate = normalizeMbti(mbti ?? this.mbti);
    if (!candidate) {
      this.suggestion = null;
      return null;
    }
    const suggestion = seedFor(candidate);
    if (!suggestion) {
      this.suggestion = null;
      return null;
    }
    this.suggestion = suggestion;
    this.emit("traits:suggested", { mbti: suggestion.mbti, traits: cloneTraits(suggestion.traits) });
    return suggestion;
  }

  acceptSuggestion(mode: "accept" | "accept_and_tweak" = "accept"): void {
    if (!this.suggestion) {
      throw new Error("Call previewSuggestion before accepting a suggestion.");
    }
    this.traits = cloneTraits(this.suggestion.traits);
    this.acceptedSuggestion = cloneSuggestion(this.suggestion);
    this.provenance = "mbti_suggested";
    this.mbti = this.suggestion.mbti;
    this.openTrait = null;
    this.emit("traits:accepted", { mbti: this.mbti, mode });
  }

  dismissSuggestion(): void {
    this.suggestion = null;
  }

  setTraitValue(key: TraitKey, value: number): void {
    if (!TRAIT_KEYS.includes(key)) {
      throw new Error(`Unknown trait key: ${key}`);
    }
    const sanitized = sanitizeValue(value);
    const before = this.traits[key];
    if (before === sanitized) {
      return;
    }
    this.traits[key] = sanitized;
    if (this.acceptedSuggestion && sanitized !== this.acceptedSuggestion.traits[key]) {
      this.provenance = "mbti_suggested+edited";
    }
    if (!this.acceptedSuggestion) {
      this.provenance = "manual";
    }
    this.emit("traits:modified", {
      key,
      before,
      after: sanitized,
      changed_keys: [key],
      provenance: this.provenance,
    });
  }

  getTraitValue(key: TraitKey): number {
    if (!TRAIT_KEYS.includes(key)) {
      throw new Error(`Unknown trait key: ${key}`);
    }
    return this.traits[key];
  }

  resetToSuggested(): void {
    if (!this.acceptedSuggestion) {
      return;
    }
    this.traits = cloneTraits(this.acceptedSuggestion.traits);
    this.provenance = "mbti_suggested";
    this.emit("traits:reset_suggested", { mbti: this.acceptedSuggestion.mbti });
  }

  resetToLastSaved(): void {
    this.traits = cloneTraits(this.lastSaved.traits);
    this.provenance = this.lastSaved.provenance;
    this.mbti = this.lastSaved.mbti;
    this.emit("traits:reset_saved", { provenance: this.provenance });
  }

  validate(): { valid: boolean; errors: Partial<Record<TraitKey | "mbti", string>> } {
    const errors: Partial<Record<TraitKey | "mbti", string>> = {};
    for (const key of TRAIT_KEYS) {
      const value = this.traits[key];
      if (typeof value !== "number" || !Number.isInteger(value) || value < 0 || value > 100) {
        errors[key] = "Select an integer between 0 and 100.";
      }
    }
    if (this.mbti && !normalizeMbti(this.mbti)) {
      errors.mbti = "MBTI code must match e/i + n/s + t/f + j/p.";
    }
    return { valid: Object.keys(errors).length === 0, errors };
  }

  save(): { valid: boolean; envelope?: TraitsEnvelope; errors?: Partial<Record<TraitKey | "mbti", string>> } {
    const validation = this.validate();
    if (!validation.valid) {
      return { valid: false, errors: validation.errors };
    }
    const envelope = this.toEnvelope();
    this.lastSaved = cloneEnvelope(envelope);
    this.emit("traits:saved", { traits: cloneTraits(envelope.traits), provenance: envelope.provenance });
    return { valid: true, envelope };
  }

  toEnvelope(): TraitsEnvelope {
    return {
      traits: cloneTraits(this.traits),
      provenance: this.provenance,
      mbti: this.mbti,
      version: "1.0",
    };
  }

  getSuggestion(): TraitsSuggestion | null {
    return this.suggestion ? cloneSuggestion(this.suggestion) : null;
  }

  getAcceptedSuggestion(): TraitsSuggestion | null {
    return this.acceptedSuggestion ? cloneSuggestion(this.acceptedSuggestion) : null;
  }

  getDisclaimer(): string {
    return "Suggestions are optional and editable; use judgment.";
  }

  private emit(action: string, value: unknown): void {
    if (!this.telemetry) {
      return;
    }
    const event: TraitsTelemetryEvent = {
      ts: now(),
      agent_id: this.agentId,
      step: "traits",
      action,
      value,
    };
    this.telemetry(event);
  }
}

function cloneEnvelope(envelope: TraitsEnvelope): TraitsEnvelope {
  return {
    traits: cloneTraits(envelope.traits),
    provenance: envelope.provenance,
    mbti: envelope.mbti,
    version: envelope.version,
  };
}

function cloneSuggestion(suggestion: TraitsSuggestion): TraitsSuggestion {
  return {
    mbti: suggestion.mbti,
    traits: cloneTraits(suggestion.traits),
    rationales: { ...suggestion.rationales },
  };
}

export function createManualEnvelope(): TraitsEnvelope {
  return { traits: defaultTraits(), provenance: "manual", version: "1.0" };
}

export function traitTooltip(key: TraitKey): string {
  return TOOLTIP_COPY[key];
}

export { TRAIT_KEYS };
