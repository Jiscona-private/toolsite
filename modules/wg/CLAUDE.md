# CLAUDE.md – WG-App (toolsite-Modul `modules/wg`)

> **Wichtig – Toolsite-Modul (gilt vor allem anderen in dieser Datei und in `docs/`):**
> Die WG-App läuft als Modul der Toolsite (dieses Repository) und **ersetzt das alte Dummy-Modul `modules/wg-manager`**. Die Regeln des Repos stehen in `/README.md` und `/docs/ADDING_MODULES.md` und gelten zusätzlich. Daraus folgt:
> - **Pfad-Präfix `/wg`:** Die App läuft unter `https://<DOMAIN>/wg/`. Alle Pfade in diesen Dokumenten (`/`, `/join/<token>`, `/welcome`, `/healthz`, `/manifest.webmanifest`, `/sw.js` …) sind **relativ zu `BASE_PATH`** (Env-Variable, Standard `/wg`). Die App mountet alle Routen unter `BASE_PATH` (Caddy nutzt `handle`, nicht `handle_path`) und baut jeden Link, jede Form-Action und jeden Redirect mit `BASE_PATH`. Cookies mit `Path=/wg`, PWA-`start_url` und Service-Worker-Scope `/wg/` (Service Worker unter `/wg/sw.js`).
> - **Kein eigenes Caddy, kein eigener Port nach außen:** Das Toolsite-Caddy (`/Caddyfile`) leitet `/wg*` an den Container `wg:3000` im Netz `toolsite_net`. Die App liest `PORT` (3000) aus der Umgebung. Die Domain kommt aus `DOMAIN` (normales Let’s-Encrypt-Zertifikat, kein IP-Zertifikat nötig).
> - **Keine Basic Auth vor `/wg`:** Zugang nur über den geheimen Link (§7.3). Der `/wg*`-Block im Caddyfile bekommt beim Umstieg **keinen** `basic_auth`.
> - **Modul-Dateien:** `modules/wg/compose.yaml` (Service `wg`, `build: .`, Volume `./data:/data`, Env `PORT=3000`, `BASE_PATH=/wg`, `APP_BASE_URL=https://${DOMAIN}/wg`, `SECRET_KEY`, Netz `toolsite_net` **ohne** `external: true`), `modules/wg/Dockerfile`, `modules/wg/module.json` (`id` `wg`, `path` `/wg/`). `module.json` erst anlegen, wenn das Modul läuft, sonst zeigt die Landing-Page eine doppelte Karte.
> - **Umstieg (letzter Schritt von Phase 1):** in `/docker-compose.yml` `modules/wg-manager/compose.yaml` durch `modules/wg/compose.yaml` ersetzen, Caddy-Block `/wg*` → `reverse_proxy wg:3000` ohne Basic Auth, `WG_BASIC_AUTH_*` aus `/docker-compose.yml`/`.env.example` entfernen, `SECRET_KEY` (bzw. `WG_SECRET_KEY`) ergänzen, `modules/wg-manager/` löschen, `/README.md` aktualisieren. Details: `docs/module-integration.md`.
> - **Backups:** zusätzlich zum App-eigenen Backup sichert `/scripts/backup.sh` `modules/*/data`.
> - Arbeitsverzeichnis für Befehle ist `modules/wg/`.

Diese Datei ist die Arbeitsgrundlage für Claude Code in diesem Repository. Sie fasst alle Entscheidungen aus der Planungsphase zusammen (Masterplan, klickbare Design-Vorschau, Chat vom 17./18.10.2026). Die Details stehen in `docs/`:

| Datei | Inhalt |
| --- | --- |
| `docs/spec.md` | Technische Spezifikation: Datenmodell, Routen, Algorithmen, Zugang, Erinnerungen, Jobs, **Testvektoren** |
| `docs/design.md` | Design-System: Farben, Schrift, Komponenten, Navigation, jeder Screen im Detail |
| `docs/design/screens/` | Die Vorschau-Screens als eigenständige HTML-Dateien (im Browser öffnen, `index.html`) |
| `docs/module-integration.md` | Einbindung in die Toolsite, Umstieg vom Dummy, Deployment |
| `docs/roadmap.md` | Phasen und To-do-Liste, **Implementierungsreihenfolge für Phase 1** |
| `docs/decisions.md` | Entscheidungslog: was wurde warum entschieden |

