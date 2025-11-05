(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});
  const DEFAULT_URL = "reports/kpi_report.json";
  const hasFetch = typeof global.fetch === "function";

  function asMetric(metric) {
    if (!metric || typeof metric !== "object") return "n/a";
    const value = metric.value !== undefined && metric.value !== null ? String(metric.value) : "";
    const target = typeof metric.target === "string" && metric.target ? metric.target : "";
    if (value && target) return `${value} (${target})`;
    if (target) return target;
    if (value) return value;
    return "n/a";
  }

  function summariseRuns(runs) {
    if (!Array.isArray(runs) || runs.length === 0) return "none";
    return runs
      .map((run) => {
        if (!run || typeof run !== "object") return "- run";
        const id = run.id || run.number || "run";
        const status = run.status || "unknown";
        const pieces = [`${id} (${status})`];
        if (run.workflow) pieces.push(run.workflow);
        if (run.timestamp) pieces.push(run.timestamp);
        if (run.url) pieces.push(run.url);
        return `- ${pieces.join(" — ")}`;
      })
      .join("\n");
  }

  function render(container, report) {
    if (!report || typeof report !== "object") {
      container.textContent = "KPI report not available.";
      return;
    }
    const lines = [
      "KPI Snapshot",
      `Timestamp: ${report.timestamp || "n/a"}`,
      `Commit: ${report.commit || "n/a"}`,
      `PRI: ${asMetric(report.pri)}`,
      `HAL: ${asMetric(report.hal)}`,
      `AUD: ${asMetric(report.aud)}`,
      "",
      `CI Runs:`,
      summariseRuns(report.ci_runs),
    ];
    container.textContent = lines.join("\n");
    container.setAttribute("data-kpi-panel-ready", "true");
  }

  async function loadReport(url) {
    if (!hasFetch) return null;
    const response = await fetch(url, { cache: "no-store" });
    if (!response.ok) return null;
    return response.json();
  }

  ns.initKpiPanel = function initKpiPanel(container, options) {
    const target = container || null;
    if (!target) return { refresh() {} };
    target.classList.add("kpi-panel");
    const opts = options || {};
    const url = typeof opts.url === "string" && opts.url ? opts.url : DEFAULT_URL;

    async function refresh() {
      try {
        const report = await loadReport(url);
        render(target, report);
      } catch (error) {
        console.warn("Failed to load KPI report", error); // eslint-disable-line no-console
        target.textContent = "KPI report not available.";
      }
    }

    refresh();
    return { refresh };
  };
})(typeof window !== "undefined" ? window : globalThis);
