// Copies the pinned htmx and Alpine builds into static/vendor/ with their versions in the file names.
import fs from "node:fs";
import path from "node:path";

const out = "static/vendor";
const files = [
  ["htmx.org", "dist/htmx.min.js", "htmx"],
  ["alpinejs", "dist/cdn.min.js", "alpine"],
  ["@alpinejs/focus", "dist/cdn.min.js", "alpine-focus"],
  ["@alpinejs/sort", "dist/cdn.min.js", "alpine-sort"],
];

const jobs = files.map(([pkg, file, name]) => {
  const dir = path.join("node_modules", pkg);
  const src = path.join(dir, file);
  if (!fs.existsSync(src)) {
    console.error(`Missing ${src}`);
    process.exit(1);
  }
  const { version } = JSON.parse(
    fs.readFileSync(path.join(dir, "package.json"), "utf8"),
  );
  return { src, dest: path.join(out, `${name}-${version}.min.js`) };
});

fs.mkdirSync(out, { recursive: true });
for (const f of fs.readdirSync(out)) {
  if (/^(htmx|alpine|alpine-focus|alpine-sort)-.*\.js$/.test(f))
    fs.rmSync(path.join(out, f));
}
for (const { src, dest } of jobs) {
  fs.copyFileSync(src, dest);
  console.log(`${src} -> ${dest}`);
}