Ändert sich eine Entscheidung, werden diese Datei und `docs/decisions.md` im selben Commit nachgezogen. Erledigte Punkte werden in `docs/roadmap.md` abgehakt.

---

## 1. Projekt in einem Absatz

Selbst gehostete Web-App für eine Vierer-WG (Jakob, Clara, Daniel, Bato). Kern: **wöchentlich rotierender Putzplan**, **geteilte Ausgaben mit automatischer Abrechnung** („wer zahlt wem“) und **Einkaufsliste**. Danach folgen Abwesenheiten, Vorräte, Pinnwand, Termine, Abstimmungen, Erinnerungen über ntfy und Statistiken. Die App läuft auf einem **netcup VPS piko** und ist als Toolsite-Modul unter **`https://<DOMAIN>/wg/`** erreichbar. Es gibt **keinen Login**: Zugang über einen geheimen Link, danach wählt jeder einmal seinen Namen. Die App ist mobile-first, als PWA installierbar und zweisprachig (Deutsch/Englisch).

Die App darf **nicht** auf fremden Plattformen laufen (kein Claude-Artifact, kein PaaS). Ziel ist ein vollwertiges, wartungsarmes WG-Management-System.

## 2. Zusammenarbeit mit dem Projektinhaber

- Der Projektinhaber ist einer der vier Mitbewohner und betreibt den VPS. Er hat schon einmal einen VPS eingerichtet, ist aber kein Vollzeit-Entwickler: Erklärungen kurz und konkret halten, Befehle immer vollständig angeben.
- **Kommunikation mit ihm: Deutsch.** Professionell, aber locker.
- **Code, Bezeichner, Code-Kommentare, Commit-Messages: Englisch.** UI-Texte ausschließlich über i18n (DE und EN).
- Er arbeitet oft vom Handy. Ergebnisse so zusammenfassen, dass sie auf einen Handybildschirm passen.
- Bei Fragen, die nur er beantworten kann (siehe §12 Offene Punkte), **fragen statt raten**. Bei technischen Details mit klarem Standard: entscheiden, im Commit/PR kurz begründen.

## 3. Harte Regeln (nie brechen)

1. **Geld ist immer Integer-Cent** (`int`). Nie `float`. Anzeige über Babel mit `Decimal(cents) / 100`.
2. **Keine hart kodierten UI-Texte** in Templates oder Python. Immer `t("key")`, immer in `de.json` **und** `en.json` (ein Test prüft Schlüsselgleichheit).
3. **Jede schreibende Aktion** erzeugt einen Eintrag in `activity_log`. **Löschen ist Soft-Delete** (`deleted_at`), Papierkorb 30 Tage, Wiederherstellen möglich.
4. **Ohne gültiges Zugangs-Cookie antwortet jede Route mit 404** und neutralem Body (`Not Found`), nie 401/403, nie App-Name, nie Redirect. Ausnahmen: `/join/<token>`, `/healthz`, `/cal/<token>.ics` (jeweils unter `BASE_PATH`).
5. **Keine externen Ressourcen im Browser**: keine CDNs, keine Google Fonts (DSGVO), kein Analytics. Schriften, htmx und Icons liegen in `app/static/`.
6. **Keine Secrets im Repo**: `.env`, `data/`, Backups und Datenbankdateien sind in `.gitignore`.
7. **Uvicorn läuft mit genau einem Worker.** Der Scheduler läuft im App-Prozess, mehrere Worker würden Jobs doppelt ausführen.
8. **Zeitzone `Europe/Berlin`** für alle fachlichen Zeitpunkte. Eine Woche läuft von Montag 00:00 bis Sonntag 23:59 Ortszeit. Zeitstempel werden in der DB in UTC gespeichert, reine Daten als `date`.
9. **Benachrichtigungen dürfen nie eine Anfrage scheitern lassen.** Fehler werden geloggt, die Anfrage läuft weiter (Versand nach dem Commit, im Hintergrund).
10. **Mobile-first:** Jede Seite funktioniert bei 360–390 px Breite ohne horizontales Scrollen. Touch-Ziele sind mindestens 44 × 44 px.
11. **Progressive Enhancement:** Jedes Formular funktioniert auch ohne JavaScript (normales POST, `303` Redirect). htmx macht es nur schneller.
12. **Vor jedem „fertig“:** `uv run ruff check .`, `uv run ruff format --check .` und `uv run pytest` sind grün.
13. **Fachregeln** (Rotation, Abrechnung, Zugang) werden **nicht ohne Rückfrage geändert.** Sie sind mit dem Nutzer abgestimmt.

