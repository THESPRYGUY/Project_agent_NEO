(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  function formatList(items, key) {
    if (!Array.isArray(items) || !items.length) return "[]";
    return items
      .map((item) => {
        if (typeof item === "string") return `- ${item}`;
        if (item && typeof item === "object") {
          const path = item.json_path || item.intake_field || key || "";
          const after = item.after !== undefined ? JSON.stringify(item.after) : JSON.stringify(item.value);
          return `- ${path}: ${after}`;
        }
        return `- ${String(item)}`;
      })
      .join("\n");
  }

  ns.initResultsPanel = function initResultsPanel(container) {
    if (!container) return { render() {} };
    container.classList.add("intake-results");
    container.style.display = "none";

    function render(result) {
      if (!result) {
        container.textContent = "";
        container.style.display = "none";
        return;
      }
      const { mode, changed_files, diff_report, mapping_report } = result;
      const parts = [];
      parts.push(`Mode: ${mode || "dry-run"}`);
      parts.push(`Changed files: ${(changed_files || []).join(", ") || "none"}`);
      if (Array.isArray(mapping_report) && mapping_report.length) {
        parts.push("Mapping Report:");
        parts.push(formatList(mapping_report, "intake_field"));
      }
      if (Array.isArray(diff_report) && diff_report.length) {
        parts.push("Diff Report:");
        diff_report.forEach((entry) => {
          const name = entry.pack_file || "pack";
          parts.push(`  ${name}`);
          parts.push(formatList(entry.changes || [], "json_path"));
        });
      }
      container.textContent = parts.join("\n");
      container.style.display = "block";
    }

    return { render };
  };
})(typeof window !== "undefined" ? window : globalThis);
