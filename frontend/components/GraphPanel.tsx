"use client";

import { useMemo, useState } from "react";

import type { GraphEdge, GraphNode } from "@/lib/types";

import { JsonTree } from "./JsonTree";

const W = 640;
const H = 480;
const CX = W / 2;
const CY = H / 2;

const TYPE_GLYPH: Record<string, string> = {
  Transaction: "T",
  Card: "C",
  Device: "D",
  IP: "IP",
  Customer: "U",
  Case: "K",
};

function layout(nodes: GraphNode[], edges: GraphEdge[]) {
  const pos = new Map<string, { x: number; y: number }>();
  const focal = nodes.find((n) => n.role === "focal");
  if (focal) pos.set(focal.id, { x: CX, y: CY });
  const ring1 = nodes.filter((n) => n.role === "context");
  ring1.forEach((n, i) => {
    const a = (i / Math.max(ring1.length, 1)) * Math.PI * 2 - Math.PI / 2;
    pos.set(n.id, { x: CX + 120 * Math.cos(a), y: CY + 110 * Math.sin(a) });
  });
  // Outer ring grouped by the node that links to it, so related neighbours sit together.
  const outer = nodes.filter((n) => n.role === "neighbour" || n.role === "memory");
  const parentIndex = (id: string) => {
    const e = edges.find((ed) => ed.target === id);
    const p = e ? ring1.findIndex((r) => r.id === e.source) : -1;
    return p === -1 ? ring1.length : p;
  };
  outer
    .map((n) => ({ n, p: parentIndex(n.id) }))
    .sort((a, b) => a.p - b.p || a.n.id.localeCompare(b.n.id))
    .forEach(({ n }, i, arr) => {
      const a = (i / Math.max(arr.length, 1)) * Math.PI * 2 - Math.PI / 2 + 0.3;
      pos.set(n.id, { x: CX + 270 * Math.cos(a), y: CY + 200 * Math.sin(a) });
    });
  return pos;
}

export function GraphPanel({
  nodes,
  edges,
  context,
}: {
  nodes: GraphNode[];
  edges: GraphEdge[];
  context: Record<string, unknown>;
}) {
  const [view, setView] = useState<"graph" | "json">("graph");
  const [selected, setSelected] = useState<GraphNode | null>(null);
  const pos = useMemo(() => layout(nodes, edges), [nodes, edges]);

  return (
    <div>
      <div role="tablist" aria-label="Graph context view" className="neu-inset mb-4 inline-flex gap-1 rounded-2xl p-1">
        {(["graph", "json"] as const).map((v) => (
          <button
            key={v}
            role="tab"
            type="button"
            aria-selected={view === v}
            onClick={() => setView(v)}
            className={`focus-ring rounded-xl px-4 py-2 text-sm font-semibold ${
              view === v ? "bg-surface text-accent shadow-neu-sm" : "text-ink-muted"
            }`}
          >
            {v === "graph" ? "Sub-graph" : "JSON tree"}
          </button>
        ))}
      </div>

      {view === "graph" ? (
        <div className="grid gap-4 lg:grid-cols-[1fr_16rem]">
          <div className="neu-inset overflow-hidden rounded-3xl p-2">
            <svg
              viewBox={`0 0 ${W} ${H}`}
              className="h-auto w-full"
              role="img"
              aria-label={`Evidence sub-graph with ${nodes.length} entities and ${edges.length} relationships`}
            >
              {edges.map((e) => {
                const a = pos.get(e.source);
                const b = pos.get(e.target);
                if (!a || !b) return null;
                return (
                  <line
                    key={`${e.source}-${e.target}-${e.type}`}
                    x1={a.x}
                    y1={a.y}
                    x2={b.x}
                    y2={b.y}
                    stroke={e.type === "SIMILAR_TO" ? "#00666b" : e.type === "LINKED_FRAUD" ? "#a4262c" : "#5b7f82"}
                    strokeWidth={1.5}
                    strokeDasharray={e.type === "SIMILAR_TO" ? "5 4" : undefined}
                  />
                );
              })}
              {nodes.map((n) => {
                const p = pos.get(n.id);
                if (!p) return null;
                const r = n.role === "focal" ? 26 : n.role === "context" ? 20 : 14;
                const isSel = selected?.id === n.id;
                return (
                  <g
                    key={n.id}
                    transform={`translate(${p.x},${p.y})`}
                    tabIndex={0}
                    role="button"
                    aria-label={`${n.type} ${n.label}${n.flagged ? ", flagged" : ""}`}
                    onClick={() => setSelected(n)}
                    onKeyDown={(ev) => (ev.key === "Enter" || ev.key === " ") && setSelected(n)}
                    className="cursor-pointer focus:outline-none"
                  >
                    <circle r={r + 3} fill="#c3d2d3" opacity={0.5} transform="translate(2,2)" />
                    <circle r={r + 3} fill="#ffffff" opacity={0.9} transform="translate(-2,-2)" />
                    <circle
                      r={r}
                      fill={n.role === "focal" ? "#00666b" : "#eaf1f1"}
                      stroke={n.flagged ? "#a4262c" : isSel ? "#00666b" : "#9bb5b7"}
                      strokeWidth={n.flagged || isSel ? 3 : 1.5}
                      strokeDasharray={n.role === "memory" ? "4 3" : undefined}
                    />
                    <text
                      textAnchor="middle"
                      dy="0.35em"
                      fontSize={n.role === "focal" ? 13 : 11}
                      fontWeight={700}
                      fill={n.role === "focal" ? "#ffffff" : "#051b1d"}
                    >
                      {TYPE_GLYPH[n.type] ?? "?"}
                    </text>
                    {n.role !== "neighbour" && (
                      <text textAnchor="middle" y={r + 16} fontSize={11} fill="#051b1d" fontWeight={600}>
                        {n.id}
                      </text>
                    )}
                  </g>
                );
              })}
            </svg>
          </div>
          <aside className="space-y-3 text-sm" aria-live="polite">
            <div className="neu-sm p-4">
              <p className="eyebrow mb-2">Selected entity</p>
              {selected ? (
                <dl className="space-y-1">
                  <div>
                    <dt className="sr-only">Type</dt>
                    <dd className="font-semibold text-ink">{selected.type}</dd>
                  </div>
                  <div>
                    <dt className="sr-only">Label</dt>
                    <dd className="break-words font-mono text-xs text-ink">{selected.label}</dd>
                  </div>
                  <div>
                    <dt className="sr-only">Status</dt>
                    <dd className={selected.flagged ? "font-semibold text-danger" : "text-ink-muted"}>
                      {selected.flagged ? "Flagged by a fraud signal" : "No fraud signal"}
                    </dd>
                  </div>
                </dl>
              ) : (
                <p className="text-ink-muted">Select a node to inspect it.</p>
              )}
            </div>
            <ul className="neu-sm space-y-1.5 p-4 text-xs text-ink">
              <li><span className="font-bold">T</span> Transaction, <span className="font-bold">C</span> Card, <span className="font-bold">D</span> Device</li>
              <li><span className="font-bold">IP</span> IP address, <span className="font-bold">U</span> Customer, <span className="font-bold">K</span> Case</li>
              <li><span className="font-semibold text-danger">Red ring</span>: flagged by a fraud signal</li>
              <li><span className="font-semibold text-accent">Dashed</span>: similar case from graph memory</li>
            </ul>
          </aside>
        </div>
      ) : (
        <div className="neu-inset max-h-[32rem] overflow-auto rounded-3xl p-4">
          <JsonTree data={context} label="graph_context" defaultOpen />
        </div>
      )}
    </div>
  );
}
