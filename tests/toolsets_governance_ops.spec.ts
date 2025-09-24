import { GovernanceOpsPanel } from "../src/neo_agent/ui/governance_ops_panel";

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

test("redaction flags remain immutable", () => {
  const panel = new GovernanceOpsPanel();
  const flags = panel.getRedactionFlags();
  flags.pop();
  const save = panel.save();
  assert(save.valid, "governance save should be valid by default");
  assert(save.governance?.redaction.length === 2, "redaction flags preserved");
  assert(save.governance?.redaction.includes("mask_pii"), "mask flag present");
});

test("prod environment enforces dry-run disabled and banner", () => {
  const telemetry: string[] = [];
  const panel = new GovernanceOpsPanel({ telemetry: (event) => telemetry.push(event.action) });
  panel.setEnvironment("prod");
  panel.setDryRun(true);
  const banner = panel.getOpsBanner();
  assert(banner !== null && banner.includes("Prod"), "prod banner displayed");
  const save = panel.save();
  assert(save.approvalsRequired, "prod ops require approval");
  assert(save.ops?.dry_run === false, "dry-run forced off for prod");
  assert(telemetry.includes("toolsets:ops_changed"), "ops telemetry emitted");
});

test("latency and cost clamp to zero or above", () => {
  const panel = new GovernanceOpsPanel();
  panel.setLatencySlo(-10);
  panel.setCostBudget(-5);
  const saved = panel.save();
  assert(saved.valid, "negative values should be clamped not rejected");
  assert(saved.ops?.latency_slo_ms === 0, "latency clamped to zero");
  assert(saved.ops?.cost_budget_usd === 0, "cost clamped to zero");
});

const failures = results.filter((item) => item.status !== "passed");
if (failures.length) {
  console.error(JSON.stringify({ status: "failed", results }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: "passed", results }, null, 2));