## 4. Tech-Stack

| Baustein | Wahl | Hinweis |
| --- | --- | --- |
| Sprache | Python 3.13 | Typannotationen überall |
| Paketverwaltung | `uv` mit `pyproject.toml` + `uv.lock` | keine `requirements.txt` |
| Web | FastAPI + Uvicorn (1 Worker) | **synchrone** Endpunkte (`def`), kein async nötig |
| Templates | Jinja2 (serverseitig gerendert) | Partials für htmx-Fragmente |
| Interaktion | htmx 2.x, lokal in `app/static/js/` | `hx-boost` auf `<body>`, gezielte Swaps für Abhaken |
| Formulare | `python-multipart` | |
| Datenbank | SQLite (WAL-Modus, `foreign_keys=ON`) | Datei `/data/wg.db` |
| ORM / Migrationen | SQLAlchemy 2.0 (typed ORM) + Alembic | jede Schemaänderung = Migration |
| Konfiguration | `pydantic-settings` (`.env`) | |
| Cookies / Tokens | `itsdangerous` (signierte Cookies), `secrets` | |
| Lokalisierung | eigene JSON-Dateien + `babel` für Datum/Zahl/Währung | |
| Jobs | APScheduler `>=3.10,<4` (BackgroundScheduler) | Cron-Trigger in `Europe/Berlin` |
| HTTP-Client | `httpx` (ntfy) | Timeout 5 s |
| QR-Codes | `segno` (SVG) | Beitrittslink, ntfy-Topic |
| Kalender (Phase 3) | `icalendar` | |
| Tests | `pytest` + FastAPI `TestClient` | In-Memory-SQLite oder tmp-Datei |
| Lint/Format | `ruff` (lint + format) | Zeilenlänge 100 |
| Webserver | Toolsite-Caddy (`/Caddyfile`) | HTTPS über die Domain, Routing `/wg*` |
| Deployment | Docker Compose `include:` der Toolsite | Modul-`compose.yaml` |
| Push | ntfy (zunächst `https://ntfy.sh`) | JSON-Publish |

**Bewusst nicht:** React/Vue/SPA, Tailwind-Build, Node im Produktivbetrieb, Postgres, Redis, Celery, OAuth/Accounts, externe Fonts/CDNs. Neue Abhängigkeiten nur mit gutem Grund (im Commit begründen).

## 5. Projektstruktur (Ziel)

```
modules/wg/
├── CLAUDE.md
├── README.md
├── pyproject.toml / uv.lock
├── Dockerfile
├── compose.yaml                # Modul-Compose (toolsite_net)
├── module.json                 # für die Landing-Page (erst beim Umstieg)
├── .env.example
├── alembic.ini
├── migrations/                 # Alembic
├── app/
│   ├── main.py                 # create_app(): Middleware, Router, Scheduler-Start
│   ├── config.py               # Settings (pydantic-settings)
│   ├── db.py                   # Engine, Session, SQLite-Pragmas
│   ├── cli.py                  # python -m app.cli init|show-link|rotate-link|logout-all|backup
│   ├── auth.py                 # Join-Link, Cookies, Member-Auswahl, CSRF, 404-Gate
│   ├── i18n.py                 # t(), Babel-Formatierer, Sprachwahl
│   ├── i18n/de.json, en.json
│   ├── models/                 # SQLAlchemy-Modelle, eine Datei je Bereich
│   ├── services/               # reine Fachlogik, gut testbar
│   │   ├── rota.py             # Putzplan-Rotation
│   │   ├── ledger.py           # Anteile, Salden, „wer zahlt wem“
│   │   ├── shopping.py, supplies.py, absences.py, board.py, polls.py
│   │   ├── activity.py         # Protokoll + Papierkorb
│   │   ├── notify.py           # ntfy-Versand
│   │   └── backup.py
│   ├── routes/                 # FastAPI-Router je Bereich (dünn, rufen services auf)
│   ├── scheduler.py            # Job-Definitionen
│   ├── templates/
│   │   ├── base.html           # Layout, Bottom-Navigation, Sheet-Container
│   │   ├── partials/           # Karten, Listenzeilen, Chips, Formularteile
│   │   └── pages/              # eine Datei je Screen
│   └── static/
│       ├── css/app.css         # Design-Tokens + Komponenten (kein Framework)
│       ├── js/htmx.min.js, app.js
│       ├── fonts/              # Bricolage Grotesque, Figtree (woff2, OFL)
│       ├── icons/              # App-Icons 192/512 (maskable)
│       ├── manifest.webmanifest
│       └── sw.js
├── deploy/
│   ├── seed.toml               # Startdaten der WG
├── tests/
└── docs/
```

