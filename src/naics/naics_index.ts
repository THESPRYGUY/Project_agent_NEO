/* NAICS index loader & query utilities.
   Loads full dataset (naics_2022.json) if present, else falls back to naics_2022.sample.json.
   Schema: { code, title, level, parents: [{code,title,level}, ...] }
*/
import type { NaicsNode } from './types';
export type NaicsHit = NaicsNode;

interface RawNode { code:string; title:string; level:number; parents: RawNode[] }

const DATASET_CACHE: { nodes?: NaicsNode[]; byCode?: Map<string, NaicsNode> } = {};

function resolveDataPaths(): string[] {
  const base = typeof __dirname !== 'undefined' ? __dirname : '.';
  // Prefer full then sample
  return [
    base + '/../../data/naics/naics_2022.json',
    base + '/../../data/naics/naics_2022.sample.json'
  ];
}

function loadRaw(): RawNode[] {
  if (DATASET_CACHE.nodes) return DATASET_CACHE.nodes as unknown as RawNode[];
  const paths = resolveDataPaths();
  for (const p of paths) {
    try {
      // eslint-disable-next-line @typescript-eslint/no-var-requires
      const data = require(p);
      if (Array.isArray(data) && data.length) {
        return data as RawNode[];
      }
    } catch(_) { /* ignore and try next */ }
  }
  return [];
}

export function materialize(): void {
  if (DATASET_CACHE.nodes) return;
  const raw = loadRaw();
  const byCode = new Map<string, NaicsNode>();
  const nodes: NaicsNode[] = raw.map(r => ({ code:r.code, title:r.title, level:r.level, parents: r.parents as unknown as NaicsNode[] }));
  for (const n of nodes) byCode.set(n.code, n);
  DATASET_CACHE.nodes = nodes;
  DATASET_CACHE.byCode = byCode;
}

export function getNode(code: string): NaicsNode | undefined {
  materialize();
  return DATASET_CACHE.byCode!.get(String(code));
}

export function lineage(code: string): NaicsNode[] {
  const node = getNode(code);
  if (!node) return [];
  return [...node.parents];
}

export function children(code: string): NaicsNode[] {
  materialize();
  return DATASET_CACHE.nodes!.filter(n => n.parents.length && n.parents[n.parents.length-1].code === code);
}

export function roots(): NaicsNode[] {
  materialize();
  return DATASET_CACHE.nodes!.filter(n => n.level === 2 && (!n.parents || n.parents.length === 0));
}

export function search(term: string): NaicsHit[] {
  materialize();
  const q = (term || '').trim().toLowerCase();
  if (!q) return [];
  const hits: NaicsHit[] = [];
  const byCode = DATASET_CACHE.byCode!;
  // Code prefix fast path
  for (const [code,node] of byCode) {
    if (code.startsWith(q)) hits.push(node);
  }
  if (hits.length === 0) {
    const tokens = q.split(/\s+/).filter(Boolean);
    for (const n of DATASET_CACHE.nodes!) {
      const titleLower = n.title.toLowerCase();
      if (tokens.every(t => titleLower.includes(t))) hits.push(n);
    }
  }
  // De-dup and sort (shorter codes first then lexicographically)
  const seen = new Set<string>();
  const ordered: NaicsHit[] = [];
  for (const h of hits) {
    if (!seen.has(h.code)) { seen.add(h.code); ordered.push(h); }
  }
  ordered.sort((a,b) => a.level === b.level ? a.code.localeCompare(b.code) : a.level - b.level);
  return ordered.slice(0, 50);
}

export function deepestValid(code: string): NaicsNode | undefined {
  if (!code) return undefined;
  // Walk down from longest to shortest until found
  for (let i = code.length; i >= 2; i--) {
    const candidate = getNode(code.slice(0,i));
    if (candidate) return candidate;
  }
  return undefined;
}
