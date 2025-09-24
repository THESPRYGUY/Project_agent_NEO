/**
 * @version 1.0.0
 * @changelog Added NAICS cascading selector with offline search and telemetry.
 * @license Licensed under the Statistics Canada Open Licence; NAICS 2022 v1.0 reference data.
 */

import { buildNaicsIndex, toNaicsPanelNode } from "./naics-index";

export type NaicsNode = { code: string; title: string; level: 2 | 3 | 4 | 5 | 6; version: "NAICS 2022 v1.0"; path: string[] };
export type NaicsTreeNode = NaicsNode & { children?: NaicsTreeNode[] };
export type NaicsPanelOptions = { telemetry?: (event: TelemetryEvent) => void; searchLimit?: number };
export type TelemetryEvent = { ts: number; actor: "intake"; step: string; action: string; value: unknown };

const noop = () => {};

function now() {
  return Date.now();
}

/**
 * @param {NaicsNode | null | undefined} node
 * @returns {NaicsNode | null}
 */
function sanitizeNode(node) {
  if (!node) {
    return null;
  }
  return {
    code: node.code,
    title: node.title,
    level: node.level,
    version: node.version,
    path: node.path.slice(),
  };
}

/**
 * @param {Document} doc
 * @param {string} tag
 * @param {string} [className]
 */
function createEl(doc, tag, className) {
  const el = doc.createElement(tag);
  if (className) {
    el.className = className;
  }
  return el;
}

export class NaicsPanel {
  /** @type {ReturnType<typeof buildNaicsIndex>} */
  index;
  /** @type {HTMLElement | null} */
  container;
  /** @type {(event: TelemetryEvent) => void} */
  onTelemetry;
  /** @type {string[]} */
  activePath;
  /** @type {NaicsNode | null} */
  selected;
  /** @type {boolean} */
  isOpen;
  /** @type {number} */
  searchLimit;
  /** @type {NaicsNode[]} */
  searchResults;
  /** @type {HTMLInputElement | null} */
  searchInput;
  /** @type {HTMLElement | null} */
  resultsList;
  /** @type {HTMLElement | null} */
  columnsRoot;

  /**
   * @param {HTMLElement | null} container
   * @param {NaicsTreeNode[]} tree
   * @param {NaicsPanelOptions} [options]
   */
  constructor(container, tree, options = {}) {
    this.container = container ?? null;
    this.index = buildNaicsIndex(tree);
    this.onTelemetry = typeof options.telemetry === "function" ? options.telemetry : noop;
    this.activePath = [];
    this.selected = null;
    this.isOpen = false;
    this.searchLimit = typeof options.searchLimit === "number" ? Math.max(5, options.searchLimit) : 15;
    this.searchResults = [];
    this.searchInput = null;
    this.resultsList = null;
    this.columnsRoot = null;
    if (this.container && this.container.ownerDocument) {
      this._mount();
    }
  }

  /** @returns {NaicsNode | null} */
  getSelected() {
    return sanitizeNode(this.selected);
  }

  /**
   * @returns {NaicsNode[][]}
   */
  getColumns() {
    const columns = [];
    const rootNodes = this.index.tree.map((node) => toNaicsPanelNode(node));
    columns.push(rootNodes);
    for (let i = 0; i < this.activePath.length; i += 1) {
      const code = this.activePath[i];
      const current = this.index.byCode.get(code);
      if (!current || !current.children || !current.children.length) {
        break;
      }
      columns.push(current.children.map((child) => toNaicsPanelNode(child)));
    }
    return columns;
  }

  /**
   * @returns {NaicsNode[]}
   */
  getTrail() {
    if (!this.selected) {
      return [];
    }
    return this.index.ancestors(this.selected.code);
  }

  /**
   * @param {string} code
   * @returns {NaicsNode | null}
   */
  focus(code) {
    const node = this.index.byCode.get(code);
    if (!node) {
      return null;
    }
    this.activePath = node.path.slice();
    this._renderColumns();
    return toNaicsPanelNode(node);
  }

  /**
   * @param {string} code
   * @returns {NaicsNode | null}
   */
  select(code) {
    const node = this.index.byCode.get(code);
    if (!node) {
      throw new Error(`Unknown NAICS code: ${code}`);
    }
    this.activePath = node.path.slice();
    this.selected = toNaicsPanelNode(node);
    this.emit({ step: "naics", action: "selected", value: { code: node.code, level: node.level } });
    this._renderColumns();
    this._renderSearchResults();
    return this.getSelected();
  }

  clearSelection() {
    this.selected = null;
    this._renderColumns();
  }

  /**
   * @param {string} query
   * @returns {NaicsNode[]}
   */
  search(query) {
    const results = this.index.search(query ?? "", this.searchLimit).map((node) => ({ ...node, path: node.path.slice() }));
    this.searchResults = results;
    this.emit({ step: "naics", action: "searched", value: { query, count: results.length } });
    this._renderSearchResults();
    return results;
  }

  open() {
    if (!this.isOpen) {
      this.isOpen = true;
      if (this.container) {
        this.container.hidden = false;
      }
      this.emit({ step: "naics", action: "opened", value: { columns: this.getColumns().length } });
    }
    this._renderColumns();
    return this.getColumns();
  }

