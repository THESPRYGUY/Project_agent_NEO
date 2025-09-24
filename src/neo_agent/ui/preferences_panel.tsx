/**
 * @version 1.0.0
 * @changelog Introduced normalized preferences panel with presets, telemetry, and derived knobs.
 * @license MIT; operates offline with locally bundled datasets only.
 */

import seed from "../../../data/persona/mbti_traits.json" assert { type: "json" };
import type { Traits, TraitsEnvelope } from "./traits_panel";

export type CommStyle =
  | "formal"
  | "conversational"
  | "executive_brief"
  | "technical_deep";

export type CollabMode = "solo" | "cross_functional" | "pair_build" | "review_first";

export type PreferencesProvenance = "manual" | "preset_applied" | "preset_edited";

export interface PreferenceKnobs {
  confirmation_gate: "none" | "light" | "strict";
  rec_depth: "short" | "balanced" | "deep";
  handoff_freq: "low" | "medium" | "high";
  communication: {
    word_cap: number | null;
    bulletize_default: boolean;
    include_call_to_action: boolean;
    allow_extended_rationale: boolean;
    include_code_snippets: boolean;
  };
  collaboration: {
    require_pair_confirmation: boolean;
    require_review_handoff: boolean;
  };
}

export interface Preferences {
  autonomy: number;
  confidence: number;
  collaboration: number;
  comm_style: CommStyle;
  collab_mode: CollabMode;
  prefs_knobs: PreferenceKnobs;
  provenance: PreferencesProvenance;
  version: "1.0";
}

export type PreferencesTelemetryEvent = {
  ts: number;
  agent_id?: string;
  step: "preferences";
  action: string;
  value: unknown;
};

export type PreferencesPanelOptions = {
  initial?: Partial<Preferences> | null;
  traits?: Partial<TraitsEnvelope> | null;
  telemetry?: (event: PreferencesTelemetryEvent) => void;
  agentId?: string;
};

export type PreferencesPreset = {
  source: "traits" | "mbti";
  mbti?: string;
  values: Pick<
    Preferences,
    "autonomy" | "confidence" | "collaboration" | "comm_style" | "collab_mode"
  >;
  knobs: PreferenceKnobs;
};

const COMM_STYLE_OPTIONS: CommStyle[] = [
  "formal",
  "conversational",
  "executive_brief",
  "technical_deep",
];

const COLLAB_MODE_OPTIONS: CollabMode[] = [
  "solo",
  "cross_functional",
  "pair_build",
  "review_first",
];

const SLIDER_KEYS = ["autonomy", "confidence", "collaboration"] as const;
type SliderKey = (typeof SLIDER_KEYS)[number];

const SLIDER_TOOLTIPS: Record<SliderKey, string> = {
  autonomy: "How far the agent proceeds before asking.",
  confidence: "How assertive vs. cautious recommendations are.",
  collaboration: "How often to coordinate/handoff or ask clarifiers.",
};

const SLIDER_DESCRIPTORS: Array<{ max: number; label: string }> = [
  { max: 40, label: "low" },
  { max: 75, label: "balanced" },
  { max: 100, label: "high" },
];

const DEFAULT_VALUES: Preferences = Object.freeze({
  autonomy: 50,
  confidence: 50,
  collaboration: 50,
  comm_style: "formal",
  collab_mode: "solo",
  prefs_knobs: {
    confirmation_gate: "light",
    rec_depth: "balanced",
    handoff_freq: "medium",
    communication: {
      word_cap: null,
      bulletize_default: false,
      include_call_to_action: false,
      allow_extended_rationale: false,
      include_code_snippets: false,
    },
    collaboration: {
      require_pair_confirmation: false,
      require_review_handoff: false,
    },
  },
  provenance: "manual",
  version: "1.0",
});

function clonePreferences(pref: Preferences): Preferences {
  return JSON.parse(JSON.stringify(pref)) as Preferences;
}

