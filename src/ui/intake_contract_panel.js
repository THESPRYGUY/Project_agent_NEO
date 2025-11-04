(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  function textInput(selector) {
    return document.querySelector(selector);
  }

  function setInputValue(input, value) {
    if (!input) return;
    input.value = value;
    input.dispatchEvent(new Event("input", { bubbles: true }));
  }

  function serialiseRoles(state) {
    return (state.rbac?.roles || []).join(", ");
  }

  function serialiseActions(state) {
    return (state.human_gate?.actions || []).join(", ");
  }

  function serialiseArray(items) {
    return (items || []).join(", ");
  }

  function ensureIsoTimestamp() {
    try {
      return new Date().toISOString();
    } catch {
      return "1970-01-01T00:00:00Z";
    }
  }

  function initPanel() {
    const panel = document.querySelector("[data-intake-panel]");
    if (!panel || !ns.loadSchema) return;

    const statusEl = panel.querySelector("[data-intake-status]");
    const memoryContainer = panel.querySelector("[data-intake-memory]");
    const connectorsContainer = panel.querySelector("[data-intake-connectors]");
    const governanceContainer = panel.querySelector("[data-intake-governance]");
    const rbacContainer = panel.querySelector("[data-intake-rbac]");
    const resultsContainer = panel.querySelector("[data-intake-results]");
    const dryRunBtn = panel.querySelector("[data-intake-dry-run]");
    const applyBtn = panel.querySelector("[data-intake-apply]");

    const hiddenPayload = document.querySelector("[data-intake-payload]");
    const hiddenConnectors = document.querySelector("[data-intake-connectors-input]");
    const hiddenHg = document.querySelector("[data-intake-hg-input]");
    const hiddenScopes = document.querySelector("[data-intake-memory-scopes]");
    const hiddenRetention = document.querySelector("[data-intake-memory-retention]");
    const hiddenPermissions = document.querySelector("[data-intake-memory-permissions]");
    const hiddenRules = document.querySelector("[data-intake-memory-rules]");
    const hiddenInitial = document.querySelector("[data-intake-memory-initial]");
    const hiddenOptional = document.querySelector("[data-intake-memory-optional]");
    const hiddenDataSources = document.querySelector("[data-intake-data-sources]");
    const hiddenPii = document.querySelector("[data-intake-pii]");
    const hiddenRiskTags = document.querySelector("[data-intake-risk-tags]");
    const hiddenClassification = document.querySelector("[data-intake-classification]");
    const hiddenRbac = document.querySelector("[data-intake-rbac-roles]");

    const results = ns.initResultsPanel ? ns.initResultsPanel(resultsContainer) : { render() {} };
    const state = {
      memory: {},
      connectors: [],
      data_sources: [],
      governance: {},
      rbac: {},
      human_gate: {},
      metadata: {},
      determinism: {},
    };

    function setStatus(message, tone) {
      if (!statusEl) return;
      statusEl.textContent = message || "";
      statusEl.setAttribute("data-tone", tone || "info");
    }

    function syncHidden(payload, sample) {
      if (hiddenPayload) setInputValue(hiddenPayload, JSON.stringify(payload));
      if (hiddenConnectors) setInputValue(hiddenConnectors, JSON.stringify(payload.connectors || []));
      if (hiddenHg) setInputValue(hiddenHg, serialiseActions(state));
      if (hiddenScopes) setInputValue(hiddenScopes, serialiseArray(state.memory.scopes || []));
      if (hiddenRetention) setInputValue(hiddenRetention, JSON.stringify(payload.memory.retention || {}));
      if (hiddenPermissions) setInputValue(hiddenPermissions, JSON.stringify(payload.memory.permissions || {}));
      if (hiddenRules) setInputValue(hiddenRules, JSON.stringify(payload.memory.writeback_rules || []));
      if (hiddenInitial) setInputValue(hiddenInitial, serialiseArray(sample.memory?.initial_memory_packs || []));
      if (hiddenOptional) setInputValue(hiddenOptional, serialiseArray(sample.memory?.optional_packs || []));
      if (hiddenDataSources) setInputValue(hiddenDataSources, serialiseArray(payload.data_sources || []));
      if (hiddenPii) setInputValue(hiddenPii, serialiseArray(state.governance.pii_flags || []));
      if (hiddenRiskTags) setInputValue(hiddenRiskTags, serialiseArray(state.governance.risk_register_tags || []));
      if (hiddenClassification) setInputValue(hiddenClassification, state.governance.classification_default || "");
      if (hiddenRbac) setInputValue(hiddenRbac, serialiseRoles(state));
    }

    function buildPayload(sample) {
      const payload = ns.clone ? ns.clone(sample) : JSON.parse(JSON.stringify(sample));
      payload.metadata = payload.metadata || {};
      payload.metadata.submitted_at = ensureIsoTimestamp();
      payload.memory = payload.memory || {};
      payload.memory.scopes = (state.memory.scopes || []).slice();
      payload.memory.retention = ns.clone ? ns.clone(state.memory.retention) : JSON.parse(JSON.stringify(state.memory.retention || {}));
      payload.memory.permissions = ns.clone ? ns.clone(state.memory.permissions) : JSON.parse(JSON.stringify(state.memory.permissions || {}));
      payload.memory.writeback_rules = (state.memory.writeback_rules || []).slice();

      payload.connectors = (state.connectors || [])
        .filter((conn) => conn.selected !== false)
        .map((conn) => ({
          name: conn.name,
          enabled: Boolean(conn.enabled),
          scopes: Array.isArray(conn.scopes) ? conn.scopes.slice() : [],
          secret_ref: conn.secret_ref || "",
        }));

      payload.data_sources = (state.data_sources || []).slice();

      payload.governance = payload.governance || {};
      payload.governance.classification_default = state.governance.classification_default || payload.governance.classification_default;
      payload.governance.pii_flags = (state.governance.pii_flags || []).slice();
      payload.governance.risk_register_tags = (state.governance.risk_register_tags || []).slice();

      payload.rbac = payload.rbac || {};
      payload.rbac.roles = (state.rbac.roles || []).slice();

      payload.human_gate = payload.human_gate || {};
      payload.human_gate.actions = (state.human_gate.actions || []).slice();

      return payload;
    }

    function validateState(payload) {
      if (!payload.connectors.length) {
        throw new Error("At least one connector must be selected.");
      }
      if (!payload.governance.pii_flags.length) {
        throw new Error("Select at least one PII flag.");
      }
      if (!payload.human_gate.actions.length) {
        throw new Error("Select at least one human gate action.");
      }
      if (!payload.rbac.roles.length) {
        throw new Error("Select at least one RBAC role.");
      }
    }

    function attachActions(schema) {
      if (!dryRunBtn || !applyBtn) return;
      const sample = schema.sample || {};
      dryRunBtn.addEventListener("click", async (event) => {
        event.preventDefault();
        try {
          dryRunBtn.disabled = true;
          applyBtn.disabled = true;
          setStatus("Running dry-run mapper…", "info");
          const payload = buildPayload(sample);
          syncHidden(payload, sample);
          validateState(payload);
          const response = await ns.runMapper(payload, { dryRun: true });
          results.render({
            mode: "dry-run",
            changed_files: response.changed_files || [],
            mapping_report: response.mapping_report || [],
            diff_report: response.diff_report || [],
          });
          setStatus(`Dry-run complete (${(response.mapping_report || []).length} mappings)`, "success");
        } catch (error) {
          const message = error && error.response && error.response.errors ? error.response.errors.join("; ") : (error.message || "Dry-run failed");
          setStatus(message, "error");
          results.render(null);
        } finally {
          dryRunBtn.disabled = false;
          applyBtn.disabled = false;
        }
      });

      applyBtn.addEventListener("click", async (event) => {
        event.preventDefault();
        try {
          dryRunBtn.disabled = true;
          applyBtn.disabled = true;
          setStatus("Applying mapper to packs…", "info");
          const payload = buildPayload(sample);
          syncHidden(payload, sample);
          validateState(payload);
          const response = await ns.runMapper(payload, { dryRun: false });
          results.render({
            mode: "apply",
            changed_files: response.changed_files || [],
            mapping_report: response.mapping_report || [],
            diff_report: response.diff_report || [],
          });
          setStatus(`Apply complete (updated ${response.changed_files.length} files)`, "success");
        } catch (error) {
          const message = error && error.response && error.response.errors ? error.response.errors.join("; ") : (error.message || "Apply failed");
          setStatus(message, "error");
          results.render(null);
        } finally {
          dryRunBtn.disabled = false;
          applyBtn.disabled = false;
        }
      });
    }

    ns.loadSchema()
      .then((schema) => {
        const defaults = schema.defaults || {};
        const sample = schema.sample || {};
        state.memory = sample.memory || {};
        state.connectors = (defaults.connectors || []).map(ns.clone ? ns.clone : (x) => JSON.parse(JSON.stringify(x)));
        state.data_sources = (sample.data_sources || defaults.data_sources || []).slice();
        state.governance = sample.governance || {
          classification_default: (defaults.governance || {}).classification_default?.default || "confidential",
          pii_flags: (defaults.governance || {}).pii_flags || ["none"],
          risk_register_tags: [],
        };
        state.rbac = sample.rbac || { roles: (defaults.roles || []).slice() };
        state.human_gate = sample.human_gate || { actions: (defaults.human_gate_actions || []).slice() };

        if (ns.initMemoryForm) {
          ns.initMemoryForm(memoryContainer, state, defaults.memory || {}, () => {
            const payload = buildPayload(sample);
            syncHidden(payload, sample);
          });
        }
        if (ns.initConnectorsForm) {
          ns.initConnectorsForm(connectorsContainer, state, {
            connectors: defaults.connectors || [],
            data_sources: defaults.data_sources || [],
          }, () => {
            const payload = buildPayload(sample);
            syncHidden(payload, sample);
          });
        }
        if (ns.initGovernanceForm) {
          ns.initGovernanceForm(governanceContainer, state, {
            classification_default: {
              default: state.governance.classification_default,
            },
            classification_options: defaults.governance?.classification_default_options || schema.contract?.properties?.governance?.properties?.classification_default?.enum || ["public", "internal", "confidential", "restricted"],
            pii_flags_options: defaults.governance?.pii_flags_options || schema.contract?.properties?.governance?.properties?.pii_flags?.items?.enum || ["none"],
            pii_flags: state.governance.pii_flags,
          }, () => {
            const payload = buildPayload(sample);
            syncHidden(payload, sample);
          });
        }
        if (ns.initRbacHitlForm) {
          ns.initRbacHitlForm(rbacContainer, state, {
            roles: defaults.roles || [],
            human_gate_actions: defaults.human_gate_actions || [],
          }, () => {
            const payload = buildPayload(sample);
            syncHidden(payload, sample);
          });
        }

        syncHidden(buildPayload(sample), sample);
        attachActions(schema);
        setStatus("Schema loaded. Configure fields and run the mapper.", "success");
      })
      .catch((error) => {
        console.error("Failed to load intake schema", error);
        setStatus("Failed to load intake schema. Check server logs.", "error");
        if (dryRunBtn) dryRunBtn.disabled = true;
        if (applyBtn) applyBtn.disabled = true;
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initPanel, { once: true });
  } else {
    initPanel();
  }
})(typeof window !== "undefined" ? window : globalThis);
