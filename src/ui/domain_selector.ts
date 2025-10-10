interface NaicsSelection {
  code: string;
  title?: string;
  level?: number;
  version?: string;
  path?: string[];
}

export interface PrimaryDomain {
  topLevel: "Strategic Functions" | "Sector Domains" | "Technical Domains" | "Support Domains";
  subdomain: string;
  tags: string[];
  naics?: NaicsSelection;
}

type DomainMap = Record<PrimaryDomain["topLevel"], string[]>;

const CURATED_DOMAINS: DomainMap = {
  "Strategic Functions": [
    "AI Strategy & Governance",
    "Prompt Architecture & Evaluation",
    "Workflow Orchestration",
    "Observability & Telemetry",
  ],
  "Sector Domains": [
    "Energy & Infrastructure",
    "Economic Intelligence",
    "Environmental Intelligence",
    "Multi-Sector SME Overlay",
  ],
  "Technical Domains": [
    "Agentic RAG & Knowledge Graphs",
    "Tool & Connector Integrations",
    "Memory & Data Governance",
    "Safety & Privacy Compliance",
  ],
  "Support Domains": [
    "Onboarding & Training",
    "Reporting & Publishing",
    "Lifecycle & Change Mgmt",
  ],
};

const SUBDOMAIN_EXTENSIONS: Record<string, string[]> = {
  "Energy & Infrastructure": [
    "VPP & Grid Services",
    "Data Center Strategy",
    "Utility Interconnection",
    "Tariffs & TVE",
  ],
};

function normalizeTag(value: string): string | null {
  const trimmed = value.trim().toLowerCase();
  if (!trimmed) {
    return null;
  }
  const cleaned = trimmed
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");
  return cleaned ? cleaned : null;
}

function uniquePush(list: string[], value: string): string[] {
  return list.includes(value) ? list : [...list, value];
}

function createTagChip(label: string, onRemove: () => void): HTMLElement {
  const tag = document.createElement("span");
  tag.className = "ds-tag";
  tag.textContent = label;

  const removeButton = document.createElement("button");
  removeButton.type = "button";
  removeButton.setAttribute("aria-label", `Remove tag ${label}`);
  removeButton.textContent = "x";
  removeButton.addEventListener("click", onRemove);

  tag.appendChild(removeButton);
  return tag;
}

function validateNaics(selection: PrimaryDomain): PrimaryDomain {
  if (selection.topLevel !== "Sector Domains") {
    if (selection.naics) {
      // NAICS currently limited to sector domains; strip until enriched.
      selection = { ...selection };
      delete selection.naics;
    }
    return selection;
  }
  // TODO: Integrate NAICS lookup & validation against reference JSON.
  return selection;
}

export class DomainSelectorComponent {
  private topLevelSelect: HTMLSelectElement;
  private subdomainSelect: HTMLSelectElement;
  private tagInput: HTMLInputElement;
  private tagContainer: HTMLElement;
  private tags: string[] = [];
  private currentTopLevel: PrimaryDomain["topLevel"] | "" = "";
  private currentSubdomain = "";

  constructor(
    private root: HTMLElement,
    private onChange?: (value: PrimaryDomain) => void,
  ) {
    this.topLevelSelect = root.querySelector("select[data-top-level]") as HTMLSelectElement;
    this.subdomainSelect = root.querySelector("select[data-subdomain]") as HTMLSelectElement;
    this.tagInput = root.querySelector("input[data-tag-input]") as HTMLInputElement;
    this.tagContainer = root.querySelector("[data-tags]") as HTMLElement;

    this.bootstrapOptions();
    this.wireEvents();
    this.root.removeAttribute("hidden");
  }

  private bootstrapOptions() {
    Object.entries(CURATED_DOMAINS).forEach(([topLevel, subdomains]) => {
      const option = document.createElement("option");
      option.value = topLevel;
      option.textContent = topLevel;
      option.dataset.count = String(subdomains.length);
      this.topLevelSelect.appendChild(option);
    });
  }

  private wireEvents() {
    this.topLevelSelect.addEventListener("change", () => {
      this.currentTopLevel = this.topLevelSelect.value as PrimaryDomain["topLevel"];
      this.populateSubdomains();
      this.emitChange();
    });

    this.subdomainSelect.addEventListener("change", () => {
      this.currentSubdomain = this.subdomainSelect.value;
      this.emitChange();
    });

    this.tagInput.addEventListener("keydown", (event) => {
      if (event.key === "Enter") {
        event.preventDefault();
        const normalized = normalizeTag(this.tagInput.value);
        if (normalized) {
          this.tags = uniquePush(this.tags, normalized);
          this.renderTags();
          this.emitChange();
        }
        this.tagInput.value = "";
      }
    });
  }

  private populateSubdomains() {
    this.subdomainSelect.innerHTML = "";
    const placeholder = document.createElement("option");
    placeholder.value = "";
    placeholder.disabled = true;
    placeholder.selected = true;
    placeholder.textContent = "Select a subdomain";
    this.subdomainSelect.appendChild(placeholder);

    if (!this.currentTopLevel) {
      this.subdomainSelect.disabled = true;
      this.currentSubdomain = "";
      return;
    }

    const subdomains = CURATED_DOMAINS[this.currentTopLevel] || [];
    subdomains.forEach((subdomain) => {
      const option = document.createElement("option");
      option.value = subdomain;
      option.textContent = subdomain;
      this.subdomainSelect.appendChild(option);
    });

    this.subdomainSelect.disabled = false;
    this.currentSubdomain = "";
  }

  private renderTags() {
    this.tagContainer.innerHTML = "";
    this.tags.forEach((tag) => {
      const chip = createTagChip(tag, () => {
        this.tags = this.tags.filter((item) => item !== tag);
        this.renderTags();
        this.emitChange();
      });
      this.tagContainer.appendChild(chip);
    });
  }

  private emitChange() {
    if (!this.currentTopLevel || !this.currentSubdomain) {
      return;
    }
    let selection: PrimaryDomain = {
      topLevel: this.currentTopLevel,
      subdomain: this.currentSubdomain,
      tags: [...this.tags],
    };

    // TODO: capture NAICS selection once UI is available.
    selection = validateNaics(selection);

    const detail = { ...selection };
    this.root.dispatchEvent(
      new CustomEvent("domain:changed", {
        bubbles: true,
        detail,
      }),
    );

    if (typeof this.onChange === "function") {
      this.onChange(detail);
    }
  }

  static mount(selector: string, opts?: { onChange?: (value: PrimaryDomain) => void }): DomainSelectorComponent | null {
    const root = document.querySelector(selector);
    if (!root) {
      return null;
    }
    return new DomainSelectorComponent(root as HTMLElement, opts?.onChange);
  }
}

export const DomainSelector = DomainSelectorComponent;

if (typeof window !== "undefined") {
  (window as unknown as { DomainSelector?: typeof DomainSelector }).DomainSelector = DomainSelector;
}

