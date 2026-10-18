function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  }[ch]));
}

const NAV_ITEMS = [
  { key: "dashboard", label: "Dashboard", href: "" },
  { key: "expenses", label: "Expenses", href: "/expenses" },
  { key: "chores", label: "Chores", href: "/chores" },
  { key: "shopping", label: "Shopping", href: "/shopping" },
  { key: "residents", label: "Residents", href: "/residents" },
];

function layout({ basePath, active, title, body }) {
  const nav = NAV_ITEMS.map(
    (item) =>
      `<a class="${item.key === active ? "active" : ""}" href="${basePath}${item.href}">${item.label}</a>`
  ).join("\n");

  return `<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>${escapeHtml(title)} · WG Manager</title>
  <link rel="stylesheet" href="${basePath}/static/style.css">
</head>
<body>
  <header>
    <h1><a href="${basePath}/">WG Manager</a></h1>
    <nav>${nav}</nav>
  </header>
  <main>
    ${body}
  </main>
  <footer>WG Manager &middot; part of Toolsite</footer>
</body>
</html>`;
}

module.exports = { layout, escapeHtml };
