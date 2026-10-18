function toCents(amountStr) {
  const value = Math.round(Number(amountStr) * 100);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

function formatCents(cents) {
  return (cents / 100).toFixed(2);
}

// Splits amountCents evenly across n shares, cent-exact: the remainder
// (amountCents % n) is handed one extra cent each to the first residents
// in the list so the shares always sum back to amountCents.
function splitEvenly(amountCents, n) {
  const base = Math.floor(amountCents / n);
  const remainder = amountCents % n;
  return Array.from({ length: n }, (_, i) => base + (i < remainder ? 1 : 0));
}

// Greedy debt simplification: match the biggest creditor against the
// biggest debtor repeatedly until every balance nets to zero.
function settleUp(balances) {
  const creditors = balances
    .filter((b) => b.balance_cents > 0)
    .map((b) => ({ ...b }))
    .sort((a, b) => b.balance_cents - a.balance_cents);
  const debtors = balances
    .filter((b) => b.balance_cents < 0)
    .map((b) => ({ ...b, balance_cents: -b.balance_cents }))
    .sort((a, b) => b.balance_cents - a.balance_cents);

  const transfers = [];
  let i = 0;
  let j = 0;
  while (i < debtors.length && j < creditors.length) {
    const amount = Math.min(debtors[i].balance_cents, creditors[j].balance_cents);
    if (amount > 0) {
      transfers.push({ from: debtors[i].name, to: creditors[j].name, amount_cents: amount });
    }
    debtors[i].balance_cents -= amount;
    creditors[j].balance_cents -= amount;
    if (debtors[i].balance_cents === 0) i += 1;
    if (creditors[j].balance_cents === 0) j += 1;
  }
  return transfers;
}

module.exports = { toCents, formatCents, splitEvenly, settleUp };