  close() {
    this.isOpen = false;
    if (this.container) {
      this.container.hidden = true;
    }
  }

  /**
   * @param {TelemetryEvent} event
   */
  emit(event) {
    try {
      this.onTelemetry({ ...event, ts: now(), actor: "intake" });
    } catch (error) {
      console.error("Telemetry handler threw an error", error);
    }
  }

  _mount() {
    if (!this.container) {
      return;
    }
    const doc = this.container.ownerDocument ?? (typeof document !== "undefined" ? document : null);
    if (!doc) {
      return;
    }
    this.container.innerHTML = "";
    const wrapper = createEl(doc, "div", "naics-panel");
    wrapper.setAttribute("role", "application");
    const searchId = `naics-search-${Math.random().toString(36).slice(2, 8)}`;
    const searchWrapper = createEl(doc, "div", "naics-panel__search");
    const label = createEl(doc, "label", "naics-panel__label");
    label.setAttribute("for", searchId);
    label.textContent = "Search NAICS";
    const input = /** @type {HTMLInputElement} */ (createEl(doc, "input", "naics-panel__input"));
    input.type = "search";
    input.id = searchId;
    input.setAttribute("role", "searchbox");
    input.setAttribute("aria-label", "Search NAICS codes");
    input.setAttribute("placeholder", "Search by code or keyword");
    const resultsList = createEl(doc, "ul", "naics-panel__results");
    resultsList.setAttribute("role", "listbox");
    resultsList.setAttribute("aria-label", "NAICS search results");
    const helper = createEl(doc, "p", "naics-panel__helper");
    helper.textContent = "Navigate with arrow keys. Enter selects a code; Left arrow returns to the previous column.";
    searchWrapper.append(label, input, resultsList, helper);

    const columnsRoot = createEl(doc, "div", "naics-panel__columns");
    columnsRoot.setAttribute("role", "tree");
    wrapper.append(searchWrapper, columnsRoot);
    this.container.append(wrapper);

    this.searchInput = input;
    this.resultsList = resultsList;
    this.columnsRoot = columnsRoot;

    input.addEventListener("input", (event) => {
      const target = event.target;
      const value = typeof target.value === "string" ? target.value : "";
      this.search(value);
    });

    resultsList.addEventListener("click", (event) => {
      const target = event.target;
      const scope = doc.defaultView;
      if (scope && target instanceof scope.HTMLElement) {
        const code = target.getAttribute("data-code");
        if (code) {
          this.select(code);
        }
      }
    });

    resultsList.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        const target = event.target;
        const scope = doc.defaultView;
        if (scope && target instanceof scope.HTMLElement) {
          const code = target.getAttribute("data-code");
          if (code) {
            event.preventDefault();
            this.select(code);
          }
        }
      }
    });

    this._renderColumns();
  }

  _renderColumns() {
    if (!this.columnsRoot) {
      return;
    }
    const doc = this.columnsRoot.ownerDocument;
    this.columnsRoot.innerHTML = "";
    const columns = this.getColumns();
    columns.forEach((nodes, columnIndex) => {
      const column = createEl(doc, "ul", "naics-panel__column");
      column.setAttribute("role", "group");
      column.setAttribute("aria-label", `NAICS level ${columnIndex + 1}`);
      nodes.forEach((node) => {
        const item = createEl(doc, "li", "naics-panel__item");
        item.setAttribute("role", "treeitem");
        item.setAttribute("data-code", node.code);
        item.tabIndex = columnIndex === columns.length - 1 ? 0 : -1;
        const label = `${node.code} · ${node.title}`;
        item.textContent = label;
        if (this.selected && this.selected.code === node.code) {
          item.setAttribute("aria-selected", "true");
          item.classList.add("is-selected");
        }
        if (this.activePath.includes(node.code)) {
          item.classList.add("is-active");
        }
        item.addEventListener("click", () => {
          this.select(node.code);
        });
        item.addEventListener("keydown", (event) => {
          if (event.key === "Enter" || event.key === " ") {
            event.preventDefault();
            this.select(node.code);
          } else if (event.key === "ArrowRight") {
            event.preventDefault();
            this.focus(node.code);
          } else if (event.key === "ArrowLeft" && node.path.length > 1) {
            event.preventDefault();
            const previous = node.path[node.path.length - 2];
            this.focus(previous);
          }
        });
        column.append(item);
      });
      this.columnsRoot.append(column);
    });
  }

  _renderSearchResults() {
    if (!this.resultsList) {
      return;
    }
    const doc = this.resultsList.ownerDocument;
    this.resultsList.innerHTML = "";
    this.searchResults.slice(0, this.searchLimit).forEach((node) => {
      const item = createEl(doc, "li", "naics-panel__result");
      item.setAttribute("role", "option");
      item.setAttribute("tabindex", "0");
      item.setAttribute("data-code", node.code);
      item.textContent = `${node.code} · ${node.title}`;
      this.resultsList.append(item);
    });
    if (!this.searchResults.length) {
      const empty = createEl(doc, "li", "naics-panel__result--empty");
      empty.textContent = "No matches found for the current query.";
      empty.setAttribute("role", "note");
      this.resultsList.append(empty);
    }
  }
}
