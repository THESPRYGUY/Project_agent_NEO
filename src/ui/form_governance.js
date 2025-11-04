(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  function asArray(value) {
    if (!value) return [];
    return Array.isArray(value) ? value.slice() : [value];
  }

  function renderPiiFlags(container, state, options, emit) {
    const chips = document.createElement("div");
    chips.className = "intake-chips";
    options.forEach((flag) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "intake-chip";
      chip.textContent = flag;
      const selected = state.pii_flags.includes(flag);
      chip.setAttribute("data-selected", selected ? "true" : "false");
      chip.addEventListener("click", () => {
        const isSelected = chip.getAttribute("data-selected") === "true";
        const next = new Set(state.pii_flags);
        if (isSelected) next.delete(flag);
        else next.add(flag);
        state.pii_flags = Array.from(next);
        chip.setAttribute("data-selected", isSelected ? "false" : "true");
        emit();
      });
      chips.appendChild(chip);
    });
    container.appendChild(chips);
  }

  function renderRiskTags(container, state, emit) {
    container.innerHTML = "";
    const chips = document.createElement("div");
    chips.className = "intake-chips";
    (state.risk_register_tags || []).forEach((tag) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "intake-chip";
      chip.textContent = tag;
      chip.setAttribute("data-selected", "true");
      chip.addEventListener("click", () => {
        state.risk_register_tags = state.risk_register_tags.filter((item) => item !== tag);
        chip.remove();
        emit();
      });
      chips.appendChild(chip);
    });
    container.appendChild(chips);

    const addRow = document.createElement("div");
    addRow.className = "intake-flex";
    addRow.style.marginTop = "0.5rem";
    const input = document.createElement("input");
    input.type = "text";
    input.placeholder = "Add risk tag (lowercase, hyphenated)";
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = "Add Tag";
    btn.addEventListener("click", () => {
      const value = (input.value || "").trim();
      if (!value) return;
      if (!state.risk_register_tags.includes(value)) {
        state.risk_register_tags.push(value);
        emit();
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "intake-chip";
        chip.textContent = value;
        chip.setAttribute("data-selected", "true");
        chip.addEventListener("click", () => {
          state.risk_register_tags = state.risk_register_tags.filter((item) => item !== value);
          chip.remove();
          emit();
        });
        chips.appendChild(chip);
      }
      input.value = "";
    });
    addRow.appendChild(input);
    addRow.appendChild(btn);
    container.appendChild(addRow);
  }

  ns.initGovernanceForm = function initGovernanceForm(container, state, defaults, emit) {
    if (!container) return;
    container.innerHTML = "";
    container.classList.add("intake-contract-card");

    state.governance = state.governance || {};
    state.governance.classification_default =
      state.governance.classification_default ||
      defaults.classification_default?.default ||
      (defaults.classification_options || ["confidential"])[0];
    state.governance.pii_flags = asArray(state.governance.pii_flags || defaults.pii_flags || ["none"]);
    state.governance.risk_register_tags = asArray(state.governance.risk_register_tags || []);

    const title = document.createElement("h3");
    title.textContent = "Governance";
    container.appendChild(title);

    const classRow = document.createElement("div");
    classRow.className = "intake-flex";
    const classLabel = document.createElement("label");
    classLabel.textContent = "Classification Default";
    const select = document.createElement("select");
    (defaults.classification_options || ["public", "internal", "confidential", "restricted"]).forEach((option) => {
      const opt = document.createElement("option");
      opt.value = option;
      opt.textContent = option;
      if (option === state.governance.classification_default) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
    select.addEventListener("change", () => {
      state.governance.classification_default = select.value;
      emit();
    });
    classLabel.appendChild(select);
    classRow.appendChild(classLabel);
    container.appendChild(classRow);

    const piiRow = document.createElement("div");
    piiRow.style.marginTop = "0.75rem";
    const piiTitle = document.createElement("strong");
    piiTitle.textContent = "PII Flags";
    piiRow.appendChild(piiTitle);
    renderPiiFlags(piiRow, state.governance, defaults.pii_flags_options || [], emit);
    container.appendChild(piiRow);

    const riskRow = document.createElement("div");
    riskRow.style.marginTop = "0.75rem";
    const riskTitle = document.createElement("strong");
    riskTitle.textContent = "Risk Register Tags";
    riskRow.appendChild(riskTitle);
    renderRiskTags(riskRow, state.governance, emit);
    container.appendChild(riskRow);

    const advanced = document.createElement("details");
    advanced.style.marginTop = "0.75rem";
    const summary = document.createElement("summary");
    summary.textContent = "Advanced Overrides";
    advanced.appendChild(summary);
    const textarea = document.createElement("textarea");
    textarea.rows = 3;
    textarea.style.width = "100%";
    textarea.placeholder = "Custom tags (comma-separated)";
    textarea.addEventListener("blur", () => {
      const value = (textarea.value || "").trim();
      if (!value) return;
      const parts = value.split(",").map((item) => item.trim()).filter(Boolean);
      const merged = new Set(state.governance.risk_register_tags || []);
      parts.forEach((part) => merged.add(part));
      state.governance.risk_register_tags = Array.from(merged);
      emit();
      renderRiskTags(riskRow, state.governance, emit);
    });
    advanced.appendChild(textarea);
    container.appendChild(advanced);
  };
})(typeof window !== "undefined" ? window : globalThis);
