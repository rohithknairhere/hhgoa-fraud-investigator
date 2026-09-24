// WCAG 2.1 contrast check for every foreground/background pair in the design tokens,
// plus a scan of source files for low-contrast Tailwind grays on the neumorphic surface.
import { readFileSync, readdirSync, statSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const tokens = JSON.parse(readFileSync(path.join(root, "lib", "tokens.json"), "utf-8"));

function luminance(hex) {
  const n = hex.replace("#", "");
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(n.slice(i, i + 2), 16) / 255);
  const lin = (c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4);
  return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b);
}
export function contrast(a, b) {
  const [l1, l2] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (l1 + 0.05) / (l2 + 0.05);
}

let failed = 0;
for (const [fg, bg] of tokens.contrastPairs) {
  const ratio = contrast(tokens.colors[fg], tokens.colors[bg]);
  const ok = ratio >= 4.5;
  if (!ok) failed++;
  console.log(`${ok ? "PASS" : "FAIL"}  ${fg.padEnd(10)} on ${bg.padEnd(12)} ${ratio.toFixed(2)}:1 (AA min 4.5)`);
}

// Heuristic: light Tailwind grays (400 and below) fail AA on #e0e5ec, so forbid them for text.
const banned = /\btext-(?:gray|slate|zinc|neutral|stone)-(?:50|100|200|300|400)\b/;
function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(tsx?|css)$/.test(name)) {
      readFileSync(p, "utf-8").split("\n").forEach((line, i) => {
        if (banned.test(line)) {
          failed++;
          console.log(`FAIL  low-contrast text class in ${path.relative(root, p)}:${i + 1}`);
        }
      });
    }
  }
}
for (const d of ["app", "components"]) walk(path.join(root, d));

// Inline hex colours used for text in SVG must also pass on the surface colour.
for (const hex of ["#1e293b", "#3730a3", "#9f1239", "#334155"]) {
  const ratio = contrast(hex, tokens.colors.surface);
  if (ratio < 4.5) {
    failed++;
    console.log(`FAIL  inline colour ${hex} on surface ${ratio.toFixed(2)}:1`);
  }
}

if (failed) {
  console.error(`\n${failed} contrast check(s) failed`);
  process.exit(1);
}
console.log("\nAll contrast checks passed (WCAG AA).");
