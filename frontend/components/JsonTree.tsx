function Leaf({ value }: { value: unknown }) {
  if (value === null) return <span className="text-ink-muted">null</span>;
  if (typeof value === "string") return <span className="text-success">&quot;{value}&quot;</span>;
  if (typeof value === "number") return <span className="text-accent">{value}</span>;
  if (typeof value === "boolean") return <span className="text-warning">{String(value)}</span>;
  return <span>{String(value)}</span>;
}

export function JsonTree({ data, label, defaultOpen = false, depth = 0 }: {
  data: unknown;
  label: string;
  defaultOpen?: boolean;
  depth?: number;
}) {
  const isObj = data !== null && typeof data === "object";
  if (!isObj) {
    return (
      <div className="font-mono text-xs leading-6">
        <span className="font-semibold text-ink">{label}</span>: <Leaf value={data} />
      </div>
    );
  }
  const entries = Array.isArray(data) ? data.map((v, i) => [String(i), v] as const) : Object.entries(data as object);
  return (
    <details open={defaultOpen || depth < 1} className="font-mono text-xs leading-6">
      <summary className="focus-ring cursor-pointer rounded font-semibold text-ink">
        {label} <span className="text-ink-muted">{Array.isArray(data) ? `[${entries.length}]` : `{${entries.length}}`}</span>
      </summary>
      <div className="ml-4 border-l border-line pl-3">
        {entries.map(([k, v]) => (
          <JsonTree key={k} data={v} label={k} depth={depth + 1} />
        ))}
      </div>
    </details>
  );
}
