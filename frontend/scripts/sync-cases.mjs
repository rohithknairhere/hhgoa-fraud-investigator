// Copies the agent's answer files (../cases/*.json) and the case pack into data/ so the dashboard
// renders exactly what was submitted.
import { cpSync, existsSync, mkdirSync, readdirSync, rmSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const src = path.resolve(root, "..", "cases");
const dst = path.join(root, "data", "cases");

if (!existsSync(src)) {
  console.error(`cases/ not found at ${src}. Run: cd backend && python -m hhgoa.agent`);
  process.exit(1);
}
rmSync(dst, { recursive: true, force: true });
mkdirSync(dst, { recursive: true });
const files = readdirSync(src).filter((f) => /^HHG-\d{3}\.json$/.test(f));
for (const f of files) cpSync(path.join(src, f), path.join(dst, f));
console.log(`synced ${files.length} case files -> data/cases`);