## 6. Befehle

Diese Befehle existieren, sobald das Gerüst (Phase 1, Schritt 1) steht. Ändern sie sich, hier aktualisieren.

```bash
uv sync                                         # Abhängigkeiten
uv run alembic upgrade head                     # DB migrieren
uv run python -m app.cli init --seed deploy/seed.toml   # Startdaten + Beitrittslink ausgeben
uv run uvicorn app.main:app --reload            # lokal starten (http://127.0.0.1:8000)
uv run python -m app.cli show-link              # Beitrittslink anzeigen
uv run pytest                                   # Tests
uv run ruff check . && uv run ruff format --check .
# Produktion (auf dem VPS, im Toolsite-Root):
./scripts/deploy.sh
docker compose exec wg python -m app.cli init --seed deploy/seed.toml
```

Lokal ohne HTTPS: In der Entwicklung setzt `APP_ENV=dev` das Cookie-Flag `Secure` auf `false`.

## 7. Fachregeln (Kurzfassung, Details in `docs/spec.md`)

### 7.1 Putzplan

- **Aufgaben** (Reihenfolge = Rotationsreihenfolge): `floor` Boden/Floor · `kitchen` Küche & Müll/Kitchen & Trash · `big_bath` Großes Bad/Large Bathroom · `small_bath` Kleines Bad/Small Bathroom.
- **Woche:** Montag bis Sonntag. Jede Woche rückt jede Person **eine Aufgabe weiter** in der Reihenfolge Boden → Küche & Müll → Großes Bad → Kleines Bad → Boden.
- **Start:** KW 43, Montag **2026-10-19**: Clara Boden, Bato Küche & Müll, Jakob Großes Bad, Daniel Kleines Bad.
- **Berechnet, nicht gespeichert:** Die Zuteilung ergibt sich aus `rota_configs` (Startwoche + Slot-Reihenfolge). Gespeichert wird nur, was passiert ist: erledigt, ausgelassen, getauscht.
- Formel: Person in Slot `s` macht in Woche `k` (Wochen seit `valid_from`) die Aufgabe mit Index `(s + k) mod n`, `n = max(#Mitglieder, #Aufgaben)`. Index ≥ #Aufgaben bedeutet „frei“.
- **Status je Aufgabe und Woche:** offen · erledigt · ausgelassen (Grund ist Pflicht) · nicht erledigt (vergangene Woche ohne Eintrag, neutral grau).
- **Ausgelassen mit Grund → Rotation läuft ganz normal weiter.** Es wird nichts nachgeholt oder verschoben.
- **Tauschen:** Zwei Personen tauschen für **eine** Woche ihre Aufgaben.
- **Vertretung:** Jemand anderes hakt ab. `done_by` ≠ zugeteilte Person, das ist sichtbar.
- **Abwesenheit** über die komplette Woche (Mo–So) → Aufgabe wird automatisch als „ausgelassen – abwesend“ angezeigt (berechnet). Teilweise Abwesenheit → nur Hinweis.
- **Ein- und Auszug:** neue `rota_config` ab einer Woche. Die bisherigen Mitglieder behalten ihre ohnehin „nächste“ Aufgabe, neue Mitglieder füllen freie Slots (Algorithmus in der Spec).

### 7.2 Ausgaben und Abrechnung