function now(): number {
  return Date.now();
}

function snapToStep(value: number): number {
  if (!Number.isFinite(value)) {
    return 0;
  }
  const bounded = Math.min(100, Math.max(0, value));
  const snapped = Math.round(bounded / 5) * 5;
  return Math.min(100, Math.max(0, snapped));
}

function descriptorFor(value: number): string {
  const bounded = Math.min(100, Math.max(0, value));
  for (const bucket of SLIDER_DESCRIPTORS) {
    if (bounded <= bucket.max) {
      return bucket.label;
    }
  }
  return SLIDER_DESCRIPTORS[SLIDER_DESCRIPTORS.length - 1].label;
}

function sanitizeCommStyle(value: unknown): CommStyle {
  if (typeof value === "string" && (COMM_STYLE_OPTIONS as readonly string[]).includes(value)) {
    return value as CommStyle;
  }
  return DEFAULT_VALUES.comm_style;
}

function sanitizeCollabMode(value: unknown): CollabMode {
  if (typeof value === "string" && (COLLAB_MODE_OPTIONS as readonly string[]).includes(value)) {
    return value as CollabMode;
  }
  return DEFAULT_VALUES.collab_mode;
}

function sanitizeProvenance(value: unknown): PreferencesProvenance {
  if (value === "preset_applied" || value === "preset_edited") {
    return value;
  }
  return "manual";
}

function normalizeInitial(options: PreferencesPanelOptions): Preferences {
  const base = clonePreferences(DEFAULT_VALUES);
  const initial = options.initial;
  if (!initial || typeof initial !== "object") {
    return base;
  }

  if (typeof initial.autonomy === "number") {
    base.autonomy = snapToStep(initial.autonomy);
  }
  if (typeof initial.confidence === "number") {
    base.confidence = snapToStep(initial.confidence);
  }
  if (typeof initial.collaboration === "number") {
    base.collaboration = snapToStep(initial.collaboration);
  }
  if (initial.comm_style) {
    base.comm_style = sanitizeCommStyle(initial.comm_style);
  }
  if (initial.collab_mode) {
    base.collab_mode = sanitizeCollabMode(initial.collab_mode);
  }
  base.provenance = sanitizeProvenance(initial.provenance);
  base.version = "1.0";

  if (initial.prefs_knobs && typeof initial.prefs_knobs === "object") {
    base.prefs_knobs = {
      confirmation_gate: initial.prefs_knobs.confirmation_gate === "none"
        ? "none"
        : initial.prefs_knobs.confirmation_gate === "strict"
          ? "strict"
          : "light",
      rec_depth: initial.prefs_knobs.rec_depth === "deep"
        ? "deep"
        : initial.prefs_knobs.rec_depth === "short"
          ? "short"
          : "balanced",
      handoff_freq: initial.prefs_knobs.handoff_freq === "high"
        ? "high"
        : initial.prefs_knobs.handoff_freq === "low"
          ? "low"
          : "medium",
      communication: {
        word_cap:
          typeof initial.prefs_knobs.communication?.word_cap === "number"
            ? initial.prefs_knobs.communication.word_cap
            : null,
        bulletize_default: Boolean(initial.prefs_knobs.communication?.bulletize_default),
        include_call_to_action: Boolean(initial.prefs_knobs.communication?.include_call_to_action),
        allow_extended_rationale: Boolean(initial.prefs_knobs.communication?.allow_extended_rationale),
        include_code_snippets: Boolean(initial.prefs_knobs.communication?.include_code_snippets),
      },
      collaboration: {
        require_pair_confirmation: Boolean(
          initial.prefs_knobs.collaboration?.require_pair_confirmation,
        ),
        require_review_handoff: Boolean(
          initial.prefs_knobs.collaboration?.require_review_handoff,
        ),
      },
    };
  }

  return base;
}

