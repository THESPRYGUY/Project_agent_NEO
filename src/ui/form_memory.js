(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  function ensureArray(value) {
    return Array.isArray(value) ? value.slice() : [];
  }

  function normaliseRetention(retention) {
    const out = {};
    if (retention && typeof retention === "object") {
      Object.keys(retention).forEach((key) => {
        const entry = retention[key] || {};
        const days = Number(entry.retention_days);
        out[key] = { retention_days: Number.isFinite(days) && days > 0 ? days : 30 };
      });
    }
    return out;
  }

  function clonePermissions(permissions) {
    const out = {};
    if (permissions && typeof permissions === "object") {
      Object.entries(permissions).forEach(([role, cfg]) => {
        if (!cfg || typeof cfg !== "object") return;
        out[role] = {
          read: ensureArray(cfg.read),
          write: ensureArray(cfg.write),
        };
      });
    }
    return out;
  }

  function createChip(label, selected, onToggle) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "intake-chip";
    chip.setAttribute("data-selected", selected ? "true" : "false");
    chip.textContent = label;
    chip.addEventListener("click", () => {
      const next = chip.getAttribute("data-selected") !== "true";
      chip.setAttribute("data-selected", next ? "true" : "false");
      if (typeof onToggle === "function") onToggle(next);
    });
    return chip;
  }

  function renderScopes(section, state, defaults, emit) {
    const chips = document.createElement("div");
    chips.className = "intake-chips";
    const uniqueScopes = Array.from(new Set([].concat(defaults || [], state.scopes || [])));
    uniqueScopes.sort((a, b) => a.localeCompare(b));
    uniqueScopes.forEach((scope) => {
      const chip = createChip(scope, state.scopes.includes(scope), (selected) => {
        const next = new Set(state.scopes || []);
        if (selected) next.add(scope);
        else next.delete(scope);
        state.scopes = Array.from(next);
        emit();
      });
      chips.appendChild(chip);
    });
    section.appendChild(chips);

    const adder = document.createElement("div");
    adder.className = "intake-flex";
    adder.style.marginTop = "0.5rem";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Add custom scope (e.g., semantic:domain/*)";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Add Scope";
    btn.addEventListener("click", () => {
      const value = (input.value || "").trim();
      if (!value) return;
      if (!state.scopes.includes(value)) {
        state.scopes = (state.scopes || []).concat([value]);
        emit();
        const chip = createChip(value, true, (selected) => {
          const next = new Set(state.scopes || []);
          if (selected) next.add(value);
          else next.delete(value);
          state.scopes = Array.from(next);
          emit();
        });
        chips.appendChild(chip);
      }
      input.value = "";
    });
    adder.appendChild(input);
    adder.appendChild(btn);
    section.appendChild(adder);
  }

  function renderRetention(section, state, defaults, emit) {
    const table = document.createElement("table");
    table.className = "intake-matrix";
    const thead = document.createElement("thead");
    thead.innerHTML = "<tr><th>Scope</th><th>Retention (days)</th></tr>";
    table.appendChild(thead);
    const tbody = document.createElement("tbody");

    const keys = Array.from(new Set(Object.keys(defaults || {}).concat(Object.keys(state.retention || {}))));
    keys.sort((a, b) => a.localeCompare(b));

    keys.forEach((key) => {
      const row = document.createElement("tr");
      const label = document.createElement("td");
      label.textContent = key;
      const cell = document.createElement("td");
      const input = document.createElement("input");
      input.type = "number";
      input.min = "1";
      input.value = String((state.retention[key] || {}).retention_days || (defaults[key] || {}).retention_days || 90);
      input.addEventListener("change", () => {
        const next = Number(input.value);
        const days = Number.isFinite(next) && next > 0 ? Math.floor(next) : 30;
        state.retention[key] = { retention_days: days };
        emit();
      });
      cell.appendChild(input);
      row.appendChild(label);
      row.appendChild(cell);
      tbody.appendChild(row);
    });
    table.appendChild(tbody);
    section.appendChild(table);
  }

  function renderPermissions(section, state, defaults, emit) {
    const wrapper = document.createElement("div");
    wrapper.className = "intake-chips";
    const roles = Object.keys(defaults || {});
    roles.sort((a, b) => a.localeCompare(b));
    roles.forEach((role) => {
      const chip = createChip(role, Boolean(state.permissions[role]), (selected) => {
        if (selected) {
          state.permissions[role] = clonePermissions(defaults)[role] || { read: [], write: [] };
        } else {
          delete state.permissions[role];
        }
        emit();
      });
      chip.title = `Read: ${(defaults[role]?.read || []).join(", ")} | Write: ${(defaults[role]?.write || []).join(", ")}`;
      wrapper.appendChild(chip);
    });
    section.appendChild(wrapper);
  }

  function renderWriteback(section, state, defaults, emit) {
    const chips = document.createElement("div");
    chips.className = "intake-chips";
    const rules = Array.from(new Set([].concat(defaults || [], state.writeback_rules || [])));
    rules.forEach((rule) => {
      const chip = createChip(rule, state.writeback_rules.includes(rule), (selected) => {
        const next = new Set(state.writeback_rules || []);
        if (selected) next.add(rule);
        else next.delete(rule);
        state.writeback_rules = Array.from(next);
        emit();
      });
      chips.appendChild(chip);
    });
    section.appendChild(chips);
  }

  ns.initMemoryForm = function initMemoryForm(container, state, defaults, emit) {
    if (!container) return;
    const current = state.memory || {};
    state.memory = {
      scopes: ensureArray(current.scopes || defaults.scopes || []),
      retention: Object.assign({}, normaliseRetention(defaults.retention), normaliseRetention(current.retention)),
      permissions: Object.assign({}, clonePermissions(defaults.permissions), clonePermissions(current.permissions)),
      writeback_rules: ensureArray(current.writeback_rules || defaults.writeback_rules || []),
    };

    container.innerHTML = "";
    container.classList.add("intake-contract-card");

    const title = document.createElement("h3");
    title.textContent = "Memory";
    container.appendChild(title);

    const scopesSection = document.createElement("div");
    const scopesHeading = document.createElement("strong");
    scopesHeading.textContent = "Scopes";
    scopesSection.appendChild(scopesHeading);
    renderScopes(scopesSection, state.memory, defaults.scopes || [], () => emit());
    container.appendChild(scopesSection);

    const retentionSection = document.createElement("div");
    retentionSection.style.marginTop = "0.75rem";
    const retentionHeading = document.createElement("strong");
    retentionHeading.textContent = "Retention";
    retentionSection.appendChild(retentionHeading);
    renderRetention(retentionSection, state.memory, defaults.retention || {}, () => emit());
    container.appendChild(retentionSection);

    const permSection = document.createElement("div");
    permSection.style.marginTop = "0.75rem";
    const permHeading = document.createElement("strong");
    permHeading.textContent = "Permissions";
    permSection.appendChild(permHeading);
    renderPermissions(permSection, state.memory, defaults.permissions || {}, () => emit());
    container.appendChild(permSection);

    const ruleSection = document.createElement("div");
    ruleSection.style.marginTop = "0.75rem";
    const ruleHeading = document.createElement("strong");
    ruleHeading.textContent = "Writeback Rules";
    ruleSection.appendChild(ruleHeading);
    renderWriteback(ruleSection, state.memory, defaults.writeback_rules || [], () => emit());
    container.appendChild(ruleSection);
  };
})(typeof window !== "undefined" ? window : globalThis);