- **Start bei null**, nichts wird nachgetragen.
- Eine Ausgabe hat: Betrag (Cent), Beschreibung, bezahlt von, Kategorie, Datum, Teilnehmer.
- **Standard: gleichmäßig auf alle aktiven Mitglieder.** Teilnehmer lassen sich abwählen (z. B. „ohne Bato“). Der Zahler muss nicht Teilnehmer sein.
- **Rundung:** `base = betrag // n`, Rest `r` Cent gehen reihum an `r` Teilnehmer, rotierender Startindex `expense.id mod n` (Reihenfolge nach `members.position`). Anteile werden in `expense_shares` **gespeichert** (Invariante: Summe = Betrag).
- **Saldo** = bezahlt − eigene Anteile + gesendete Ausgleiche − empfangene Ausgleiche.
- **Wer zahlt wem:** gierig größter Schuldner an größten Gläubiger, höchstens `n − 1` Überweisungen. Gleichstand → nach `members.position`.
- **Ausgleich:** „Als überwiesen markieren“ legt ein `settlement` an. Der Empfänger bekommt eine ntfy-Nachricht. Eine Bestätigung durch den Empfänger ist **vorerst nicht nötig** (offener Punkt).
- **Wiederkehrende Ausgaben** (Phase 2): monatlich (Tag 1–28) oder wöchentlich, werden täglich um 06:00 fällig angelegt.
- Ausgezogene Mitglieder behalten ihren Saldo, bis er null ist. Bei neuen Ausgaben sind sie nicht vorausgewählt.

### 7.3 Zugang

- **Geheimer Link** `https://<DOMAIN>/wg/join/<token>` (Token: `secrets.token_urlsafe(32)`). Bei Erfolg wird das Cookie `wg_auth` gesetzt (signiert, enthält `cookie_version`, 400 Tage, `HttpOnly`, `Secure`, `SameSite=Lax`), danach Redirect `303` auf `/welcome` (Namenswahl) oder `/`.
- **Namenswahl** `/welcome` setzt das Cookie `wg_member` (signierte Member-ID). Wechsel jederzeit im Profil. Es gibt bewusst keine Passwörter pro Person.
- **Link erneuern:** neuer Token, alter Link ungültig, eingeloggte Geräte bleiben drin. **Alle abmelden:** `cookie_version += 1`.
- Rate-Limit auf `/join`: 10 Fehlversuche pro IP in 15 Minuten, danach ebenfalls 404. Admin bekommt einmalig eine ntfy-Nachricht.
- CSRF: Origin-Prüfung **und** Token (HMAC über Session) für alle unsicheren Methoden. htmx sendet ihn als Header `X-CSRF-Token`, Formulare als Hidden-Feld.

### 7.4 Einkauf und Vorräte

- Einkaufsliste: Artikel + optional Menge/Notiz. Abhaken heißt „im Wagen“. Mit „Als Ausgabe eintragen“ geht es zu einer neuen Ausgabe mit vorbefüllter Beschreibung. Nach dem Speichern werden die Artikel archiviert und mit der Ausgabe verknüpft.
- Vorräte (Phase 2): Status genug/wird knapp/leer. „Wird knapp“ oder „leer“ legt automatisch einen Einkaufsartikel an (falls keiner offen ist). Ist der Artikel gekauft, steht der Vorrat wieder auf „genug“.

### 7.5 Erinnerungen (Phase 2)

- Jede Person hat ein eigenes, zufälliges ntfy-Topic (`wg-<8 Zeichen>-<name>`) und schaltet die Arten im Profil einzeln an oder aus.
- Standards: Aufgabe nächste Woche (So 18:00, an) · Aufgabe noch offen (Fr 18:00, an) · Geld erhalten (sofort, an) · neue Ausgabe, die mich betrifft (aus) · Vorrat leer/Einkaufsartikel (aus) · Termin morgen (Vorabend 19:00, aus).
- Während einer Abwesenheit gibt es keine Putz-Erinnerungen. Nachrichten bleiben kurz, **ohne Beträge** (sie laufen über ntfy.sh), und kommen in der Sprache des Empfängers.

## 8. Design (Kurzfassung, Details in `docs/design.md`)

- Ruhiges, freundliches Grün: Akzent `#1F6F5C`, Grund `#F4F5F1`, Karten weiß mit Rand `#E2E5DF`, Radius 20 px.
- Schriften: **Bricolage Grotesque 700** für Überschriften und große Zahlen, **Figtree** 400–700 für alles andere. Beide selbst gehostet. Geldbeträge mit `font-variant-numeric: tabular-nums`.
- **Navigation:** Bottom-Bar mit **Start · Putzplan · (+) · Ausgaben · Einkauf**. Das **(+)** in der Mitte öffnet ein Sheet: Ausgabe · Einkaufsliste · Notiz an die Pinnwand · Termin oder Abstimmung · Abwesenheit. **Profil** über den Avatar oben rechts auf jedem Hauptscreen. **Pinnwand** über eine Karte auf der Startseite. Unterseiten haben „‹ Zurück“, Formulare haben „✕ Abbrechen“.
- Status nie nur über Farbe: Chips mit Text (offen, erledigt, ausgelassen).
- Die Referenz-Screens liegen in `docs/design/screens/`. Sie sind **verbindlich für Layout, Abstände und Inhalte**. Inline-Styles dort sind nur Mockup: in der App wird alles über Klassen in `app.css` gelöst (CSP erlaubt keine Inline-Styles).

