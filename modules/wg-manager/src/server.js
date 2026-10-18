const express = require("express");
const path = require("path");
const db = require("./db");
const { layout, escapeHtml } = require("./views");
const { formatCents } = require("./money");

const residentsRouter = require("./routes/residents");
const expensesRouter = require("./routes/expenses");
const choresRouter = require("./routes/chores");
const shoppingRouter = require("./routes/shopping");

const app = express();
const PORT = process.env.PORT || 3000;
const BASE_PATH = (process.env.BASE_PATH || "/wg").replace(/\/+$/, "");

app.use(express.urlencoded({ extended: false }));

app.use((req, res, next) => {
  req.basePath = BASE_PATH;
  next();
});

app.use(`${BASE_PATH}/static`, express.static(path.join(__dirname, "..", "public")));

app.get(`${BASE_PATH}/healthz`, (req, res) => res.send("ok"));

app.get(`${BASE_PATH}/`, (req, res) => {
  const residents = db.prepare("SELECT * FROM residents ORDER BY name").all();

  const paidRows = db
    .prepare("SELECT paid_by AS resident_id, SUM(amount_cents) AS total FROM expenses GROUP BY paid_by")
    .all();
  const owedRows = db
    .prepare("SELECT resident_id, SUM(share_cents) AS total FROM expense_shares GROUP BY resident_id")
    .all();
  const paid = new Map(paidRows.map((r) => [r.resident_id, r.total]));
  const owed = new Map(owedRows.map((r) => [r.resident_id, r.total]));
  const balances = residents.map((r) => ({
    name: r.name,
    balance_cents: (paid.get(r.id) || 0) - (owed.get(r.id) || 0),
  }));

  const dueChores = db
    .prepare(
      `SELECT chores.name AS chore_name, residents.name AS resident_name, chore_assignments.due_date
       FROM chore_assignments
       JOIN chores ON chores.id = chore_assignments.chore_id
       JOIN residents ON residents.id = chore_assignments.resident_id
       WHERE chore_assignments.completed_at IS NULL
       ORDER BY chore_assignments.due_date ASC
       LIMIT 5`
    )
    .all();

  const openShoppingCount = db
    .prepare("SELECT COUNT(*) AS n FROM shopping_items WHERE completed_at IS NULL")
    .get().n;

  const balanceList = balances
    .map((b) => {
      const cls = b.balance_cents > 0 ? "balance-positive" : b.balance_cents < 0 ? "balance-negative" : "";
      const label = b.balance_cents > 0 ? "is owed" : b.balance_cents < 0 ? "owes" : "is settled";
      return `<li>${escapeHtml(b.name)} <span class="${cls}">${label} ${formatCents(Math.abs(b.balance_cents))}</span></li>`;
    })
    .join("\n");

  const choreList = dueChores
    .map((c) => `<li>${escapeHtml(c.chore_name)} — ${escapeHtml(c.resident_name)} (due ${c.due_date})</li>`)
    .join("\n");

  const body = `
    <div class="card">
      <h2>Balances</h2>
      ${balances.length ? `<ul>${balanceList}</ul>` : '<p class="empty">No residents yet — start on the <a href="' + req.basePath + '/residents">Residents</a> page.</p>'}
      <p><a href="${req.basePath}/expenses">View expenses &rarr;</a></p>
    </div>
    <div class="card">
      <h2>Upcoming chores</h2>
      ${dueChores.length ? `<ul>${choreList}</ul>` : '<p class="empty">No chores scheduled.</p>'}
      <p><a href="${req.basePath}/chores">View chores &rarr;</a></p>
    </div>
    <div class="card">
      <h2>Shopping list</h2>
      <p>${openShoppingCount} item${openShoppingCount === 1 ? "" : "s"} still needed.</p>
      <p><a href="${req.basePath}/shopping">View shopping list &rarr;</a></p>
    </div>`;

  res.send(layout({ basePath: req.basePath, active: "dashboard", title: "Dashboard", body }));
});

app.use(`${BASE_PATH}/residents`, residentsRouter);
app.use(`${BASE_PATH}/expenses`, expensesRouter);
app.use(`${BASE_PATH}/chores`, choresRouter);
app.use(`${BASE_PATH}/shopping`, shoppingRouter);

app.listen(PORT, () => console.log(`wg-manager listening on :${PORT} (base path ${BASE_PATH})`));
