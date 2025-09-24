/**
 * @version 1.0.0
 * @changelog Added NAICS index builder with by-code lookup and offline search helpers.
 * @license Licensed under the Statistics Canada Open Licence; NAICS 2022 v1.0 reference data.
 */

export type NaicsNode = { code: string; title: string; level: 2 | 3 | 4 | 5 | 6; version: "NAICS 2022 v1.0"; path: string[] };
export type NaicsTreeNode = NaicsNode & { children?: NaicsTreeNode[] };
export type NaicsIndex = {
  tree: NaicsTreeNode[];
  byCode: Map<string, NaicsTreeNode>;
  flatten(): NaicsNode[];
  ancestors(code: string): NaicsNode[];
  search(query: string, limit?: number): NaicsNode[];
};

const VERSION = "NAICS 2022 v1.0";

/**
 * @param {unknown} path
 * @param {string[]} fallback
 * @returns {string[]}
 */
function sanitizePath(path, fallback) {
  if (Array.isArray(path) && path.every((segment) => typeof segment === "string")) {
    return path.slice();
  }
  return fallback.slice();
}

/**
 * @param {NaicsTreeNode} treeNode
 * @returns {NaicsNode}
 */
function toNaicsNode(treeNode) {
  return {
    code: treeNode.code,
    title: treeNode.title,
    level: treeNode.level,
    version: VERSION,
    path: treeNode.path.slice(),
  };
}

/**
 * @param {string} code
 * @param {unknown} explicit
 * @param {string[]} path
 * @returns {number}
 */
function computeLevel(code, explicit, path) {
  if (typeof explicit === "number" && [2, 3, 4, 5, 6].includes(explicit)) {
    return explicit;
  }
  const derived = path.length ? path[path.length - 1].length : code.length;
  return /** @type {2 | 3 | 4 | 5 | 6} */ (Math.min(Math.max(derived, 2), 6));
}

/**
 * @param {unknown} value
 * @returns {string}
 */
function normalizeTitle(value) {
  return typeof value === "string" ? value : "";
}

/**
 * @param {unknown} value
 * @returns {string}
 */
function normalizeCode(value) {
  return typeof value === "string" ? value : "";
}

/**
 * @param {string} text
 * @returns {string}
 */
function simplify(text) {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
}

/**
 * @param {NaicsNode} node
 * @param {string} query
 * @returns {number}
 */
function scoreMatch(node, query) {
  if (!query) {
    return 0;
  }
  const normalized = simplify(node.title);
  const exactCode = node.code === query ? 40 : 0;
  const codePrefix = node.code.startsWith(query) ? 20 : 0;
  const exactTitle = normalized === query ? 30 : 0;
  const partial = normalized.includes(query) ? 10 : 0;
  return exactCode + codePrefix + exactTitle + partial;
}

/**
 * @param {NaicsTreeNode[]} rawTree
 */
function collectNodes(rawTree) {
  const byCode = new Map();
  const flat = [];

  /**
   * @param {any} node
   * @param {string[]} parents
   * @returns {NaicsTreeNode}
   */
  function visit(node, parents) {
    const code = normalizeCode(node.code);
    const title = normalizeTitle(node.title);
    if (!code || !title) {
      throw new Error("NAICS nodes require code and title values.");
    }
    const path = sanitizePath(node.path, [...parents, code]);
    const level = computeLevel(code, node.level, path);
    const childrenInput = Array.isArray(node.children) ? node.children : [];
    const clean = {
      code,
      title,
      level,
      version: VERSION,
      path,
      children: [],
    };
    byCode.set(code, clean);
    flat.push(toNaicsNode(clean));
    clean.children = childrenInput.map((child) => visit(child, path));
    return clean;
  }

  const tree = rawTree.map((node) => visit(node, []));
  return { tree, byCode, flat };
}

/**
 * @param {NaicsTreeNode[]} rawTree
 * @returns {NaicsIndex}
 */
export function buildNaicsIndex(rawTree) {
  const { tree, byCode, flat } = collectNodes(rawTree);

  function flatten() {
    return flat.map((node) => ({ ...node, path: node.path.slice() }));
  }

  function ancestors(code) {
    const match = byCode.get(code);
    if (!match) {
      return [];
    }
    const nodes = [];
    for (const ancestorCode of match.path) {
      const ancestor = byCode.get(ancestorCode);
      if (ancestor) {
        nodes.push(toNaicsNode(ancestor));
      }
    }
    return nodes;
  }

  function search(query, limit = 20) {
    const normalized = simplify(query ?? "");
    if (!normalized) {
      return flatten().slice(0, limit);
    }
    const scored = flat
      .map((node) => ({ node, score: scoreMatch(node, normalized) }))
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score || a.node.code.localeCompare(b.node.code))
      .slice(0, limit)
      .map((entry) => ({ ...entry.node, path: entry.node.path.slice() }));
    if (!scored.length) {
      return flat
        .filter((node) => simplify(node.title).includes(normalized) || node.code.includes(normalized))
        .slice(0, limit)
        .map((node) => ({ ...node, path: node.path.slice() }));
    }
    return scored;
  }

  return {
    tree,
    byCode,
    flatten,
    ancestors,
    search,
  };
}

/**
 * @param {NaicsTreeNode} node
 * @returns {NaicsNode}
 */
export function toNaicsPanelNode(node) {
  return {
    code: node.code,
    title: node.title,
    level: node.level,
    version: node.version,
    path: node.path.slice(),
  };
}
