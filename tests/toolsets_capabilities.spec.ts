import {
  CapabilitiesPanel,
  createDefaultToolsetsPayload,
  type CapabilityKey,
} from "../src/neo_agent/ui/capabilities_panel";
import { applyToolsetsRouting } from "../src/neo_agent/runtime/routing_map";

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

test("capabilities selection emits telemetry and enforces at least one", () => {
  const telemetry: string[] = [];
  const panel = new CapabilitiesPanel({ telemetry: (event) => telemetry.push(event.action), agentId: "agent-123" });
  panel.toggleCapability("analysis_modeling");
  panel.toggleCapability("communication_reporting");
  const saved = panel.save();
  assert(saved.valid, "save should be valid with capabilities selected");
  const capabilities = saved.capabilities as CapabilityKey[];
  assert(capabilities.includes("analysis_modeling"), "analysis modeling capability retained");
  assert(telemetry.includes("toolsets:capability_selected"), "telemetry emitted for capability toggles");
});

test("routing merges capability routes and flags approvals for prod ops", () => {
  const payload = createDefaultToolsetsPayload();
  payload.capabilities = ["reasoning_planning", "orchestration"];
  payload.connectors = [
    {
      name: "email",
      scopes: ["read/*", "send:external"],
    },
  ];
  payload.ops.env = "prod";
  payload.ops.dry_run = false;
  const routing = applyToolsetsRouting(payload);
  assert(routing.approvals_required === true, "prod env or optional scopes require approval");
  assert(routing.routes.roles.includes("Planner"), "planner role included for reasoning capability");
  assert(routing.routes.roles.includes("Builder"), "builder route included for orchestration");
  assert(routing.routes.approvals.includes("ops:prod"), "ops approval surfaced");
  assert(!routing.routes.warnings.length, "connectors present so no warning");
});

test("missing connectors with orchestration produces warning", () => {
  const payload = createDefaultToolsetsPayload();
  payload.capabilities = ["orchestration"];
  payload.connectors = [];
  const routing = applyToolsetsRouting(payload);
  assert(routing.routes.warnings.length === 1, "warning emitted for missing connector scopes");
  assert(routing.routes.warnings[0].includes("Orchestration"), "warning references orchestration");
});

const failures = results.filter((item) => item.status !== "passed");
if (failures.length) {
  console.error(JSON.stringify({ status: "failed", results }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: "passed", results }, null, 2));
