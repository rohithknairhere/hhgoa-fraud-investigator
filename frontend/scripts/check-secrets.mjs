// Scans the browser bundle (.next/static) for anything that must stay server-side:
// backend URLs, server env var names, credential-shaped strings.
import { existsSync, readFileSync, readdirSync, statSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const staticDir = path.join(root, ".next", "static");
if (!existsSync(staticDir)) {
  console.error("No build output found. Run `npm run build` first.");
  process.exit(1);
}

const patterns = [
  ["server env name", /BACKEND_API_URL|TG_PASSWORD|TG_SECRET|ANTHROPIC_API_KEY/],
  ["backend origin", /127\.0\.0\.1:8000|localhost:8000/],
  ["Anthropic key", /sk-ant-[A-Za-z0-9_-]{10,}/],
  ["private key", /-----BEGIN (?:RSA |EC )?PRIVATE KEY-----/],
  ["bearer token", /Bearer\s+[A-Za-z0-9._-]{20,}/],
];
if (process.env.BACKEND_API_URL) patterns.push(["configured backend URL", new RegExp(process.env.BACKEND_API_URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))]);

let files = 0;
let hits = 0;
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (/\.(js|css|json|html|txt)$/.test(name)) {
      files++;
      const body = readFileSync(p, "utf-8");
      for (const [label, re] of patterns) {
        if (re.test(body)) {
          hits++;
          console.log(`LEAK  ${label} in ${path.relative(root, p)}`);
        }
      }
    }
  }
})(staticDir);

console.log(`${files} client bundle files scanned.`);
if (hits) process.exit(1);
console.log("No secrets or internal URLs in the browser bundle.");
