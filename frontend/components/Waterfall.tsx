import type { TraceStep } from "@/lib/types";

export function Waterfall({ steps }: { steps: TraceStep[] }) {
  const total = steps.reduce((s, t) => s + t.duration_ms, 0) || 1;
  let offset = 0;
  return (
    <ol className="space-y-4" aria-label="LangGraph execution trace">
      {steps.map((s) => {
        const left = (offset / total) * 100;
        const width = Math.max((s.duration_ms / total) * 100, 1.5);
        offset += s.duration_ms;
        return (
          <li key={s.step} className="neu-sm p-4">
            <div className="flex flex-wrap items-start justify-between gap-2">
              <div className="flex items-center gap-3">
                <span aria-hidden="true" className="neu-inset grid h-9 w-9 place-items-center rounded-xl font-mono text-sm font-bold text-accent">
                  {s.step}
                </span>
                <div>
                  <p className="text-sm font-bold text-ink">
                    {s.title}
                  </p>
                  <p className="font-mono text-xs text-ink-muted">{s.node}</p>
                </div>
              </div>
              <span className="font-mono text-xs font-semibold text-ink">{s.duration_ms.toFixed(1)} ms</span>
            </div>
            <div className="neu-inset mt-3 h-2 rounded-full" aria-hidden="true">
              <div className="relative h-full">
                <div className="absolute h-full rounded-full bg-accent" style={{ left: `${left}%`, width: `${width}%` }} />
              </div>
            </div>
            <p className="mt-3 text-sm text-ink">{s.summary}</p>
          </li>
        );
      })}
    </ol>
  );
}