function traitAverage(values: Array<number | undefined>): number {
  const filtered = values.filter((value): value is number => typeof value === "number");
  if (!filtered.length) {
    return 50;
  }
  const sum = filtered.reduce((acc, value) => acc + value, 0);
  return sum / filtered.length;
}

function resolveTraitsForPreset(options: PreferencesPanelOptions): {
  source: "traits" | "mbti";
  traits: Traits;
  mbti?: string;
} | null {
  const envelope = options.traits;
  if (!envelope || typeof envelope !== "object") {
    return null;
  }

  const traits = envelope.traits as Traits | undefined;
  if (traits) {
    return { source: "traits", traits: { ...traits }, mbti: envelope.mbti };
  }

  const mbti = typeof envelope.mbti === "string" ? envelope.mbti.toLowerCase() : undefined;
  if (!mbti) {
    return null;
  }
  const mapping = (seed as { version: string; mbti: Record<string, Traits> }).mbti;
  const suggested = mapping[mbti];
  if (!suggested) {
    return null;
  }
  return { source: "mbti", traits: { ...suggested }, mbti };
}

export function derivePreferenceKnobs(state: {
  autonomy: number;
  confidence: number;
  collaboration: number;
  comm_style: CommStyle;
  collab_mode: CollabMode;
}): PreferenceKnobs {
  const autonomy = snapToStep(state.autonomy);
  const confidence = snapToStep(state.confidence);
  const collaboration = snapToStep(state.collaboration);

  let confirmation_gate: PreferenceKnobs["confirmation_gate"] = "light";
  if (autonomy >= 80) {
    confirmation_gate = "none";
  } else if (autonomy <= 40) {
    confirmation_gate = "strict";
  }

  let rec_depth: PreferenceKnobs["rec_depth"] = "balanced";
  if (confidence >= 80) {
    rec_depth = "deep";
  } else if (confidence <= 40) {
    rec_depth = "short";
  }

  let handoff_freq: PreferenceKnobs["handoff_freq"] = "medium";
  if (collaboration >= 80) {
    handoff_freq = "high";
  } else if (collaboration <= 40) {
    handoff_freq = "low";
  }

  const communication: PreferenceKnobs["communication"] = {
    word_cap: null,
    bulletize_default: false,
    include_call_to_action: false,
    allow_extended_rationale: false,
    include_code_snippets: false,
  };

  if (state.comm_style === "executive_brief") {
    communication.word_cap = 200;
    communication.bulletize_default = true;
    communication.include_call_to_action = true;
  } else if (state.comm_style === "technical_deep") {
    communication.allow_extended_rationale = true;
    communication.include_code_snippets = true;
  } else if (state.comm_style === "conversational") {
    communication.bulletize_default = false;
    communication.word_cap = null;
  }

  const collaborationKnobs: PreferenceKnobs["collaboration"] = {
    require_pair_confirmation: state.collab_mode === "pair_build",
    require_review_handoff: state.collab_mode === "review_first",
  };

  return {
    confirmation_gate,
    rec_depth,
    handoff_freq,
    communication,
    collaboration: collaborationKnobs,
  };
}

function buildPresetFromTraits(
  traits: Traits,
): Pick<Preferences, "autonomy" | "confidence" | "collaboration" | "comm_style" | "collab_mode"> {
  const autonomy = snapToStep(traitAverage([traits.proactive, traits.experimental]));
  const confidence = snapToStep(traitAverage([traits.strategic, traits.detail_oriented]));
  const collaboration = snapToStep(traitAverage([traits.collaborative, traits.empathetic]));

  let comm_style: CommStyle = "formal";
  if (traits.strategic >= 75 && traits.efficient >= 55) {
    comm_style = "executive_brief";
  } else if (traits.experimental >= 70 || traits.detail_oriented >= 70) {
    comm_style = "technical_deep";
  } else if (traits.empathetic >= 65 || traits.collaborative >= 65) {
    comm_style = "conversational";
  }

  let collab_mode: CollabMode = "solo";
  if (traits.collaborative >= 80) {
    collab_mode = "cross_functional";
  } else if (traits.proactive >= 75) {
    collab_mode = "pair_build";
  } else if (traits.detail_oriented >= 75) {
    collab_mode = "review_first";
  }

  return { autonomy, confidence, collaboration, comm_style, collab_mode };
}

