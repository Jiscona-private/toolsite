const express = require("express");
const db = require("../db");
const { layout, escapeHtml } = require("../views");

const router = express.Router();

router.get("/", (req, res) => {
  const items = db
    .prepare(
      `SELECT shopping_items.*, residents.name AS added_by_name
       FROM shopping_items
       LEFT JOIN residents ON residents.id = shopping_items.added_by
       ORDER BY completed_at IS NOT NULL, created_at DESC`
    )
    .all();
  const residents = db.prepare("SELECT * FROM residents ORDER BY name").all();

  const rows = items
    .map((item) => {
      const doneAttr = item.completed_at ? "checked" : "";
      const label = `${escapeHtml(item.name)}${item.quantity ? ` (${escapeHtml(item.quantity)})` : ""}`;
      return `
      <tr>
        <td>
          <form class="inline" method="post" action="${req.basePath}/shopping/${item.id}/toggle">
            <button class="secondary" type="submit">${item.completed_at ? "☑" : "☐"}</button>
          </form>
        </td>
        <td style="${item.completed_at ? "text-decoration: line-through; color: var(--muted);" : ""}">${label}</td>
        <td class="muted">${item.added_by_name ? escapeHtml(item.added_by_name) : ""}</td>
        <td>
          <form class="inline" method="post" action="${req.basePath}/shopping/${item.id}/delete">
            <button class="secondary" type="submit">Delete</button>
          </form>
        </td>
      </tr>`;
    })
    .join("\n");

  const residentOptions = residents
    .map((r) => `<option value="${r.id}">${escapeHtml(r.name)}</option>`)
    .join("\n");

  const body = `
    <div class="card">
      <h2>Shopping list</h2>
      ${items.length ? `<table><tbody>${rows}</tbody></table>` : '<p class="empty">Nothing on the list.</p>'}
      <form class="inline" method="post" action="${req.basePath}/shopping">
        <input type="text" name="name" placeholder="Item" required>
        <input type="text" name="quantity" placeholder="Qty (optional)" style="width: 7rem;">
        <select name="added_by">
          <option value="">Added by…</option>
          ${residentOptions}
        </select>
        <button type="submit">Add item</button>
      </form>
    </div>`;

  res.send(layout({ basePath: req.basePath, active: "shopping", title: "Shopping list", body }));
});

router.post("/", (req, res) => {
  const name = (req.body.name || "").trim();
  if (name) {
    db.prepare(
      "INSERT INTO shopping_items (name, quantity, added_by) VALUES (?, ?, ?)"
    ).run(name, (req.body.quantity || "").trim() || null, req.body.added_by || null);
  }
  res.redirect(`${req.basePath}/shopping`);
});

router.post("/:id/toggle", (req, res) => {
  const item = db.prepare("SELECT * FROM shopping_items WHERE id = ?").get(req.params.id);
  if (item) {
    db.prepare("UPDATE shopping_items SET completed_at = ? WHERE id = ?").run(
      item.completed_at ? null : new Date().toISOString(),
      item.id
    );
  }
  res.redirect(`${req.basePath}/shopping`);
});

router.post("/:id/delete", (req, res) => {
  db.prepare("DELETE FROM shopping_items WHERE id = ?").run(req.params.id);
  res.redirect(`${req.basePath}/shopping`);
});

module.exports = router;
