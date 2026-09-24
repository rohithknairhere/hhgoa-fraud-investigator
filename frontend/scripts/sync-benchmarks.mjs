// Copies ../benchmark_results/*.json into data/benchmarks so the dashboard can render an
// offline snapshot when the FastAPI backend is not reachable (e.g. during `next build`).
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const src = path.resolve(root, "..", "benchmark_results");
const dst = path.join(root, "data", "benchmarks");

if (!existsSync(src)) {
  console.error(`benchmark_results not found at ${src}. Run: python backend/run_benchmarks.py`);
  process.exit(1);
}
rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
const files = readdirSync(src).filter((f) => f.endsWith(".json"));
for (const f of files) cpSync(path.join(src, f), path.join(dst, f));
console.log(`synced ${files.length} benchmark files -> data/benchmarks`);
