/** Shared NAICS types */
export interface NaicsNode {
  code: string;
  title: string;
  level: number; // 2..6
  parents: NaicsNode[]; // ancestry chain
}

export type NaicsLineage = Array<Pick<NaicsNode, 'code' | 'title' | 'level'>>;

export interface NaicsEventPayload {
  code: string;
  title?: string;
  level: number;
  lineage: NaicsLineage;
}
