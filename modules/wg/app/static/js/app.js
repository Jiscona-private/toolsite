// Progressive enhancement only: every link/form here already works via a
// plain navigation/POST without this file (CLAUDE.md rule 11). No inline
// scripts/handlers anywhere - the CSP's script-src 'self' has no
// 'unsafe-inline', so everything is wired up here instead.
document.addEventListener("DOMContentLoaded", () => {
  const sheet = document.getElementById("new-sheet");
  if (!sheet) return;

  const opener = document.querySelector("[data-open-sheet]");
  if (opener) {
    opener.addEventListener("click", (event) => {
      event.preventDefault();
      sheet.showModal();
    });
  }

  const closeButton = sheet.querySelector("[data-close-sheet]");
  if (closeButton) {
    closeButton.addEventListener("click", () => sheet.close());
  }
});
