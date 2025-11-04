(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  async function loadSchema() {
    const res = await fetch("/api/intake/schema", { method: "GET", cache: "no-store" });
    if (!res.ok) {
      const text = await res.text().catch(() => "");
      const error = new Error("schema_fetch_failed");
      error.status = res.status;
      error.body = text;
      throw error;
    }
    return res.json();
  }

  function clone(value) {
    return value == null ? value : JSON.parse(JSON.stringify(value));
  }

  ns.loadSchema = loadSchema;
  ns.clone = clone;
})(typeof window !== "undefined" ? window : globalThis);
