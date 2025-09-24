import { NaicsPanel } from "../src/intake/naics-panel";
import { DomainSelector } from "../src/intake/domain-selector";
import naicsData from "../data/naics/naics-2022.json" assert { type: "json" };

const results = [];

function test(name, fn) {
  try {
    fn();
    results.push({ name, status: "passed" });
  } catch (error) {
    results.push({ name, status: "failed", error: error && error.message ? error.message : String(error) });
  }
}

function assert(condition, message) {
  if (!condition) {
    throw new Error(message);
  }
}

test("cascader exposes hierarchical columns and selections", () => {
  const events = [];
  const panel = new NaicsPanel(null, naicsData.tree, { telemetry: (event) => events.push(event) });
  const initialColumns = panel.open();
  assert(initialColumns[0].some((node) => node.code === "51"), "expected top-level sector in first column");
  panel.focus("51");
  const focusedColumns = panel.getColumns();
  assert(focusedColumns.length >= 2, "focusing a sector should expose a second column");
  const level2 = panel.select("51");
  assert(level2 && level2.level === 2, "should allow selection at level 2");
  const level3 = panel.select("518");
  assert(level3 && level3.level === 3, "should allow selection at level 3");
  const level5 = panel.select("51821");
  assert(level5 && level5.level === 5, "should allow selection at level 5");
  const level6 = panel.select("518210");
  assert(level6 && level6.level === 6, "should allow selection at level 6");
  const trail = panel.getTrail();
  assert(trail.length === 5, "trail should include ancestors for selected node");
  const telemetryNames = events.map((event) => `${event.step}:${event.action}`);
  assert(telemetryNames.includes("naics:opened"), "open should emit telemetry");
  assert(telemetryNames.includes("naics:selected"), "select should emit telemetry");
});

test("search returns relevant NAICS codes and integrates with domain selector", () => {
  const panel = new NaicsPanel(null, naicsData.tree);
  const searchResults = panel.search("data processing");
  assert(searchResults.some((node) => node.code === "51821"), "search should surface 51821 by title");
  const codeSearch = panel.search("518210");
  assert(codeSearch.length && codeSearch[0].code === "518210", "search should match explicit code");
  const selection = panel.select("51821");
  const selector = new DomainSelector();
  selector.setTopLevel("Sector Domains");
  selector.setSubdomain("Energy & Infrastructure");
  selector.setTags(["Hyperscale"]);
  selector.setNaics(selection);
  assert(selector.canSave(), "domain selector should validate once NAICS is set");
});

const failures = results.filter((item) => item.status !== "passed");
if (failures.length) {
  console.error(JSON.stringify({ status: "failed", results }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: "passed", results }, null, 2));