export class PreferencesPanel {
  private preferences: Preferences;
  private lastSaved: Preferences;
  private telemetry?: (event: PreferencesTelemetryEvent) => void;
  private agentId?: string;
  private traitsContext: ReturnType<typeof resolveTraitsForPreset>;
  private presetSnapshot: PreferencesPreset | null = null;
  private lastPreview: PreferencesPreset | null = null;
  private telemetryLog: PreferencesTelemetryEvent[] = [];
  private legacyConflict = false;

  constructor(options: PreferencesPanelOptions = {}) {
    this.preferences = normalizeInitial(options);
    const initialGate = this.preferences.prefs_knobs.confirmation_gate;
    this.preferences.prefs_knobs = derivePreferenceKnobs(this.preferences);
    if (this.preferences.autonomy <= 30 && initialGate === "none") {
      this.legacyConflict = true;
    }
    this.lastSaved = clonePreferences(this.preferences);
    this.telemetry = options.telemetry;
    this.agentId = options.agentId;
    this.traitsContext = resolveTraitsForPreset(options);
  }

  private emit(action: string, value: unknown): void {
    const event: PreferencesTelemetryEvent = {
      ts: now(),
      agent_id: this.agentId,
      step: "preferences",
      action,
      value,
    };
    this.telemetryLog.push(event);
    if (this.telemetry) {
      this.telemetry(event);
    }
  }

  getTelemetryLog(): PreferencesTelemetryEvent[] {
    return this.telemetryLog.slice();
  }

  getSliderValue(key: SliderKey): number {
    return this.preferences[key];
  }

  getSliderTooltip(key: SliderKey): string {
    return SLIDER_TOOLTIPS[key];
  }

  getSliderDescriptor(key: SliderKey): string {
    return descriptorFor(this.preferences[key]);
  }

  getCommStyle(): CommStyle {
    return this.preferences.comm_style;
  }

  getCollabMode(): CollabMode {
    return this.preferences.collab_mode;
  }

  setSliderValue(key: SliderKey, value: number): void {
    const snapped = snapToStep(value);
    if (this.preferences[key] === snapped) {
      return;
    }
    this.preferences[key] = snapped;
    this.preferences.prefs_knobs = derivePreferenceKnobs(this.preferences);
    this.bumpProvenanceForEdit();
    this.emit("prefs:changed", { field: key, value: snapped });
  }

  setCommStyle(style: CommStyle): void {
    const next = sanitizeCommStyle(style);
    if (this.preferences.comm_style === next) {
      return;
    }
    this.preferences.comm_style = next;
    this.preferences.prefs_knobs = derivePreferenceKnobs(this.preferences);
    this.bumpProvenanceForEdit();
    this.emit("prefs:changed", { field: "comm_style", value: next });
  }

  setCollabMode(mode: CollabMode): void {
    const next = sanitizeCollabMode(mode);
    if (this.preferences.collab_mode === next) {
      return;
    }
    this.preferences.collab_mode = next;
    this.preferences.prefs_knobs = derivePreferenceKnobs(this.preferences);
    this.bumpProvenanceForEdit();
    this.emit("prefs:changed", { field: "collab_mode", value: next });
  }

  private bumpProvenanceForEdit(): void {
    if (this.preferences.provenance === "preset_applied") {
      this.preferences.provenance = "preset_edited";
    }
  }

