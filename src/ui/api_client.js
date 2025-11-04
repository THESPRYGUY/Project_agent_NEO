(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  async function runMapper(payload, options) {
    const body = {
      payload,
      dry_run: Boolean(options && options.dryRun),
    };
    const res = await fetch("/api/intake/mapper", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const text = await res.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch { data = null; }
    if (!res.ok || !data) {
      const error = new Error("mapper_failed");
      error.status = res.status;
      error.response = data || { message: text };
      throw error;
    }
    return data;
  }

  ns.runMapper = runMapper;
})(typeof window !== "undefined" ? window : globalThis);
