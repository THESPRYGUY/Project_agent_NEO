import {
  ConnectorsPanel,
  detectOrchestrationWarning,
  summarizeConnectorScopes,
} from "../src/neo_agent/ui/connectors_panel";
import { createDefaultToolsetsPayload } from "../src/neo_agent/ui/capabilities_panel";

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

test("connector toggles capture approvals and telemetry", () => {
  const telemetry: string[] = [];
  const panel = new ConnectorsPanel({ telemetry: (event) => telemetry.push(event.action) });
  panel.toggleConnector("email");
  panel.setScope("email", "send:external", true);
  panel.addInstance("email", { label: "work", secret_ref: "vault://email/work" });
  const save = panel.save();
  assert(save.valid, "connector save should be valid");
  assert(save.approvalsRequired, "optional scope should require approval");
  const connectors = save.connectors ?? [];
  assert(connectors[0].instances && connectors[0].instances.length === 1, "instance persisted");
  assert(telemetry.includes("toolsets:connector_scope_requested"), "scope telemetry emitted");
  assert(panel.getApprovalBanner() !== null, "approval banner shown when connectors active");
});

test("orchestration warning helper detects missing connectors", () => {
  const payload = createDefaultToolsetsPayload();
  payload.capabilities = ["orchestration"];
  const warning = detectOrchestrationWarning(payload.capabilities, []);
  assert(warning !== null, "warning should surface without connector scopes");
  const banner = detectOrchestrationWarning(payload.capabilities, [
    { name: "email", scopes: ["read/*", "send:internal"] },
  ]);
  assert(banner === null, "warning cleared when connector scopes exist");
});

test("connector summary enumerates selected scopes", () => {
  const panel = new ConnectorsPanel();
  panel.toggleConnector("calendar");
  const summary = summarizeConnectorScopes(panel.getConnectors());
  assert(Array.isArray(summary.calendar), "calendar connector summarized");
  assert(summary.calendar.includes("read/*"), "default scope listed");
});

const failures = results.filter((item) => item.status !== "passed");
if (failures.length) {
  console.error(JSON.stringify({ status: "failed", results }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: "passed", results }, null, 2));
