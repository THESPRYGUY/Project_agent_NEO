const { JSDOM } = require("jsdom");

let DomainSelector;
let dom;

describe("DomainSelector", () => {
  beforeEach(() => {
    dom = new JSDOM("<!doctype html><html><body></body></html>", { pretendToBeVisual: true });
    global.window = dom.window;
    global.document = dom.window.document;
    global.CustomEvent = dom.window.CustomEvent;
    global.Node = dom.window.Node;

    delete require.cache[require.resolve("../../src/ui/domain_selector.js")];
    DomainSelector = require("../../src/ui/domain_selector.js").DomainSelector;
  });

  afterEach(() => {
    dom.window.close();
    delete global.window;
    delete global.document;
    delete global.CustomEvent;
    delete global.Node;
  });

  test("emits payload when selection changes", async () => {
    document.body.innerHTML = [
      '<div id="domain-selector" data-domain-selector hidden>',
      '  <label>',
      '    <select data-top-level>',
      '      <option value="" disabled selected>Select a domain group</option>',
      '    </select>',
      '  </label>',
      '  <label>',
      '    <select data-subdomain disabled>',
      '      <option value="" disabled selected>Select a subdomain</option>',
      '    </select>',
      '  </label>',
      '  <label>',
      '    <input data-tag-input type="text" />',
      '  </label>',
      '  <div data-tags></div>',
      '</div>'
    ].join('');

    const root = document.querySelector("#domain-selector");
    expect(root).not.toBeNull();

    const events = [];
    root.addEventListener("domain:changed", (event) => {
      events.push(event.detail);
    });

  global.fetch = jest.fn().mockResolvedValue({ ok: true, json: async () => ({ status: 'ok', curated: { 'Strategic Functions': ['Workflow Orchestration'] } }) });
  DomainSelector.mount("#domain-selector");
  await new Promise(r => setTimeout(r, 5));

    const topLevel = root.querySelector("[data-top-level]");
    const subdomain = root.querySelector("[data-subdomain]");

    topLevel.value = "Strategic Functions";
    topLevel.dispatchEvent(new dom.window.Event("change"));

    subdomain.value = "Workflow Orchestration";
    subdomain.dispatchEvent(new dom.window.Event("change"));

  expect(events).toHaveLength(1);
    expect(events[0]).toMatchObject({
      topLevel: "Strategic Functions",
      subdomain: "Workflow Orchestration",
      tags: [],
    });
  });
});
