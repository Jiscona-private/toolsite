const express = require("express");
const db = require("../db");
const { layout, escapeHtml } = require("../views");

const router = express.Router();

function isoDate(date) {
  return date.toISOString().slice(0, 10);
}

function addDays(date, days) {
  const d = new Date(date);
  d.setDate(d.getDate() + days);
  return d;
}

function nextResidentId(currentResidentId, residents) {
  const ids = residents.map((r) => r.id);
  const idx = ids.indexOf(currentResidentId);
  const nextIdx = idx === -1 ? 0 : (idx + 1) % ids.length;
  return ids[nextIdx];
}

router.get("/", (req, res) => {
  const residents = db.prepare("SELECT * FROM residents ORDER BY id").all();
  const chores = db.prepare("SELECT * FROM chores ORDER BY name").all();

  const choreBlocks = chores
    .map((chore) => {
      const current = db
        .prepare(
          `SELECT chore_assignments.*, residents.name AS resident_name
           FROM chore_assignments
           JOIN residents ON residents.id = chore_assignments.resident_id
           WHERE chore_id = ? AND completed_at IS NULL
           ORDER BY due_date ASC LIMIT 1`
        )
        .get(chore.id);

      const history = db
        .prepare(
          `SELECT chore_assignments.*, residents.name AS resident_name
           FROM chore_assignments
           JOIN residents ON residents.id = chore_assignments.resident_id
           WHERE chore_id = ? AND completed_at IS NOT NULL
           ORDER BY completed_at DESC LIMIT 3`
        )
        .all(chore.id);

      const historyList = history
        .map((h) => `<li class="muted">${escapeHtml(h.resident_name)} — done ${h.completed_at.slice(0, 10)}</li>`)
        .join("\n");

      return `
      <div class="card">
        <div class="row">
          <h2>${escapeHtml(chore.name)}</h2>
          <form method="post" action="${req.basePath}/chores/${chore.id}/delete">
            <button class="secondary" type="submit">Delete</button>
          </form>
        </div>
        <p class="muted">every ${chore.frequency_days} day${chore.frequency_days === 1 ? "" : "s"}</p>
        ${
          current
            ? `<p>Next up: <strong>${escapeHtml(current.resident_name)}</strong> &middot; due ${escapeHtml(current.due_date)}</p>
               <form method="post" action="${req.basePath}/chores/${chore.id}/complete">
                 <button type="submit">Mark done</button>
               </form>`
            : '<p class="empty">No one assigned — add residents to start the rotation.</p>'
        }
        ${history.length ? `<p class="muted">Recent:</p><ul>${historyList}</ul>` : ""}
      </div>`;
    })
    .join("\n");

  const residentOptions = residents
    .map((r) => `<option value="${r.id}">${escapeHtml(r.name)}</option>`)
    .join("\n");

  const body = `
    <div class="card">
      <h2>Add chore</h2>
      ${residents.length
        ? `<form class="inline" method="post" action="${req.basePath}/chores">
            <input type="text" name="name" placeholder="Chore (e.g. Take out trash)" required>
            <input type="number" name="frequency_days" min="1" value="7" style="width: 5rem;" title="Repeat every N days">
            <select name="first_resident" required>
              ${residentOptions}
            </select>
            <button type="submit">Add</button>
          </form>
          <p class="muted">Rotates through residents in order each time it's marked done.</p>`
        : '<p class="empty">Add residents before creating chores.</p>'}
    </div>
    ${choreBlocks || (residents.length ? '<p class="empty">No chores yet.</p>' : "")}`;

  res.send(layout({ basePath: req.basePath, active: "chores", title: "Chores", body }));
});

router.post("/", (req, res) => {
  const name = (req.body.name || "").trim();
  const frequencyDays = Math.max(1, parseInt(req.body.frequency_days, 10) || 7);
  const firstResident = Number(req.body.first_resident);
  if (!name || !firstResident) return res.redirect(`${req.basePath}/chores`);

  db.transaction(() => {
    const { lastInsertRowid } = db
      .prepare("INSERT INTO chores (name, frequency_days) VALUES (?, ?)")
      .run(name, frequencyDays);
    db.prepare(
      "INSERT INTO chore_assignments (chore_id, resident_id, due_date) VALUES (?, ?, ?)"
    ).run(lastInsertRowid, firstResident, isoDate(addDays(new Date(), frequencyDays)));
  })();

  res.redirect(`${req.basePath}/chores`);
});

router.post("/:id/complete", (req, res) => {
  const chore = db.prepare("SELECT * FROM chores WHERE id = ?").get(req.params.id);
  const residents = db.prepare("SELECT * FROM residents ORDER BY id").all();
  const current = db
    .prepare(
      "SELECT * FROM chore_assignments WHERE chore_id = ? AND completed_at IS NULL ORDER BY due_date ASC LIMIT 1"
    )
    .get(req.params.id);

  if (chore && current && residents.length > 0) {
    db.transaction(() => {
      db.prepare("UPDATE chore_assignments SET completed_at = ? WHERE id = ?").run(
        new Date().toISOString(),
        current.id
      );
      const nextId = nextResidentId(current.resident_id, residents);
      db.prepare(
        "INSERT INTO chore_assignments (chore_id, resident_id, due_date) VALUES (?, ?, ?)"
      ).run(chore.id, nextId, isoDate(addDays(new Date(), chore.frequency_days)));
    })();
  }

  res.redirect(`${req.basePath}/chores`);
});

router.post("/:id/delete", (req, res) => {
  db.prepare("DELETE FROM chores WHERE id = ?").run(req.params.id);
  res.redirect(`${req.basePath}/chores`);
});

module.exports = router;