## 9. Tests und Qualität

- **Fachlogik in `services/` ist rein und vollständig getestet.** Router bleiben dünn.
- **Pflicht-Testvektoren** stehen in `docs/spec.md` §10, unter anderem:
  - Rotation KW 43–47 (genaue Tabelle), Tauschen, Auslassen ändert nichts, Ein- und Auszug, mehr Personen als Aufgaben.
  - Abrechnung mit dem Vorschau-Beispiel: Salden Clara +43,40 / Bato +10,80 / Daniel −25,40 / Jakob −28,80 und Überweisungen Jakob→Clara 28,80, Daniel→Clara 14,60, Daniel→Bato 10,80. Rundung 10,00 € auf 3 Personen = 3,34 + 3,33 + 3,33.
  - Zugang: ohne Cookie 404; Join setzt Cookie; erneuerter Link macht den alten ungültig; „Alle abmelden“ wirft alle raus; CSRF ohne Token wird abgewiesen.
  - i18n: `de.json` und `en.json` haben exakt dieselben Schlüssel; kein Template nutzt einen fehlenden Schlüssel.
- Barrierefreiheit: echte `<button>`/`<a>`/`<label>`, sichtbarer Fokus, `aria-current` in der Navigation, Kontrast ≥ 4,5:1.

## 10. Deployment (Kurzfassung, Details in `docs/module-integration.md`)

- Läuft im Toolsite-Stack auf dem netcup VPS piko: Toolsite-Caddy (Domain, automatisches HTTPS) → `wg:3000` im Netz `toolsite_net`.
- Der Container veröffentlicht **keine Ports**. Daten in `modules/wg/data/` (Volume `/data`).
- Update: im Toolsite-Root `./scripts/deploy.sh` (git pull → build → up). Migrationen laufen beim Containerstart. Vorher macht die App selbst ein Backup per CLI (`docker compose exec wg python -m app.cli backup`).
- Backups: App-intern täglich 03:30 nach `/data/backups` (14 Tage) plus `/scripts/backup.sh` der Toolsite.

## 11. Stand und nächste Schritte

- **Planung: abgeschlossen.** Masterplan, Design-Vorschau, Entscheidungen.
- **Phase 0 (VPS): erledigt.** Die Toolsite läuft mit Domain auf dem VPS, derzeit noch mit dem Dummy-Modul `wg-manager` unter `/wg`.
- **Phase 1 (Kern): als Nächstes.** Reihenfolge und Häkchen stehen in `docs/roadmap.md`. Mit Schritt 1 (Gerüst) beginnen, nach jedem Schritt committen.
- Der Dummy bleibt live, bis die neue App fertig ist. Der Umstieg ist der letzte Schritt von Phase 1.

## 12. Offene Punkte (beim Nutzer nachfragen, sobald relevant)

1. **Ausgaben-Kategorien:** Vorschlag Lebensmittel · Putzmittel · Haushalt · Sonstiges (so in `seed.toml`). Bestätigen lassen.
2. **Ausgleich bestätigen:** Muss der Empfänger eine Überweisung bestätigen? Standard bis zur Antwort: nein.
3. **Müll- und Containertermine** für den Kalender: gibt es feste Termine?
4. **Ziel für die externe Backup-Kopie** (eigener Rechner, Cloudspeicher, Storage Box).
5. **Name der App** (bis dahin „WG-App“; kommt aus `settings.wg_name`, nie hart kodiert).

## 13. Was Claude hier nicht tun soll

- Keine Fachregeln eigenmächtig ändern (z. B. Rotation, die nachholt, oder Zinsen bzw. Gewichtungen bei Ausgaben).
- Keine Accounts, Passwörter oder E-Mail-Logins einführen.
- Keine Daten an Dritte senden außer: ntfy (kurze Texte ohne Beträge) und Let’s Encrypt (über das Toolsite-Caddy).
- Keine Migrationen nachträglich ändern, die schon auf dem VPS gelaufen sind. Immer eine neue Migration anlegen.
- Nicht auf `main` force-pushen. Keine Secrets, Datenbanken oder Backups committen.
