import { PreferencesPanel, Preferences } from "../src/neo_agent/ui/preferences_panel";
import {
  applyPreferencesKnobs,
  applyTraitsKnobs,
  mergeRoutingKnobs,
} from "../src/neo_agent/runtime/routing_map";
import type { TraitsEnvelope } from "../src/neo_agent/ui/traits_panel";

const results: Array<{ name: string; status: string; error?: string }> = [];

function test(name: string, fn: () => void) {
  try {
    fn();
    results.push({ name, status: "passed" });
  } catch (error) {
    const message =
      error && typeof error === "object" && "message" in error
        ? (error as Error).message
        : String(error);
    results.push({ name, status: "failed", error: message });
  }
}

function assert(condition: unknown, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

const TRAIT_CONTEXT: TraitsEnvelope = {
  traits: {
    detail_oriented: 82,
    collaborative: 78,
    proactive: 88,
    strategic: 92,
    empathetic: 70,
    experimental: 64,
    efficient: 73,
  },
  provenance: "manual",
  version: "1.0",
};

test("slider values snap to increments and expose descriptors", () => {
  const panel = new PreferencesPanel();
  panel.setSliderValue("autonomy", 83);
  panel.setSliderValue("confidence", 12);
  assert(panel.getSliderValue("autonomy") === 85, "autonomy should snap to nearest 5");
  assert(panel.getSliderValue("confidence") === 10, "confidence snaps within bounds");
  assert(panel.getSliderDescriptor("autonomy") === "high", "descriptor reflects high autonomy");
  assert(panel.getSliderDescriptor("confidence") === "low", "descriptor reflects low confidence");
});

test("preset preview -> apply -> edit updates provenance", () => {
  const telemetry: string[] = [];
  const panel = new PreferencesPanel({
    traits: TRAIT_CONTEXT,
    telemetry: (event) => telemetry.push(event.action),
  });
  const preview = panel.previewPreset();
  assert(preview !== null, "expected preset preview from traits context");
  assert(telemetry.includes("prefs:preset_previewed"), "telemetry logs preset preview");
  panel.applyPreset("apply");
  const saved = panel.save();
  assert(saved.valid, "save should succeed after applying preset");
  assert(saved.preferences?.provenance === "preset_applied", "provenance reflects preset");
  panel.setSliderValue("confidence", saved.preferences!.confidence + 5);
  const edited = panel.save();
  assert(edited.preferences?.provenance === "preset_edited", "editing after preset updates provenance");
  assert(telemetry.includes("prefs:preset_applied"), "apply preset telemetry emitted");
  assert(telemetry.includes("prefs:saved"), "save telemetry emitted");
});

test("legacy conflict guard blocks incompatible confirmation gate", () => {
  const telemetry: string[] = [];
  const initial: Preferences = {
    autonomy: 20,
    confidence: 55,
    collaboration: 60,
    comm_style: "formal",
    collab_mode: "solo",
    prefs_knobs: {
      confirmation_gate: "none",
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
  };

  const panel = new PreferencesPanel({
    initial,
    telemetry: (event) => telemetry.push(event.action),
  });
  const result = panel.save();
  assert(result.valid, "save succeeds despite incoming conflict");
  assert(result.preferences?.prefs_knobs.confirmation_gate !== "none", "confirmation gate adjusted");
  assert(telemetry.includes("prefs:conflict_blocked"), "conflict telemetry emitted");
});

test("derived knobs map canonical slider values and merge with traits", () => {
  const panel = new PreferencesPanel();
  panel.setSliderValue("autonomy", 80);
  panel.setSliderValue("confidence", 60);
  panel.setSliderValue("collaboration", 90);
  panel.setCommStyle("executive_brief");
  panel.setCollabMode("pair_build");
  const saved = panel.save();
  assert(saved.valid, "save should succeed");
  const knobs = applyPreferencesKnobs(saved.preferences!);
  assert(knobs.confirmation_gate === "none", "high autonomy removes confirmation gate");
  assert(knobs.rec_depth === "balanced", "mid confidence remains balanced");
  assert(knobs.handoff_freq === "high", "high collaboration increases handoffs");
  assert(knobs.communication.include_call_to_action, "executive brief includes CTA");
  assert(knobs.collaboration.require_pair_confirmation, "pair build enforces confirmation");

  const traitsKnobs = applyTraitsKnobs({
    detail_oriented: 70,
    collaborative: 65,
    proactive: 80,
    strategic: 85,
    empathetic: 55,
    experimental: 60,
    efficient: 72,
  });
  const merged = mergeRoutingKnobs({ traits: traitsKnobs, preferences: knobs });
  assert(merged.plan_depth >= 3, "merged retains planner knobs");
  assert(merged.confirmation_gate === "none", "merged exposes preference gate");
  assert(merged.communication.include_call_to_action === true, "merged forwards communication directives");
});

const failures = results.filter((item) => item.status !== "passed");
if (failures.length) {
  console.error(JSON.stringify({ status: "failed", results }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: "passed", results }, null, 2));
