import { children, getNode, deepestValid, roots } from './naics_index';
import type { NaicsNode } from './types';

export interface CascadeState {
  selectedCode?: string; // full current selection
}

export interface CascadeOptions {
  level: number; // which level we want options for (2..6)
  parentCode?: string; // code of parent node whose children we enumerate
  options: NaicsNode[];
}

/**
 * Compute cascade option sets for NAICS levels 2..6 based on current selection.
 * Traverses the dataset graph (roots + children) without numeric loops.
 */
export function computeCascade(selectedCode: string | undefined): CascadeOptions[] {
  const result: CascadeOptions[] = [];
  const current = selectedCode ? deepestValid(selectedCode) : undefined;
  const lineage = current ? [...current.parents, current] : [];
  // Build levels 2..6
  let parent: NaicsNode | undefined = undefined;
  for (let level = 2; level <= 6; level++) {
    const parentForLevel = lineage.find(n => n.level === level - 1);
    parent = parentForLevel || undefined;
    const parentCode = parent ? parent.code : undefined;
    let opts: NaicsNode[] = [];
    if (level === 2) {
      opts = roots();
    } else if (parentCode) {
      opts = children(parentCode).filter(n => n.level === level);
    }
    if (!opts.length) continue;
    result.push({ level, parentCode, options: opts });
  }
  return result;
}
