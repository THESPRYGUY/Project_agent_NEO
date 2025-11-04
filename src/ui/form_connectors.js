(function (global) {
  const ns = global.NeoIntake || (global.NeoIntake = {});

  function cloneConnector(conn) {
    return {
      id: conn.id || conn.name || "",
      name: conn.name || conn.id || "",
      enabled: Boolean(conn.enabled),
      scopes: Array.isArray(conn.scopes) ? conn.scopes.slice() : [],
      secret_ref: conn.secret_ref || "",
      selected: conn.selected !== false,
    };
  }

  function createConnectorRow(connector, onChange) {
    const row = document.createElement("div");
    row.style.border = "1px solid #dbe2ef";
    row.style.borderRadius = "8px";
    row.style.padding = "0.6rem";
    row.style.marginBottom = "0.55rem";
    row.style.background = "#ffffff";

    const title = document.createElement("div");
    title.style.display = "flex";
    title.style.justifyContent = "space-between";
    title.style.alignItems = "center";
    const label = document.createElement("label");
    label.style.fontWeight = "600";
    const include = document.createElement("input");
    include.type = "checkbox";
    include.checked = connector.selected !== false;
    include.addEventListener("change", () => {
      connector.selected = include.checked;
      onChange();
    });
    label.appendChild(include);
    label.appendChild(document.createTextNode(" " + connector.name));
    title.appendChild(label);

    const enabledLabel = document.createElement("label");
    enabledLabel.style.fontSize = "0.85rem";
    enabledLabel.style.display = "inline-flex";
    enabledLabel.style.alignItems = "center";
    enabledLabel.style.gap = "0.3rem";
    enabledLabel.textContent = "";
    const enabledInput = document.createElement("input");
    enabledInput.type = "checkbox";
    enabledInput.checked = Boolean(connector.enabled);
    enabledInput.addEventListener("change", () => {
      connector.enabled = enabledInput.checked;
      onChange();
    });
    enabledLabel.appendChild(enabledInput);
    enabledLabel.appendChild(document.createTextNode("Enabled"));
    title.appendChild(enabledLabel);
    row.appendChild(title);

    const scopes = document.createElement("div");
    scopes.style.fontSize = "0.85rem";
    scopes.style.marginTop = "0.3rem";
    scopes.textContent = "Scopes: " + (connector.scopes || []).join(", ");
    row.appendChild(scopes);

    const secret = document.createElement("div");
    secret.style.fontSize = "0.8rem";
    secret.style.color = "#205072";
    secret.style.marginTop = "0.25rem";
    secret.textContent = connector.secret_ref || "";
    row.appendChild(secret);

    return row;
  }

  function renderDataSources(container, state, defaults, emit) {
    const chips = document.createElement("div");
    chips.className = "intake-chips";
    const combined = Array.from(new Set([].concat(defaults || [], state.data_sources || [])));
    combined.sort((a, b) => a.localeCompare(b));
    combined.forEach((src) => {
      const chip = document.createElement("button");
      chip.type = "button";
      chip.className = "intake-chip";
      chip.textContent = src;
      const selected = state.data_sources.includes(src);
      chip.setAttribute("data-selected", selected ? "true" : "false");
      chip.addEventListener("click", () => {
        const isSelected = chip.getAttribute("data-selected") === "true";
        const next = new Set(state.data_sources || []);
        if (isSelected) next.delete(src);
        else next.add(src);
        state.data_sources = Array.from(next);
        chip.setAttribute("data-selected", isSelected ? "false" : "true");
        emit();
      });
      chips.appendChild(chip);
    });
    container.appendChild(chips);
  }

  ns.initConnectorsForm = function initConnectorsForm(container, state, defaults, emit) {
    if (!container) return;
    const defaultsConnectors = Array.isArray(defaults.connectors) ? defaults.connectors : [];
    const initial = Array.isArray(state.connectors) && state.connectors.length ? state.connectors : defaultsConnectors;
    state.connectors = initial.map(cloneConnector);
    state.data_sources = Array.isArray(state.data_sources) && state.data_sources.length
      ? state.data_sources.slice()
      : Array.isArray(defaults.data_sources)
        ? defaults.data_sources.slice()
        : [];

    container.innerHTML = "";
    container.classList.add("intake-contract-card");

    const title = document.createElement("h3");
    title.textContent = "Connectors & Data Sources";
    container.appendChild(title);

    const connectorsBlock = document.createElement("div");
    connectorsBlock.style.marginBottom = "1rem";
    const connectorsHeading = document.createElement("strong");
    connectorsHeading.textContent = "Connectors";
    connectorsBlock.appendChild(connectorsHeading);

    state.connectors.forEach((conn) => {
      const row = createConnectorRow(conn, emit);
      connectorsBlock.appendChild(row);
    });
    container.appendChild(connectorsBlock);

    const dataSourceBlock = document.createElement("div");
    const dsHeading = document.createElement("strong");
    dsHeading.textContent = "Data Sources";
    dataSourceBlock.appendChild(dsHeading);
    renderDataSources(dataSourceBlock, state, defaults.data_sources || [], emit);
    container.appendChild(dataSourceBlock);
  };
})(typeof window !== "undefined" ? window : globalThis);
