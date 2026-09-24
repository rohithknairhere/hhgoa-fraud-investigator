// Verifies that every internal link in the prerendered HTML (and every sitemap URL)
// resolves to a page produced by `next build`. Also enforces alt text on every <img>.
import { existsSync, readFileSync, readdirSync, statSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const root = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const appOut = path.join(root, ".next", "server", "app");
if (!existsSync(appOut)) {
  console.error("No build output found. Run `npm run build` first.");
  process.exit(1);
}

const htmlFiles = [];
(function walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = path.join(dir, name);
    if (statSync(p).isDirectory()) walk(p);
    else if (name.endsWith(".html")) htmlFiles.push(p);
  }
})(appOut);

const routeFor = (file) => {
  const rel = path.relative(appOut, file).replace(/\\/g, "/").replace(/\.html$/, "");
  return rel === "index" ? "/" : `/${rel}`;
};
const pages = new Set(htmlFiles.map(routeFor));
// Non-HTML routes emitted by the metadata file conventions / route handlers.
for (const extra of ["/sitemap.xml", "/robots.txt", "/icon.svg", "/opengraph-image"]) pages.add(extra);

let failures = 0;
let checked = 0;
for (const file of htmlFiles) {
  const html = readFileSync(file, "utf-8");
  for (const m of html.matchAll(/<a\b[^>]*\bhref="([^"]+)"/g)) {
    const href = m[1];
    if (!href.startsWith("/") || href.startsWith("//")) continue;
    const target = href.split("#")[0].split("?")[0] || "/";
    checked++;
    if (!pages.has(target)) {
      failures++;
      console.log(`BROKEN  ${routeFor(file)} -> ${href}`);
    }
  }
  for (const m of html.matchAll(/<img\b[^>]*>/g)) {
    const alt = m[0].match(/\balt="([^"]*)"/);
    if (!alt || !alt[1].trim()) {
      failures++;
      console.log(`NO-ALT  ${routeFor(file)}: ${m[0].slice(0, 80)}...`);
    }
  }
}

const sitemapBody = path.join(appOut, "sitemap.xml.body");
if (existsSync(sitemapBody)) {
  for (const m of readFileSync(sitemapBody, "utf-8").matchAll(/<loc>([^<]+)<\/loc>/g)) {
    const p = new URL(m[1]).pathname;
    checked++;
    if (!pages.has(p)) {
      failures++;
      console.log(`BROKEN  sitemap -> ${p}`);
    }
  }
}

console.log(`${checked} internal links checked across ${htmlFiles.length} pages.`);
if (failures) {
  console.error(`${failures} problem(s) found`);
  process.exit(1);
}
console.log("No broken internal links; every <img> has alt text.");
