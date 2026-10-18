# Entscheidungslog

Neue Entscheidungen oben anhängen. Format: Datum · Entscheidung · Begründung · Alternativen.

| Datum | Entscheidung | Begründung | Verworfen |
| --- | --- | --- | --- |
| 2026-10-18 | **WG-App wird Toolsite-Modul** `modules/wg/` unter `https://<DOMAIN>/wg/` und ersetzt den Dummy `wg-manager`. Kein eigenes Caddy, keine Basic Auth, Domain statt IP-Zertifikat | Toolsite (Landing + Module) läuft bereits mit Domain; ein Repo, ein Deploy-Skript; geheimer Link ersetzt Basic Auth (Nutzerwunsch: kein Login) | eigenes Repo `wg-app` mit eigenem Caddy (Konflikt um Ports 80/443) |
| 2026-10-18 | Code-Entwicklung in **Claude Code** mit privatem GitHub-Repo, Planung/Design weiter im Claude-Chat | Versionsverlauf, Tests, Commits; der VPS holt Updates per `git pull` | Code nur im Chat erzeugen |
| 2026-10-18 | **Navigation:** Bottom-Bar Start · Putzplan · (+) · Ausgaben · Einkauf; „+“ öffnet ein Sheet für alle Einträge; Profil über Avatar oben rechts; Pinnwand über eine Karte auf der Startseite | Vom Nutzer gewünscht: einfacher und intuitiver. Ein Ort zum Eintragen, vier klare Bereiche | 5 Tabs inkl. „WG“ (zu unklar), schwebender FAB (verdeckt Inhalte) |
| 2026-10-18 | **Putzplan-Start** Montag 2026-10-19 (KW 43): Jakob Großes Bad, Clara Boden, Bato Küche & Müll, Daniel Kleines Bad. Reihenfolge Boden → Küche & Müll → Großes Bad → Kleines Bad | Vom Nutzer vorgegeben | – |
| 2026-10-18 | **Ausgaben starten bei null** | Vom Nutzer entschieden | Nachtragen seit Einzug |
| 2026-10-18 | To-dos stehen im Masterplan (Abschnitt To-dos) und in `docs/roadmap.md`, kein eigenes Tool | Nutzer: „nur irgendwo abrufbar“ | separates Task-Tool |
| 2026-10-17 | **Zugang über geheimen Link**, danach Namenswahl, keine Passwörter | Nutzer wünscht „ohne extra Login“; der Link schützt vor Fremden, das Protokoll schafft Nachvollziehbarkeit | WG-Passwort, Accounts |
| 2026-10-17 | **Erinnerungen über ntfy**, pro Person und Art an/aus, zunächst ntfy.sh | Nutzerwunsch; einfache App, keine eigene Push-Infrastruktur nötig | Telegram, Web-Push, E-Mail |
| 2026-10-17 | ~~**HTTPS direkt über die IPv4-Adresse**~~ (ersetzt am 18.10.: Domain der Toolsite) mit Let’s-Encrypt-IP-Zertifikat (Profil `shortlived`) via Caddy | Nutzer möchte SSL nur mit IPv4. Seit 15.01.2026 möglich | Domain (bleibt Plan B), selbst signiert |
| 2026-10-17 | **Hosting auf eigenem netcup VPS piko**, nicht als Claude-Artifact | Nutzerwunsch; Daten bleiben bei der WG | PaaS, Artifact |
| 2026-10-17 | **Stack:** Python/FastAPI, Jinja2 + htmx, SQLite, Caddy, Docker Compose | Wartungsarm, kein Build-Schritt, eine Datei als Datenbank, gut lesbar | SPA (React/Vue), Postgres, Node |
| 2026-10-17 | **Ausgelassen mit Grund → Rotation läuft normal weiter**, nichts wird nachgeholt | Nutzer-Regel | Nachholen, Verschieben |
| 2026-10-17 | **Ausgaben gleichmäßig** auf alle aktiven Mitglieder, Teilnehmer abwählbar | Nutzerwunsch, Abwählen für Sonderfälle (z. B. „ohne Bato“) | Gewichtungen, Prozente |
| 2026-10-17 | **Zweisprachig DE/EN**, umschaltbar pro Person | Nutzerwunsch („auch Englisch“) | nur Deutsch |
| 2026-10-17 | **Alle Zusatzfunktionen** (Abwesenheiten, Pinnwand, Termine, Vorräte, Abstimmungen, Statistiken, wiederkehrende Ausgaben) umsetzen, gestaffelt in Phasen | Nutzerwunsch: „fully featured WG-Management-System“ | – |
| 2026-10-17 | **Schriften und Skripte selbst hosten** | Datenschutz (Google-Fonts-Urteile in DE), CSP, Unabhängigkeit | CDNs |
