# Roadmap und To-dos

Abhaken mit `[x]`, sobald etwas erledigt ist (im selben Commit). „(du)“ = erledigt der Projektinhaber, alles andere Claude Code.

```
Phase 0 Fundament ──▶ Phase 1 Kern ──▶ Phase 2 Alltag ──▶ Phase 3 Komfort
   weiter, wenn:        weiter, wenn:      weiter, wenn:
   VPS + HTTPS laufen   2 Wochen Alltags-  Feedback der WG
                        test mit allen 4   eingearbeitet
```
Phase 1 darf lokal schon vor Phase 0 beginnen.

## Planung (abgeschlossen)
- [x] Masterplan, Architektur, Datenmodell
- [x] Klickbare Design-Vorschau (9 Screens) → `docs/design/screens/`
- [x] Startverteilung Putzplan festgelegt (ab 2026-10-19)
- [x] Ausgaben-Start festgelegt: bei null
- [x] Navigation vereinfacht (4 Bereiche + „+“)
- [x] Übergabe an Claude Code (diese Dateien)

## Phase 0 · Fundament
- [x] VPS piko bestellt und eingerichtet, Toolsite mit Domain läuft (du)
- [x] Entscheidung: WG-App als Toolsite-Modul `modules/wg/`, ersetzt den Dummy `wg-manager`
- [ ] Ziel für die externe Backup-Kopie festlegen und einrichten (du)

## Phase 1 · Kern – Implementierungsreihenfolge
Jeder Schritt endet mit grünen Tests, `ruff` und einem Commit.

1. [x] **Gerüst:** in `modules/wg/`: `pyproject.toml` (uv), `app/main.py` mit `create_app()` und allen Routen unter `BASE_PATH`, `config.py` (`PORT`, `BASE_PATH`, …), `/wg/healthz`, ruff- und pytest-Konfiguration, `Dockerfile` (python:3.13-slim, Nicht-root-User, `uvicorn --workers 1 --proxy-headers --port $PORT`), `compose.yaml` nach Toolsite-Konvention (noch **nicht** in `/docker-compose.yml` eintragen).
2. [x] **Datenbank:** SQLAlchemy-Setup mit SQLite-Pragmas (WAL, `foreign_keys`), Alembic, Modelle für Phase 1 (members, settings, chores, rota_configs, chore_entries, chore_swaps, expense_categories, expenses, expense_shares, settlements, shopping_items, notes, info_pages, activity_log). Migration beim Containerstart.
3. [x] **CLI:** `init --seed`, `show-link` (mit QR), `rotate-link`, `logout-all`, `backup`, `add-member`.
4. [x] **Zugang:** Join-Link, signierte Cookies, 404-Gate-Middleware, `/welcome`, CSRF (Origin + Token), Rate-Limit, Security-Header/CSP. Tests aus Spec §10.3.
5. [x] **Grundlayout:** i18n (`t()`, Babel), `base.html`, `app.css` mit Tokens, selbst gehostete Schriften, htmx lokal, Icon-Sprite, Bottom-Bar mit „+“-Sheet (`<dialog>` + Fallback `/new`), Profil-Avatar. i18n-Paritätstest.
6. [x] **Putzplan:** (Hero-Karte folgt in Schritt 10 zusammen mit der Startseite, die sie trägt) `services/rota.py` + Tests aus Spec §10.1, Seite `/chores` (Woche blättern, erledigt/auslassen/rückgängig, nächste Wochen), Hero-Karte auf Start.
7. [x] **Ausgaben:** (Formular noch unstyled - großes Betragsfeld, Avatar-Grid etc. kommen in der Qualitätsrunde) `services/ledger.py` + Tests aus Spec §10.2 (inkl. Eigenschaftstest), `/expenses`, `/expenses/new`, Bearbeiten, Löschen, Ausgleich, `/expenses/all`.
8. [x] **Einkaufsliste:** `/shopping`, Abhaken mit htmx-Fragment, „als Ausgabe eintragen“, erledigte entfernen.
9. [x] **Pinnwand (Basis):** Notizen und WG-Infos (`/board`).
10. [ ] **Startseite komplett** nach `docs/design.md` §5.2.
11. [ ] **Profil und Einstellungen:** Name wechseln, Sprache, Mitglieder, Aufgaben, Rotation neu festlegen (mit Vorschau), Kategorien, Zugang (Link + QR, erneuern, alle abmelden).
12. [ ] **Protokoll und Papierkorb:** Anzeige, Wiederherstellen, Job zum endgültigen Löschen.
13. [ ] **PWA:** Manifest, Icons, Service Worker, Offline-Seite.
14. [ ] **Backup-Job** (03:30) + Admin-ntfy bei Fehlern.
15. [ ] **Qualitätsrunde:** alle Seiten bei 360/390 px, Tastatur und Screenreader-Labels, Kontraste, DE/EN-Durchsicht, Smoke-Test aller GET-Routen.
16. [ ] **Umstieg in der Toolsite** nach `docs/module-integration.md`: Include-Zeile tauschen, Caddy-Block ohne Basic Auth, `module.json`, Dummy `modules/wg-manager/` entfernen, README/`.env.example` anpassen.
17. [ ] Lokal testen (du), dann `./scripts/deploy.sh` auf dem VPS, `init`, Link in der WG-Gruppe teilen (du)
18. [ ] Zwei Wochen Alltagstest mit allen vier

## Phase 2 · Alltag
- [ ] Abwesenheiten (inkl. Wirkung auf Putzplan und Erinnerungen)
- [ ] Tauschen und Vertretung im Putzplan
- [ ] ntfy-Erinnerungen mit Schaltern pro Person, Profil-Karte mit Topic und QR
- [ ] Wiederkehrende Ausgaben (+ Schalter „Monatlich“ im Formular)
- [ ] Vorräte mit Verknüpfung zur Einkaufsliste, Schnellauswahl häufiger Artikel
- [ ] Feedback der WG sammeln

## Phase 3 · Komfort
- [ ] Termine mit Wiederholung + iCal-Abo
- [ ] Abstimmungen
- [ ] Statistiken
- [ ] CSV-Export
- [ ] Dunkelmodus finalisieren
- [ ] Optional: eigener ntfy-Server auf dem VPS

## Offene Punkte (siehe CLAUDE.md §12)
- [ ] Ausgaben-Kategorien bestätigen
- [ ] Ausgleich vom Empfänger bestätigen lassen? (Standard: nein)
- [ ] Müll-/Containertermine für den Kalender
- [ ] Ziel für die externe Backup-Kopie
- [ ] Name der App
