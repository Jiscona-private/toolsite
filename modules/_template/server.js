const express = require("express");

const app = express();
const PORT = process.env.PORT || 3000;
// Keep BASE_PATH baked into every route/link this module emits — Caddy
// forwards the full path (including the prefix) upstream, it does not
// strip it. See docs/ADDING_MODULES.md.
const BASE_PATH = (process.env.BASE_PATH || "/__MODULE_ID__").replace(/\/+$/, "");

app.get(`${BASE_PATH}/healthz`, (req, res) => res.send("ok"));

app.get(`${BASE_PATH}/`, (req, res) => {
  res.send(`<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><title>__MODULE_NAME__</title></head>
<body>
  <h1>__MODULE_NAME__</h1>
  <p>This module is scaffolded and running — replace this page with real content.</p>
  <p><a href="/">&larr; Back to Toolsite</a></p>
</body>
</html>`);
});

app.listen(PORT, () => console.log(`__MODULE_ID__ listening on :${PORT} (base path ${BASE_PATH})`));
