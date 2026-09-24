import type { CaseView, GraphEdge, GraphNode } from "./types";

// Builds the sub-graph shown on a case page from the answer file: the flagged transaction, its card,
// device profiles, the rest of the fraud episode, connected cards and the closed cases retrieved as memory.
export function caseGraph({ pack, answer }: CaseView): { nodes: GraphNode[]; edges: GraphEdge[] } {
  const c = answer.case;
  const nodes = new Map<string, GraphNode>();
  const edges: GraphEdge[] = [];
  const add = (n: GraphNode) => {
    if (!nodes.has(n.id)) nodes.set(n.id, n);
  };
  const fraud = c.verdict === "fraud";
  const focal = pack.flagged_txn_id;
  add({ id: focal, type: "Transaction", label: `Txn ${focal}`, role: "focal", flagged: fraud });
  add({ id: pack.card_id, type: "Card", label: pack.card_id, role: "context", flagged: fraud });
  edges.push({ source: focal, target: pack.card_id, type: "MADE_BY" });
  c.connected_device_profiles.slice(0, 2).forEach((d, i) => {
    const id = `Device ${i + 1}`;
    add({ id, type: "Device", label: d, role: "context", flagged: fraud });
    edges.push({ source: focal, target: id, type: "FROM_DEVICE" });
  });
  if (c.graph_case_id) {
    add({ id: c.graph_case_id, type: "Case", label: `${c.graph_case_id} (written to TigerGraph)`, role: "context", flagged: false });
    edges.push({ source: focal, target: c.graph_case_id, type: "CASE_FLAGS" });
  }
  c.affected_txn_ids
    .filter((t) => t !== focal)
    .slice(0, 8)
    .forEach((t) => {
      add({ id: t, type: "Transaction", label: `Txn ${t} (same episode)`, role: "neighbour", flagged: true });
      edges.push({ source: pack.card_id, target: t, type: "LINKED_FRAUD" });
    });
  const hub = c.connected_device_profiles.length ? "Device 1" : pack.card_id;
  c.connected_card_ids.slice(0, 10).forEach((card) => {
    add({ id: card, type: "Card", label: `${card} (shares device)`, role: "neighbour", flagged: true });
    edges.push({ source: hub, target: card, type: "SHARED_DEVICE" });
  });
  c.similar_prior_cases.slice(0, 5).forEach((k) => {
    add({ id: k, type: "Case", label: `${k} (closed case memory)`, role: "memory", flagged: false });
    edges.push({ source: focal, target: k, type: "SIMILAR_TO" });
  });
  return { nodes: Array.from(nodes.values()), edges };
}