  previewPreset(): PreferencesPreset | null {
    if (!this.traitsContext) {
      return null;
    }
    const values = buildPresetFromTraits(this.traitsContext.traits);
    const knobs = derivePreferenceKnobs(values);
    const preset: PreferencesPreset = {
      source: this.traitsContext.source,
      mbti: this.traitsContext.mbti,
      values,
      knobs,
    };
    this.lastPreview = preset;
    this.emit("prefs:preset_previewed", preset);
    return preset;
  }

  applyPreset(mode: "apply" | "apply_and_edit" = "apply"): PreferencesPreset | null {
    const preset = this.lastPreview ?? this.previewPreset();
    if (!preset) {
      return null;
    }
    this.preferences.autonomy = preset.values.autonomy;
    this.preferences.confidence = preset.values.confidence;
    this.preferences.collaboration = preset.values.collaboration;
    this.preferences.comm_style = preset.values.comm_style;
    this.preferences.collab_mode = preset.values.collab_mode;
    this.preferences.prefs_knobs = derivePreferenceKnobs(this.preferences);
    this.preferences.provenance = "preset_applied";
    this.presetSnapshot = preset;
    if (mode === "apply_and_edit") {
      this.preferences.provenance = "preset_edited";
    }
    this.emit("prefs:preset_applied", { mode, preset });
    return preset;
  }

  resetToLastSaved(): void {
    this.preferences = clonePreferences(this.lastSaved);
    this.emit("prefs:reset", { target: "last_saved" });
  }

  toPreferences(): Preferences {
    return clonePreferences(this.preferences);
  }

  getDerivedKnobs(): PreferenceKnobs {
    return clonePreferences(this.preferences).prefs_knobs;
  }

  private validate(): { valid: boolean; errors: string[]; conflict: boolean } {
    const errors: string[] = [];

    for (const key of SLIDER_KEYS) {
      const value = this.preferences[key];
      if (!Number.isInteger(value) || value < 0 || value > 100 || value % 5 !== 0) {
        errors.push(`${key} must be an integer between 0 and 100 in increments of 5.`);
      }
    }

    if (!COMM_STYLE_OPTIONS.includes(this.preferences.comm_style)) {
      errors.push("Communication style must be a supported option.");
    }
    if (!COLLAB_MODE_OPTIONS.includes(this.preferences.collab_mode)) {
      errors.push("Collaboration mode must be a supported option.");
    }

    const recalculated = derivePreferenceKnobs(this.preferences);
    let conflict = false;
    if (this.preferences.autonomy <= 30 && this.preferences.prefs_knobs.confirmation_gate === "none") {
      conflict = true;
    }
    this.preferences.prefs_knobs = recalculated;

    return { valid: errors.length === 0, errors, conflict };
  }

  save(): { valid: boolean; errors?: string[]; preferences?: Preferences } {
    const { valid, errors, conflict } = this.validate();
    if (!valid) {
      return { valid: false, errors };
    }

    if (conflict || this.legacyConflict) {
      this.emit("prefs:conflict_blocked", {
        autonomy: this.preferences.autonomy,
        confirmation_gate: this.preferences.prefs_knobs.confirmation_gate,
      });
      this.legacyConflict = false;
    }

    if (this.preferences.provenance === "manual" && this.presetSnapshot) {
      const same = SLIDER_KEYS.every(
        (key) => this.preferences[key] === this.presetSnapshot!.values[key],
      );
      const dropdownsMatch =
        this.preferences.comm_style === this.presetSnapshot.values.comm_style &&
        this.preferences.collab_mode === this.presetSnapshot.values.collab_mode;
      if (same && dropdownsMatch) {
        this.preferences.provenance = "preset_applied";
      }
    }

    this.preferences.version = "1.0";
    this.lastSaved = clonePreferences(this.preferences);
    this.emit("prefs:saved", { preferences: this.preferences });
    return { valid: true, preferences: clonePreferences(this.preferences) };
  }
}

export { COMM_STYLE_OPTIONS, COLLAB_MODE_OPTIONS, SLIDER_KEYS, SLIDER_TOOLTIPS, descriptorFor };
