const express = require("express");
const db = require("../db");
const { layout, escapeHtml } = require("../views");
const { toCents, formatCents, splitEvenly, settleUp } = require("../money");

const router = express.Router();

function getBalances() {
  const residents = db.prepare("SELECT * FROM residents ORDER BY name").all();
  const paidRows = db
    .prepare("SELECT paid_by AS resident_id, SUM(amount_cents) AS total FROM expenses GROUP BY paid_by")
    .all();
  const owedRows = db
    .prepare("SELECT resident_id, SUM(share_cents) AS total FROM expense_shares GROUP BY resident_id")
    .all();

  const paid = new Map(paidRows.map((r) => [r.resident_id, r.total]));
  const owed = new Map(owedRows.map((r) => [r.resident_id, r.total]));

  return residents.map((r) => ({
    id: r.id,
    name: r.name,
    balance_cents: (paid.get(r.id) || 0) - (owed.get(r.id) || 0),
  }));
}

router.get("/", (req, res) => {
  const residents = db.prepare("SELECT * FROM residents ORDER BY name").all();
  const expenses = db
    .prepare(
      `SELECT expenses.*, residents.name AS paid_by_name
       FROM expenses
       JOIN residents ON residents.id = expenses.paid_by
       ORDER BY created_at DESC
       LIMIT 50`
    )
    .all();
  const balances = getBalances();
  const transfers = settleUp(balances);

  const balanceRows = balances
    .map((b) => {
      const cls = b.balance_cents > 0 ? "balance-positive" : b.balance_cents < 0 ? "balance-negative" : "";
      const label = b.balance_cents > 0 ? "is owed" : b.balance_cents < 0 ? "owes" : "is settled";
      return `<tr><td>${escapeHtml(b.name)}</td><td class="${cls}">${label} ${formatCents(Math.abs(b.balance_cents))}</td></tr>`;
    })
    .join("\n");

  const transferRows = transfers
    .map((t) => `<li>${escapeHtml(t.from)} → ${escapeHtml(t.to)}: ${formatCents(t.amount_cents)}</li>`)
    .join("\n");

  const expenseRows = expenses
    .map(
      (e) => `
      <tr>
        <td>${escapeHtml(e.description)}</td>
        <td>${formatCents(e.amount_cents)}</td>
        <td class="muted">paid by ${escapeHtml(e.paid_by_name)}</td>
        <td>
          <form class="inline" method="post" action="${req.basePath}/expenses/${e.id}/delete">
            <button class="secondary" type="submit">Delete</button>
          </form>
        </td>
      </tr>`
    )
    .join("\n");

  const residentOptions = residents
    .map((r) => `<option value="${r.id}">${escapeHtml(r.name)}</option>`)
    .join("\n");

  const body = `
    <div class="card">
      <h2>Balances</h2>
      ${residents.length ? `<table><tbody>${balanceRows}</tbody></table>` : '<p class="empty">Add residents first.</p>'}
      ${transfers.length ? `<p class="muted">To settle up:</p><ul>${transferRows}</ul>` : ""}
    </div>
    <div class="card">
      <h2>Add expense</h2>
      ${residents.length
        ? `<form class="inline" method="post" action="${req.basePath}/expenses">
            <input type="text" name="description" placeholder="What for?" required>
            <input type="number" name="amount" step="0.01" min="0.01" placeholder="Amount" required style="width: 7rem;">
            <select name="paid_by" required>
              ${residentOptions}
            </select>
            <button type="submit">Add</button>
          </form>
          <p class="muted">Split evenly across all ${residents.length} resident${residents.length === 1 ? "" : "s"}.</p>`
        : '<p class="empty">Add residents before logging expenses.</p>'}
    </div>
    <div class="card">
      <h2>Recent expenses</h2>
      ${expenses.length ? `<table><tbody>${expenseRows}</tbody></table>` : '<p class="empty">No expenses yet.</p>'}
    </div>`;

  res.send(layout({ basePath: req.basePath, active: "expenses", title: "Expenses", body }));
});

router.post("/", (req, res) => {
  const description = (req.body.description || "").trim();
  const amountCents = toCents(req.body.amount);
  const paidBy = Number(req.body.paid_by);
  const residents = db.prepare("SELECT * FROM residents ORDER BY id").all();

  if (!description || !amountCents || !paidBy || residents.length === 0) {
    return res.redirect(`${req.basePath}/expenses`);
  }

  const shares = splitEvenly(amountCents, residents.length);

  const insertExpense = db.prepare(
    "INSERT INTO expenses (description, amount_cents, paid_by) VALUES (?, ?, ?)"
  );
  const insertShare = db.prepare(
    "INSERT INTO expense_shares (expense_id, resident_id, share_cents) VALUES (?, ?, ?)"
  );

  db.transaction(() => {
    const { lastInsertRowid } = insertExpense.run(description, amountCents, paidBy);
    residents.forEach((resident, i) => {
      insertShare.run(lastInsertRowid, resident.id, shares[i]);
    });
  })();

  res.redirect(`${req.basePath}/expenses`);
});

router.post("/:id/delete", (req, res) => {
  db.prepare("DELETE FROM expenses WHERE id = ?").run(req.params.id);
  res.redirect(`${req.basePath}/expenses`);
});

module.exports = router;
