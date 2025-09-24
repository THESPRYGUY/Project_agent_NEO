import { TraitsPanel, createManualEnvelope, TRAIT_KEYS } from "../src/neo_agent/ui/traits_panel";
import { applyTraitsKnobs } from "../src/neo_agent/runtime/routing_map";

const results: Array<{ name: string; status: string; error?: string }> = [];

function test(name: string, fn: () => void) {
  try {
    fn();
    results.push({ name, status: "passed" });
  } catch (error) {
    const message = error && typeof error === "object" && "message" in error ? (error as Error).message : String(error);
    results.push({ name, status: "failed", error: message });
  }
}

function assert(condition: unknown, message: string) {
  if (!condition) {
    throw new Error(message);
  }
}

test("suggest accept and save keeps provenance", () => {
  const events: string[] = [];
  const panel = new TraitsPanel({ telemetry: (event) => events.push(event.action), agentId: "agent-42" });
  const suggestion = panel.previewSuggestion("entj");
  assert(suggestion !== null, "expected suggestion for ENTJ");
  panel.acceptSuggestion();
  const saved = panel.save();
  assert(saved.valid, "expected save to succeed");
  assert(saved.envelope && saved.envelope.provenance === "mbti_suggested", "provenance should remain suggested");
  assert(saved.envelope && saved.envelope.traits.proactive === 85, "traits should match suggestion values");
  assert(events.includes("traits:suggested"), "suggestion should emit telemetry");
  assert(events.includes("traits:accepted"), "accept should emit telemetry");
  assert(events.includes("traits:saved"), "save should emit telemetry");
});

test("manual envelope produces balanced knobs", () => {
  const manualEnvelope = createManualEnvelope();
  manualEnvelope.traits.detail_oriented = 55;
  manualEnvelope.traits.proactive = 72;
  manualEnvelope.traits.experimental = 40;

  const panel = new TraitsPanel({ initial: manualEnvelope });
  panel.setTraitValue("strategic", 77);
  const knobs = applyTraitsKnobs(panel.toEnvelope().traits);
  assert(knobs.plan_depth >= 3 && knobs.plan_depth <= 7, "plan depth scaled from traits");
  assert(knobs.parallel_branches >= 1, "parallel branches minimum");
  assert(["balanced", "detailed", "concise"].includes(knobs.draft_verbosity), "verbosity classification");
  assert(typeof knobs.alt_paths === "boolean", "alt paths should be boolean");
  panel.setTraitValue("empathetic", 90);
  panel.setTraitValue("efficient", 35);
  const save = panel.save();
  assert(save.valid, "manual save should still succeed");
  assert(save.envelope?.provenance === "manual", "manual provenance stays manual");
});

test("editing suggestions updates provenance", () => {
  const panel = new TraitsPanel();
  panel.previewSuggestion("enfp");
  panel.acceptSuggestion("accept_and_tweak");
  panel.setTraitValue("empathetic", 92);
  const saved = panel.save();
  assert(saved.envelope?.provenance === "mbti_suggested+edited", "editing suggested values updates provenance");
});

test("reset behaviours restore values", () => {
  const panel = new TraitsPanel();
  panel.previewSuggestion("intj");
  panel.acceptSuggestion();
  const accepted = panel.getAcceptedSuggestion();
  assert(accepted !== null, "expected stored accepted suggestion");
  panel.setTraitValue("experimental", 55);
  panel.resetToSuggested();
  assert(panel.getTraitValue("experimental") === accepted!.traits.experimental, "reset to suggested should restore value");
  const savedEnvelope = panel.save().envelope!;
  panel.setTraitValue("efficient", 10);
  panel.resetToLastSaved();
  assert(panel.getTraitValue("efficient") === savedEnvelope.traits.efficient, "reset to last saved restores saved value");
});

test("chip metadata maintains accessibility hints", () => {
  const panel = new TraitsPanel();
  const chips = panel.getChipMetadata();
  assert(chips.length === TRAIT_KEYS.length, "chip metadata returns all traits");
  for (const chip of chips) {
    const wordCount = chip.tooltip.trim().split(/\s+/).length;
    assert(wordCount <= 12, "tooltips remain concise for accessibility");
    assert(chip.ariaLabel.includes(String(chip.value)), "aria label contains value");
  }
  panel.focusTrait("proactive");
  assert(panel.getFocusedTrait() === "proactive", "focus moves to requested trait");
  const next = panel.moveFocus(1);
  assert(next !== "", "cycle focus should return a trait key");
  assert(TRAIT_KEYS.includes(next as typeof TRAIT_KEYS[number]), "focused trait must be valid key");
});

const failures = results.filter((item) => item.status !== "passed");
if (failures.length) {
  console.error(JSON.stringify({ status: "failed", results }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: "passed", results }, null, 2));
