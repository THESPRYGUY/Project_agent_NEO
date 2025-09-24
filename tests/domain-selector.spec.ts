import { DomainSelector, parsePrimaryDomain } from "../src/intake/domain-selector";
import { buildNaicsIndex } from "../src/intake/naics-index";
import naicsData from "../data/naics/naics-2022.json" assert { type: "json" };

const index = buildNaicsIndex(naicsData.tree);

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

function getNaics(code) {
  const node = index.byCode.get(code);
  if (!node) {
    throw new Error(`Missing NAICS code ${code} in test dataset.`);
  }
  return {
    code: node.code,
    title: node.title,
    level: node.level,
    version: node.version,
    path: node.path.slice(),
  };
}

test("cascades curated subdomains by top-level", () => {
  const selector = new DomainSelector();
  const topLevels = selector.getTopLevelOptions();
  assert(topLevels.includes("Sector Domains"), "expected Sector Domains option");
  selector.setTopLevel("Sector Domains");
  const sectorOptions = selector.getSubdomainOptions();
  assert(sectorOptions.length === 4, "expected four curated sector subdomains");
  selector.setSubdomain("Energy & Infrastructure");
  const suggestions = selector.getContextualTags();
  assert(suggestions.includes("data-center-strategy"), "expected nested energy tag suggestions");
});

test("enforces NAICS requirement for sector domains", () => {
  const events = [];
  const selector = new DomainSelector({ telemetry: (event) => events.push(event) });
  selector.setTopLevel("Sector Domains");
  selector.setSubdomain("Energy & Infrastructure");
  selector.addTag("ERCOT");
  selector.addTag("Ontario ");
  let validation = selector.validate();
  assert(!validation.valid, "sector domain should fail without NAICS");
  assert(validation.errors.naics === "Select an industry classification.", "expected NAICS error message");
  selector.setNaics(getNaics("51821"));
  validation = selector.validate();
  assert(validation.valid, "sector domain should validate with NAICS");
  const payload = selector.toRequestEnvelope();
  assert(payload.domain.naics && payload.domain.naics.code === "51821", "expected NAICS persisted in payload");
  assert(payload.industry.naics && payload.industry.naics.code === "51821", "expected industry section to persist NAICS");
  const telemetryNames = events.map((event) => `${event.step}:${event.action}`);
  assert(telemetryNames.includes("domain:changed"), "top-level change should emit telemetry");
  assert(telemetryNames.includes("domain:validated"), "validation should emit telemetry");
  assert(telemetryNames.includes("intake:saved"), "saving should emit telemetry");
});

test("normalizes tags to kebab-case without duplicates", () => {
  const selector = new DomainSelector();
  selector.setTopLevel("Technical Domains");
  selector.setSubdomain("Agentic RAG & Knowledge Graphs");
  selector.setTags([" Graph", "graph", "Graph Knowledge"]);
  const state = selector.getState();
  assert(state.tags.length === 2, "expected duplicate tags removed");
  assert(state.tags.includes("graph"), "expected normalized lower-case tag");
  assert(state.tags.includes("graph-knowledge"), "expected kebab-case tag");
});

test("parsePrimaryDomain enforces schema and normalization", () => {
  const input = {
    topLevel: "Sector Domains",
    subdomain: "Energy & Infrastructure",
    tags: ["ERCOT", "Ontario"],
    naics: getNaics("51821"),
  };
  const parsed = parsePrimaryDomain(input);
  assert(parsed.tags[0] === "ercot", "expected normalized tag during parsing");
  let threw = false;
  try {
    parsePrimaryDomain({ topLevel: "Sector Domains", subdomain: "Energy & Infrastructure", tags: [] });
  } catch (error) {
    threw = true;
  }
  assert(threw, "parsing should fail when required NAICS is missing");
});

const failures = results.filter((item) => item.status !== "passed");
if (failures.length) {
  console.error(JSON.stringify({ status: "failed", results }, null, 2));
  process.exit(1);
}
console.log(JSON.stringify({ status: "passed", results }, null, 2));
