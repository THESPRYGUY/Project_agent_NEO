import { describe, expect, it } from "vitest";
import { roleFitScore } from "../../src/persona/math";

describe("roleFitScore", () => {
  it("honours explicit domain overrides over derived values", () => {
    const result = roleFitScore({
      domain: "Finance",
      role: "Enterprise Analyst",
      agentCode: "ENTJ",
      businessFunctionKey: "ENGINEERING_PLATFORM",
    });

    expect(result.domain).toBe("Finance");
    expect(result.domainSource).toBe("override");
    expect(result.factors.some((line) => line.includes("Strong prior"))).toBe(true);
    expect(result.factors.some((line) => line.includes("Domain inferred"))).toBe(false);
    expect(result.score).toBeGreaterThan(80);
  });

  it("derives domain from business function mapping when override missing", () => {
    const result = roleFitScore({
      role: null,
      domain: null,
      agentCode: "INTJ",
      businessFunctionKey: "ENGINEERING_PLATFORM",
    });

    expect(result.domain).toBe("Technology");
    expect(result.domainSource).toBe("derived");
    expect(result.factors).toContain("Domain inferred from Business Function: Technology.");
    expect(result.factors.some((line) => line.includes("Domain match"))).toBe(true);
    expect(result.score).toBeGreaterThanOrEqual(80);
  });

  it("applies role-only priors when no domain is available", () => {
    const result = roleFitScore({
      domain: null,
      role: "ENG:PLATFORM",
      agentCode: "INTJ",
      businessFunctionKey: "UNKNOWN_FN",
    });

    expect(result.domain).toBeNull();
    expect(result.domainSource).toBe("none");
    expect(result.factors).toContain("Role prior used (no domain).");
    expect(result.factors.some((line) => line.includes("Strong match"))).toBe(true);
    expect(result.factors.some((line) => line.includes("generic persona baseline"))).toBe(false);
    expect(result.score).toBeGreaterThan(80);
  });
});
