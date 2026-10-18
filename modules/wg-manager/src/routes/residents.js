const express = require("express");
const db = require("../db");
const { layout, escapeHtml } = require("../views");

const router = express.Router();

router.get("/", (req, res) => {
  const residents = db.prepare("SELECT * FROM residents ORDER BY name").all();

  const rows = residents
    .map(
      (r) => `
      <tr>
        <td>${escapeHtml(r.name)}</td>
        <td>
          <form class="inline" method="post" action="${req.basePath}/residents/${r.id}/delete" onsubmit="return confirm('Remove ${escapeHtml(r.name)}? Their past expenses/chores stay on record.');">
            <button class="secondary" type="submit">Remove</button>
          </form>
        </td>
      </tr>`
    )
    .join("\n");

  const body = `
    <div class="card">
      <h2>Residents</h2>
      ${residents.length ? `<table><tbody>${rows}</tbody></table>` : '<p class="empty">No residents yet. Add the people living in the flat below.</p>'}
      <form class="inline" method="post" action="${req.basePath}/residents">
        <input type="text" name="name" placeholder="Name" required>
        <button type="submit">Add resident</button>
      </form>
    </div>`;

  res.send(layout({ basePath: req.basePath, active: "residents", title: "Residents", body }));
});

router.post("/", (req, res) => {
  const name = (req.body.name || "").trim();
  if (name) {
    db.prepare("INSERT OR IGNORE INTO residents (name) VALUES (?)").run(name);
  }
  res.redirect(`${req.basePath}/residents`);
});

router.post("/:id/delete", (req, res) => {
  db.prepare("DELETE FROM residents WHERE id = ?").run(req.params.id);
  res.redirect(`${req.basePath}/residents`);
});

module.exports = router;
