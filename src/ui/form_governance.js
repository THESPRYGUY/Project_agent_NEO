(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  function asArray(value) {
    if (!value) return [];
    return Array.isArray(value) ? value.slice() : [value];
  }

  function renderPiiFlags(container, state, options, emit) {
    const hasNoneOption = options.includes("none");
    const existing = container.querySelector("[data-intake-pii-chips]");
    if (existing) existing.remove();

    const chips = document.createElement("div");
    chips.className = "intake-chips";
    chips.setAttribute("data-intake-pii-chips", "true");

    options.forEach((flag) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "intake-chip";
      chip.textContent = flag;
      const selected = Array.isArray(state.pii_flags) && state.pii_flags.includes(flag);
      chip.setAttribute("data-selected", selected ? "true" : "false");
      chip.addEventListener("click", () => {
        const current = Array.isArray(state.pii_flags) ? state.pii_flags.slice() : [];
        let next;
        if (flag === "none") {
          next = ["none"];
        } else {
          const set = new Set(current);
          set.delete("none");
          if (selected) {
            set.delete(flag);
          } else {
            set.add(flag);
          }
          if (!set.size && hasNoneOption) {
            set.add("none");
          }
          next = Array.from(set);
        }
        state.pii_flags = next;
        emit();
        renderPiiFlags(container, state, options, emit);
      });
      chips.appendChild(chip);
    });

    container.appendChild(chips);
  }

  function renderClassificationChips(container, state, options, select, emit) {
    container.innerHTML = "";
    const chips = document.createElement("div");
    chips.className = "intake-chips";

    options.forEach((option) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "intake-chip";
      chip.textContent = option;
      const selected = state.classification_default === option;
      chip.setAttribute("data-selected", selected ? "true" : "false");
      chip.addEventListener("click", () => {
        if (state.classification_default === option) return;
        state.classification_default = option;
        if (select) select.value = option;
        emit();
        renderClassificationChips(container, state, options, select, emit);
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

    const classificationOptions =
      defaults.classification_options || ["public", "internal", "confidential", "restricted"];
    const piiOptions = defaults.pii_flags_options || ["none"];

    const initialPii = asArray(state.governance.pii_flags || defaults.pii_flags || ["none"]).filter(Boolean);
    let normalisedPii = Array.from(
      new Set(initialPii.filter((flag) => piiOptions.includes(flag)))
    );
    if (normalisedPii.length > 1 && normalisedPii.includes("none")) {
      normalisedPii = normalisedPii.filter((flag) => flag !== "none");
    }
    if (!normalisedPii.length && piiOptions.includes("none")) {
      normalisedPii = ["none"];
    }
    state.governance.pii_flags = normalisedPii;
    state.governance.risk_register_tags = asArray(state.governance.risk_register_tags || []);

    const title = document.createElement("h3");
    title.textContent = "Governance";
    container.appendChild(title);

    const banner = document.createElement("div");
    banner.className = "intake-governance-banner";
    const bannerLead = document.createElement("strong");
    bannerLead.textContent = "No impersonation enforced.";
    const bannerCopy = document.createElement("span");
    bannerCopy.textContent =
      " Agent responses must never impersonate real people or brands; this guardrail syncs with Safety Pack 05.";
    banner.appendChild(bannerLead);
    banner.appendChild(bannerCopy);
    container.appendChild(banner);

    const availableFlags = new Set(piiOptions);
    const presetCatalog = [
      {
        id: "open",
        label: "Open (public + none)",
        classification: "public",
        pii: ["none"],
        description: "Marketing or open data handling.",
      },
      {
        id: "internal",
        label: "Internal (internal + none)",
        classification: "internal",
        pii: ["none"],
        description: "Employees only, no stored PII.",
      },
      {
        id: "confidential",
        label: "Confidential PII (confidential + PII)",
        classification: "confidential",
        pii: ["PII"],
        description: "Customer or employee PII with masking.",
      },
      {
        id: "regulated",
        label: "Regulated (restricted + PII/PHI/PCI)",
        classification: "restricted",
        pii: ["PII", "PHI", "PCI"],
        description: "High-sensitivity regulated data.",
      },
    ]
      .filter((preset) => classificationOptions.includes(preset.classification))
      .map((preset) => {
        const flags = preset.pii.filter((flag) => availableFlags.has(flag));
        return Object.assign({}, preset, {
          pii: flags.length ? flags : availableFlags.has("none") ? ["none"] : flags,
        });
      });

    const presetButtons = [];
    function matchesPreset(preset) {
      if (!preset) return false;
      if (state.governance.classification_default !== preset.classification) return false;
      const currentFlags = new Set(state.governance.pii_flags || []);
      if (currentFlags.size !== preset.pii.length) return false;
      return preset.pii.every((flag) => currentFlags.has(flag));
    }

    function updatePresetActive() {
      presetButtons.forEach(({ element, preset }) => {
        element.setAttribute("data-selected", matchesPreset(preset) ? "true" : "false");
      });
    }

    const handleEmit = () => {
      updatePresetActive();
      emit();
    };

    const classBlock = document.createElement("div");
    classBlock.className = "intake-flex";
    const classTitle = document.createElement("strong");
    classTitle.textContent = "Classification Default";
    classBlock.appendChild(classTitle);

    const select = document.createElement("select");
    select.setAttribute("aria-label", "Classification default override");
    classificationOptions.forEach((option) => {
      const opt = document.createElement("option");
      opt.value = option;
      opt.textContent = option;
      if (option === state.governance.classification_default) {
        opt.selected = true;
      }
      select.appendChild(opt);
    });
    const classificationChipHolder = document.createElement("div");
    classificationChipHolder.className = "intake-governance-classification";
    renderClassificationChips(classificationChipHolder, state.governance, classificationOptions, select, handleEmit);
    select.addEventListener("change", () => {
      state.governance.classification_default = select.value;
      renderClassificationChips(classificationChipHolder, state.governance, classificationOptions, select, handleEmit);
      handleEmit();
    });
    const selectWrapper = document.createElement("div");
    selectWrapper.className = "intake-governance-select";
    selectWrapper.appendChild(select);
    classBlock.appendChild(classificationChipHolder);
    classBlock.appendChild(selectWrapper);
    container.appendChild(classBlock);

    const piiRow = document.createElement("div");
    piiRow.className = "intake-governance-pii";
    const piiTitle = document.createElement("strong");
    piiTitle.textContent = "PII Flags";
    piiRow.appendChild(piiTitle);
    renderPiiFlags(piiRow, state.governance, piiOptions, handleEmit);
    container.appendChild(piiRow);

    if (presetCatalog.length) {
      const presetRow = document.createElement("div");
      presetRow.className = "intake-governance-presets";
      const presetHeading = document.createElement("strong");
      presetHeading.textContent = "Quick governance presets";
      presetRow.appendChild(presetHeading);
      const presetHint = document.createElement("p");
      presetHint.textContent = "Apply curated combinations of classification and PII flags.";
      presetRow.appendChild(presetHint);
      const presetChipHolder = document.createElement("div");
      presetChipHolder.className = "intake-chips";
      presetCatalog.forEach((preset) => {
        const button = document.createElement("button");
        button.type = "button";
        button.className = "intake-chip intake-chip--preset";
        button.textContent = preset.label;
        if (preset.description) {
          button.title = preset.description;
        }
        button.addEventListener("click", () => {
          state.governance.classification_default = preset.classification;
          select.value = preset.classification;
          state.governance.pii_flags = preset.pii.slice();
          renderClassificationChips(
            classificationChipHolder,
            state.governance,
            classificationOptions,
            select,
            handleEmit
          );
          renderPiiFlags(piiRow, state.governance, piiOptions, handleEmit);
          handleEmit();
        });
        presetButtons.push({ element: button, preset });
        presetChipHolder.appendChild(button);
      });
      presetRow.appendChild(presetChipHolder);
      container.insertBefore(presetRow, classBlock);
    }

    const riskRow = document.createElement("div");
    riskRow.style.marginTop = "0.75rem";
    const riskTitle = document.createElement("strong");
    riskTitle.textContent = "Risk Register Tags";
    riskRow.appendChild(riskTitle);
    renderRiskTags(riskRow, state.governance, handleEmit);
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
      renderRiskTags(riskRow, state.governance, handleEmit);
      handleEmit();
    });
    advanced.appendChild(textarea);
    container.appendChild(advanced);

    updatePresetActive();
  };
})(typeof window !== "undefined" ? window : globalThis);
