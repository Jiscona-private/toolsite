const express = require("express");
const fs = require("fs");
const path = require("path");

const app = express();
const PORT = process.env.PORT || 3000;
const MODULES_DIR = process.env.MODULES_DIR || "/modules";

app.use("/static", express.static(path.join(__dirname, "public")));

function loadModules() {
  if (!fs.existsSync(MODULES_DIR)) return [];

  return fs
    .readdirSync(MODULES_DIR, { withFileTypes: true })
    .filter((entry) => entry.isDirectory() && !entry.name.startsWith("_"))
    .map((entry) => {
      const manifestPath = path.join(MODULES_DIR, entry.name, "module.json");
      if (!fs.existsSync(manifestPath)) return null;
      try {
        const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
        if (!manifest.name || !manifest.path) return null;
        return manifest;
      } catch (err) {
        console.error(`landing: failed to parse ${manifestPath}: ${err.message}`);
        return null;
      }
    })
    .filter(Boolean)
    .sort((a, b) => a.name.localeCompare(b.name));
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

function renderPage(modules) {
  const cards = modules
    .map(
      (m) => `
    <a class="card" href="${escapeHtml(m.path)}">
      <div class="card-icon">${escapeHtml(m.icon || "\u{1F527}")}</div>
      <h2>${escapeHtml(m.name)}</h2>
      <p>${escapeHtml(m.description || "")}</p>
    </a>`
    )
    .join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Toolsite</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <header>
    <h1>Toolsite</h1>
    <p>A small collection of self-hosted tools.</p>
  </header>
  <main class="grid">
    ${cards || '<p class="empty">No modules installed yet.</p>'}
  </main>
  <footer>toolsite</footer>
</body>
</html>`;
}

app.get("/", (req, res) => {
  res.send(renderPage(loadModules()));
});

app.get("/healthz", (req, res) => res.send("ok"));

app.listen(PORT, () => console.log(`landing listening on :${PORT}`));
