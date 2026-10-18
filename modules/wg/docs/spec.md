# Technische Spezifikation – WG-App

Stand: 18.10.2026. Diese Spezifikation ist verbindlich für die Implementierung. Abweichungen nur nach Rückfrage beim Projektinhaber, danach hier und in `docs/decisions.md` nachziehen.

> **Toolsite-Modul:** Alle Pfade hier sind relativ zu `BASE_PATH` (`/wg`), siehe Kasten oben in `CLAUDE.md`. In §9.5 entfallen `PUBLIC_IP` und `ACME_EMAIL` (gehören dem Toolsite-Caddy); neu sind `PORT` (3000) und `BASE_PATH` (`/wg`); `APP_BASE_URL` = `https://<DOMAIN>/wg`.

Inhalt:
1. Begriffe und Grundsätze
2. Datenmodell
3. Putzplan-Rotation
4. Ausgaben und Abrechnung
5. Einkauf, Vorräte, Abwesenheiten, Pinnwand, Termine, Abstimmungen
6. Zugang und Sicherheit
7. Routen und Screens
8. Erinnerungen (ntfy) und Hintergrundjobs
9. Lokalisierung, PWA, Export, Kalender, Logging
10. Testvektoren (Pflicht)

---

## 1. Begriffe und Grundsätze

| Begriff (UI) | Code | Bedeutung |
| --- | --- | --- |
| Mitglied / Mitbewohner | `Member` | Eine Person der WG |
| Aufgabe (Putzplan) | `Chore` | Eine Putzaufgabe, z. B. Großes Bad |
| Woche | `week` | `date` des Montags der Woche (ISO-Woche, Europe/Berlin) |
| Ausgabe | `Expense` | Etwas, das jemand für die WG bezahlt hat |
| Anteil | `ExpenseShare` | Wie viel ein Teilnehmer an einer Ausgabe trägt |
| Ausgleich | `Settlement` | Eine Überweisung zwischen zwei Mitgliedern |
| Saldo | `balance` | positiv = bekommt Geld, negativ = schuldet Geld |
| Einkaufsartikel | `ShoppingItem` | Eintrag auf der Einkaufsliste |
| Vorrat | `Supply` | Verbrauchsartikel mit Füllstand |
| Abwesenheit | `Absence` | Zeitraum, in dem jemand weg ist |
| Notiz | `Note` | Eintrag auf der Pinnwand |
| WG-Info | `InfoPage` | Dauerhafte Info (WLAN, Hausmeister, Regeln) |
| Termin | `Event` | Kalendereintrag |
| Abstimmung | `Poll` | Umfrage mit Optionen |
| Protokoll | `ActivityLog` | Wer hat wann was geändert |

Grundsätze:
- Geldbeträge: `int` Cent. Datumswerte: `date`. Zeitpunkte: `datetime` in UTC (tz-aware), Darstellung in Europe/Berlin.
- Alle IDs sind Integer (Autoincrement).
- Soft-Delete über `deleted_at` (nullable). Standard-Queries filtern gelöschte Einträge aus.
- `created_by` / `updated_by` verweisen auf `members.id` (die Person, die laut `wg_member`-Cookie handelt).

## 2. Datenmodell

Notation: `?` = nullable. Jede Tabelle hat `created_at` (UTC), sofern nicht anders angegeben.

### 2.1 Mitglieder und Einstellungen

**members**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| name | str(40), unique | Anzeigename |
| language | str(2) | `de` \| `en`, Standard `de` |
| color | int | Index in die Avatar-Palette (0–7), siehe design.md |
| position | int | Anzeigereihenfolge, auch Tie-Break in Algorithmen |
| active | bool | ausgezogen = false |
| joined_on | date | |
| left_on | date? | |
| ntfy_topic | str(64), unique | `wg-<8 zufällige Zeichen a–z0–9>-<name-slug>` |
| notify_prefs | JSON | siehe §8.1, Standardwerte beim Anlegen |

**settings** (Key-Value, `key` PK, `value` text)
| Key | Inhalt |
| --- | --- |
| `wg_name` | Anzeigename der App/WG (Standard „WG-App“) |
| `join_token` | aktueller Beitritts-Token (Klartext, Vergleich mit `hmac.compare_digest`) |
| `cookie_version` | Integer als Text, Start `1` |
| `calendar_token` | Token für den iCal-Feed (Phase 3) |
| `default_language` | `de` |
| `admin_ntfy_topic` | Topic für technische Meldungen |

Begründung Klartext-Token: Wer die Datenbank lesen kann, hat ohnehin vollen Zugriff. Der Klartext erlaubt es, den Link in den Einstellungen erneut anzuzeigen (für neue Geräte, inklusive QR-Code).

### 2.2 Putzplan

**chores**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| key | str(32), unique | `floor`, `kitchen`, `big_bath`, `small_bath` |
| name_de / name_en | str(60) | |
| position | int | Rotationsreihenfolge, 0-basiert |
| active | bool | |

**rota_configs**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| valid_from | date | immer ein Montag |
| chore_ids | JSON list[int] | aktive Aufgaben in Rotationsreihenfolge zum Zeitpunkt |
| slots | JSON list[int \| null] | Slot `s` = Mitglied, das in Woche `valid_from` die Aufgabe `chore_ids[s]` macht. Länge `n = max(#Mitglieder, #Aufgaben)`, `null` = leerer Slot |
| created_by | int? | `null` bei Seed |

Die für eine Woche gültige Konfiguration ist die mit dem größten `valid_from ≤ week`.

**chore_entries**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| week | date | Montag |
| chore_id | int FK | |
| assigned_member_id | int? FK | Snapshot der berechneten Zuteilung zum Zeitpunkt der Aktion |
| status | str | `done` \| `skipped` |
| reason | str(200)? | Pflicht bei `skipped` (mind. 3 Zeichen) |
| done_by_member_id | int FK | wer abgehakt oder ausgelassen hat |
| acted_at | datetime | |
| Unique | (week, chore_id) | „Rückgängig“ = Eintrag löschen (protokolliert) |

**chore_swaps**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| week | date | |
| member_a_id, member_b_id | int FK | tauschen ihre Aufgaben nur in dieser Woche |
| created_by | int FK | |
| Unique | (week, member_a_id), (week, member_b_id) | eine Person tauscht höchstens einmal pro Woche |

### 2.3 Ausgaben

**expense_categories**: id, key (unique), name_de, name_en, position, active. Startwerte aus `deploy/seed.toml`.

**expenses**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| description | str(120) | |
| amount_cents | int | > 0, Obergrenze 1 000 000 (10 000 €) als Plausibilitätsprüfung |
| paid_by_id | int FK | |
| category_id | int FK? | |
| spent_on | date | Standard heute |
| recurring_id | int FK? | wenn aus einer wiederkehrenden Ausgabe erzeugt |
| created_by, updated_by | int FK | |
| updated_at | datetime? | |
| deleted_at | datetime? | |

**expense_shares**: (expense_id, member_id) PK, share_cents int ≥ 0. **Invariante:** `sum(share_cents) == amount_cents`.

**settlements**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| from_member_id, to_member_id | int FK | from ≠ to |
| amount_cents | int | > 0 |
| paid_on | date | |
| note | str(120)? | |
| confirmed_at | datetime? | für eine spätere Bestätigungsfunktion, vorerst ungenutzt |
| created_by | int FK | |
| deleted_at | datetime? | |

**recurring_expenses** (Phase 2)
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| description, amount_cents, paid_by_id, category_id | wie expenses | |
| interval | str | `monthly` \| `weekly` |
| day | int | monthly: 1–28, weekly: 0 (Mo) – 6 (So) |
| next_due | date | |
| participant_ids | JSON list[int]? | `null` = alle zum Zeitpunkt aktiven Mitglieder |
| active | bool | |
| created_by | int FK | |

### 2.4 Einkauf und Vorräte

**shopping_items**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| name | str(80) | |
| quantity | str(30)? | frei, z. B. „2 Liter“ |
| note | str(120)? | |
| source | str | `manual` \| `supply` |
| supply_id | int FK? | |
| added_by | int FK | |
| checked_at, checked_by | ? | „im Wagen“ |
| expense_id | int FK? | gesetzt, wenn als Ausgabe eingetragen |
| archived_at | datetime? | erledigt und weggeräumt |
| deleted_at | datetime? | |

**supplies** (Phase 2): id, name, status (`ok` \| `low` \| `empty`), position, active, updated_by, updated_at.

### 2.5 Abwesenheiten, Pinnwand, Termine, Abstimmungen

**absences** (Phase 2): id, member_id, start_date, end_date (inklusive), note str(120)?, created_by, deleted_at.

**notes**: id, body text (≤ 1000 Zeichen, reiner Text, URLs werden verlinkt), pinned bool, expires_on date?, created_by, deleted_at.

**info_pages**: id, title str(60), body text (≤ 4000, reiner Text mit Zeilenumbrüchen), position, updated_by, updated_at.

**events** (Phase 3): id, title str(80), starts_on date, start_time time?, end_time time?, location str(80)?, recurrence (`none` \| `weekly` \| `biweekly` \| `monthly`), recurrence_until date?, note?, created_by, deleted_at.

**polls** (Phase 3): id, question str(140), created_by, closes_at datetime?, closed_at datetime?, deleted_at.
**poll_options**: id, poll_id, label str(60), position.
**votes**: (poll_id, member_id) PK, option_id, voted_at. Die Stimme lässt sich bis zum Schluss ändern.

### 2.6 Protokoll

**activity_log**
| Spalte | Typ | Hinweis |
| --- | --- | --- |
| id | int PK | |
| at | datetime | |
| actor_member_id | int? | `null` = System/Job |
| action | str | `create`, `update`, `delete`, `restore`, `check`, `uncheck`, `done`, `skip`, `undo`, `swap`, `settle`, `vote`, `join`, `rotate_link`, `logout_all` |
| entity | str | z. B. `expense` |
| entity_id | int? | |
| summary_key | str | i18n-Schlüssel, z. B. `log.expense.create` |
| summary_params | JSON | z. B. `{"description": "Großeinkauf"}` |
| before, after | JSON? | Zustand für Nachvollziehbarkeit und Wiederherstellen |

Papierkorb = alle Entitäten mit `deleted_at` aus den letzten 30 Tagen. Wiederherstellen setzt `deleted_at = null` und protokolliert `restore`. Ein täglicher Job löscht endgültig, was älter als 30 Tage ist.

## 3. Putzplan-Rotation

### 3.1 Zuteilung berechnen

```
def assignment(week):                       # week = Montag
    cfg = latest rota_config with valid_from <= week
    if cfg is None: return {}               # vor Start: kein Plan
    k = (week - cfg.valid_from).days // 7
    n = len(cfg.slots)                      # = max(#members, #chores) zum Zeitpunkt
    result = {chore_id: None for chore_id in cfg.chore_ids}
    for s, member_id in enumerate(cfg.slots):
        if member_id is None: continue
        idx = (s + k) % n
        if idx < len(cfg.chore_ids):
            result[cfg.chore_ids[idx]] = member_id
        # sonst: Person ist diese Woche "frei"
    apply swaps of this week: exchange the chores of member_a and member_b
    return result                           # chore_id -> member_id | None ("unbesetzt")
```

Startkonfiguration (Seed): `valid_from = 2026-10-19`, `chore_ids = [floor, kitchen, big_bath, small_bath]`, `slots = [Clara, Bato, Jakob, Daniel]`.

### 3.2 Status je Woche und Aufgabe

Reihenfolge der Prüfung:
1. Es gibt einen `chore_entry` → dessen Status (`done` / `skipped`).
2. Die zugeteilte Person ist in dieser Woche komplett abwesend (Abwesenheit deckt Mo–So) → `skipped` mit Grund „abwesend“ (berechnet, nicht gespeichert; ein echter Eintrag hat Vorrang, z. B. wenn jemand vertritt).
3. Woche liegt in der Vergangenheit → `missed` („nicht erledigt“, neutral grau, keine Konsequenz).
4. Sonst `open`.

Aktionen (jeweils protokolliert):
- **Erledigt:** jedes Mitglied darf jede Aufgabe abhaken (Vertretung). `assigned_member_id` wird als Snapshot gespeichert.
- **Auslassen:** Grund ist Pflicht. Die Rotation ändert sich nicht.
- **Rückgängig:** löscht den Eintrag (nur für die aktuelle und die vorige Woche).
- **Tauschen:** zwei Personen, eine Woche. Gültig für die aktuelle und künftige Wochen. Ein bestehender Tausch lässt sich aufheben.

### 3.3 Besetzung oder Aufgaben ändern

Auslöser: Mitglied hinzufügen oder deaktivieren, Aufgabe hinzufügen oder deaktivieren, „Rotation neu festlegen“. Die neue Konfiguration gilt ab `W` = nächster Montag (in der Einstellungsseite wählbar: diese oder nächste Woche).

```
def rebuild(W, members_new, chores_new):
    old = assignment(W) without swaps          # chore_id -> member_id
    n = max(len(members_new), len(chores_new))
    slots = [None] * n
    # 1) Bisherige Mitglieder behalten ihre "nächste" Aufgabe (Kontinuität)
    for chore_id, member_id in old.items():
        if member_id in members_new and chore_id in chores_new:
            slots[chores_new.index(chore_id)] = member_id
    # 2) Alle übrigen Mitglieder (neu oder bisher "frei") füllen freie Slots,
    #    zuerst Slots mit Aufgabe (Index < len(chores_new)), Reihenfolge nach members.position
    for m in members_new not yet placed (sorted by position):
        slots[first free index] = m
    insert rota_config(valid_from=W, chore_ids=chores_new, slots=slots)
```

Die Einstellungsseite zeigt vor dem Speichern eine Vorschau der nächsten vier Wochen.

## 4. Ausgaben und Abrechnung

### 4.1 Anteile berechnen

```
def split(expense_id, amount_cents, participants):   # participants sortiert nach position
    n = len(participants)
    base, r = divmod(amount_cents, n)
    start = expense_id % n
    shares = {m: base for m in participants}
    for i in range(r):
        shares[participants[(start + i) % n]] += 1
    return shares                                    # Summe == amount_cents
```

Dazu wird zuerst die Ausgabe eingefügt (`flush`, um die ID zu bekommen), dann werden die Anteile geschrieben. Beim Bearbeiten von Betrag oder Teilnehmern werden die Anteile neu berechnet.

### 4.2 Saldo

```
balance(m) =  Σ expenses.amount_cents where paid_by = m
            − Σ expense_shares.share_cents where member = m
            + Σ settlements.amount_cents where from = m
            − Σ settlements.amount_cents where to = m
(nur nicht gelöschte Ausgaben und Ausgleiche)
Invariante: Σ balance(m) über alle Mitglieder == 0
```

### 4.3 Wer zahlt wem

```
def transfers(balances):                       # dict member -> cents
    debtors   = [(-b, m) for m, b in balances if b < 0]
    creditors = [( b, m) for m, b in balances if b > 0]
    result = []
    while debtors and creditors:
        sort both by (amount desc, position asc)
        (d, dm), (c, cm) = debtors[0], creditors[0]
        x = min(d, c)
        result.append((dm, cm, x))
        update both, drop entries that reached 0
    return result                              # höchstens n-1 Einträge
```

Auf dem Screen „Ausgaben“ steht die eigene Zeile oben mit dem Button „Als überwiesen markieren“. Das legt `settlement(from=ich, to=Empfänger, amount=x, paid_on=heute)` an. Teilbeträge sind über das Formular möglich.

### 4.4 Validierung

- Betragseingabe akzeptiert `6,40`, `6.40`, `6`, `6,4` und wird in Cent umgewandelt. Ungültige Eingaben werden mit einer Fehlermeldung am Feld abgewiesen.
- Mindestens ein Teilnehmer.
- `spent_on` nicht mehr als ein Jahr in der Zukunft.

## 5. Weitere Module

### 5.1 Einkaufsliste
- Hinzufügen: Name (Pflicht), Menge und Notiz optional. Doppelte offene Einträge (gleicher Name, case-insensitive) → Hinweis „steht schon drauf“, kein Duplikat.
- Abhaken heißt „im Wagen“ (`checked_at`). Erneutes Tippen hebt das wieder auf.
- „N Artikel als Ausgabe eintragen“ führt zu `/expenses/new?items=1,2` mit vorbefüllter Beschreibung („Eier, Toastbrot“). Nach dem Speichern gilt `expense_id` für die Artikel, sie werden archiviert.
- „Erledigte entfernen“ archiviert abgehakte Artikel ohne Ausgabe.
- Schnellauswahl (Phase 2): die 8 häufigsten Namen der letzten 90 Tage, die gerade nicht offen sind.

### 5.2 Vorräte (Phase 2)
- Tippen auf den Status wechselt genug → wird knapp → leer → genug.
- Wechsel auf `low` oder `empty`: offenen `shopping_item` mit `source=supply` anlegen, falls keiner existiert.
- Wird ein verknüpfter Einkaufsartikel abgehakt und archiviert, geht der Vorrat auf `ok`.

### 5.3 Abwesenheiten (Phase 2)
- Eintragen über das „+“-Sheet oder das Profil. Eintragen darf man nur für sich selbst, in den Einstellungen auch für andere.
- Wirkung: Putzplan (§3.2), keine Putz-Erinnerungen, Anzeige auf Start und Pinnwand („Bato ist bis Do, 22.10. weg“).

### 5.4 Pinnwand
- Reihenfolge: offene Abstimmungen → nächste 3 Termine → angepinnte Notizen → neueste Notizen → Link zu den WG-Infos.
- Notizen mit `expires_on` verschwinden danach automatisch (Job).
- WG-Infos: Liste von Info-Seiten, von allen bearbeitbar (protokolliert).

### 5.5 Termine (Phase 3)
- Einfache Wiederholungen: wöchentlich, zweiwöchentlich, monatlich (gleicher Tag im Monat; bei 29–31 auf den Monatsletzten begrenzen).
- iCal-Feed `/cal/<calendar_token>.ics` mit Terminen, Abwesenheiten (ganztägig) und den Putzplan-Zuteilungen der nächsten 8 Wochen (ganztägig Mo–So, ein Eintrag pro Woche: „Putzplan: Jakob Großes Bad, …“).

### 5.6 Abstimmungen (Phase 3)
- Frage plus 2–6 Optionen (Standard: Ja/Nein), optionales Enddatum.
- Ergebnis immer sichtbar, inklusive wer noch nicht abgestimmt hat.

### 5.7 Statistiken (Phase 3)
- Putzplan: Anteil erledigt/ausgelassen/nicht erledigt pro Person (letzte 12 Wochen), neutral dargestellt.
- Ausgaben: Summe pro Monat und Kategorie.

## 6. Zugang und Sicherheit

### 6.1 Ablauf
```
GET /join/<token>
  rate-limit check (per IP, 10 Fehlversuche / 15 min) -> bei Überschreitung 404
  if compare_digest(token, settings.join_token):
      set cookie wg_auth = sign({"v": cookie_version})   # max_age 400 Tage
      log action=join
      303 -> "/" if valid wg_member cookie else "/welcome"
  else: count failure, 404

Middleware (alle Routen außer /join/*, /healthz, /cal/*.ics):
  wg_auth fehlt, ist ungültig oder hat v != cookie_version -> 404 "Not Found" (text/plain)
  wg_member fehlt oder Mitglied inaktiv -> 303 /welcome (nur wenn wg_auth gültig)
```

- Cookies: `HttpOnly`, `Secure` (außer `APP_ENV=dev`), `SameSite=Lax`, `Path=/`, signiert mit `SECRET_KEY` (itsdangerous, Salt je Cookie).
- `wg_member` enthält `{"m": member_id, "v": cookie_version}`.
- Hinter Caddy: Client-IP aus `X-Forwarded-For`, aber nur von der Proxy-IP vertrauen (Uvicorn `--proxy-headers --forwarded-allow-ips`, auf das Docker-Netz beschränkt).

### 6.2 CSRF
- Für POST/PUT/PATCH/DELETE: `Origin` (oder `Referer`) muss `APP_BASE_URL` entsprechen **und** der Token muss passen.
- Token = `HMAC(SECRET_KEY, cookie_version + member_id)`, als `<meta name="csrf-token">` im Layout. htmx sendet ihn per `hx-headers` auf `<body>`, Formulare als `<input type="hidden" name="csrf">`.
- Fehler → 403 mit kurzer Seite „Bitte Seite neu laden“ (nur für authentifizierte Nutzer, die ja wissen, dass es die App gibt).

### 6.3 HTTP-Header (App-Middleware, zusätzlich zu Caddy)
```
Content-Security-Policy: default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:;
                         connect-src 'self'; font-src 'self'; manifest-src 'self'; worker-src 'self';
                         frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Robots-Tag: noindex, nofollow
Cache-Control: no-store            (für HTML-Antworten)
```
- htmx-Konfiguration per `<meta name="htmx-config" content='{"includeIndicatorStyles": false}'>`, damit htmx kein Inline-`<style>` einfügt (CSP).
- Keine Inline-Skripte und keine Inline-Styles in Templates. Dynamische Breiten (z. B. Abstimmungsbalken) per `<progress>` oder vordefinierte Klassen.
- `robots.txt` liefert für Nicht-Eingeloggte 404 wie alles andere. `noindex` reicht.

### 6.4 Admin-Funktionen
Es gibt keine eigene Admin-Rolle: alle Mitglieder dürfen alles. Gefährliche Aktionen (Link erneuern, alle abmelden, Mitglied deaktivieren, Rotation neu festlegen) brauchen einen Bestätigungsdialog und werden protokolliert. Zusätzlich gibt es die CLI auf dem Server.

**CLI** (`python -m app.cli`):
| Befehl | Wirkung |
| --- | --- |
| `init --seed deploy/seed.toml` | Nur wenn die DB leer ist: Mitglieder, Aufgaben, Rotation, Kategorien, Vorräte, Info-Seiten, Settings anlegen; gibt den Beitrittslink aus |
| `show-link` | Beitrittslink ausgeben (+ QR im Terminal, `segno`) |
| `rotate-link` | neuer Token |
| `logout-all` | `cookie_version += 1` |
| `backup` | sofortiges Backup |
| `add-member <name>` | Notfall-Werkzeug |

## 7. Routen und Screens

Pfade auf Englisch, Seitentitel/Texte über i18n. Alle HTML-Routen liefern ganze Seiten. Bei `HX-Request` liefern Toggle-Aktionen nur das betroffene Fragment.

| Methode | Pfad | Zweck | Phase |
| --- | --- | --- | --- |
| GET | `/join/{token}` | Beitritt | 1 |
| GET/POST | `/welcome` | „Wer bist du?“ + Sprache | 1 |
| GET | `/` | Start | 1 |
| GET | `/new` | „+“-Sheet (mit htmx als `<dialog>`, ohne JS als Seite) | 1 |
| GET | `/chores?week=YYYY-MM-DD` | Putzplan | 1 |
| POST | `/chores/{week}/{chore_id}/done` | erledigt | 1 |
| POST | `/chores/{week}/{chore_id}/skip` | auslassen (Feld `reason`) | 1 |
| POST | `/chores/{week}/{chore_id}/undo` | rückgängig | 1 |
| GET/POST | `/chores/swap` | tauschen | 2 |
| GET | `/expenses` | Saldo, wer zahlt wem, letzte Ausgaben | 1 |
| GET | `/expenses/all` | alle Ausgaben, filterbar nach Monat | 1 |
| GET/POST | `/expenses/new` | neue Ausgabe (`?items=` aus Einkauf) | 1 |
| GET/POST | `/expenses/{id}/edit` | bearbeiten | 1 |
| POST | `/expenses/{id}/delete` | in den Papierkorb | 1 |
| POST | `/settlements` | Ausgleich anlegen | 1 |
| POST | `/settlements/{id}/delete` | Ausgleich zurücknehmen | 1 |
| GET | `/expenses/export.csv` | CSV-Export | 3 |
| GET/POST | `/expenses/recurring…` | wiederkehrende Ausgaben | 2 |
| GET/POST | `/shopping` | Liste + Hinzufügen (`?focus=1` fokussiert das Eingabefeld) | 1 |
| POST | `/shopping/{id}/toggle` | im Wagen an/aus | 1 |
| POST | `/shopping/clear-checked` | erledigte entfernen | 1 |
| POST | `/supplies/{id}/cycle` | Vorratsstatus weiterschalten | 2 |
| GET | `/board` | Pinnwand | 1 (Notizen, Infos) / 3 (Rest) |
| GET/POST | `/board/notes/new`, `/board/notes/{id}/…` | Notizen | 1 |
| GET/POST | `/board/info/{id}/edit` | WG-Infos | 1 |
| GET/POST | `/board/events/…` | Termine | 3 |
| GET/POST | `/board/polls/…`, `/board/polls/{id}/vote` | Abstimmungen | 3 |
| GET/POST | `/absences/new`, `/absences/{id}/delete` | Abwesenheiten | 2 |
| GET | `/profile` | Profil | 1 |
| POST | `/profile/language`, `/profile/switch`, `/profile/notifications` | Einstellungen der Person | 1/2 |
| GET | `/settings` | WG-Einstellungen | 1 |
| POST | `/settings/members…`, `/settings/chores…`, `/settings/rota…`, `/settings/categories…` | Verwaltung | 1 |
| POST | `/settings/rotate-link`, `/settings/logout-all` | Zugang | 1 |
| GET | `/settings/activity`, `/settings/trash` | Protokoll, Papierkorb | 1 |
| POST | `/settings/trash/{entity}/{id}/restore` | wiederherstellen | 1 |
| GET | `/cal/{token}.ics` | Kalender-Abo | 3 |
| GET | `/healthz` | `ok` (prüft DB mit `SELECT 1`) | 1 |
| GET | `/manifest.webmanifest`, `/sw.js` | PWA (Service Worker am Root, Scope `/`) | 1 |

Inhalte je Screen: siehe `docs/design.md` §5.

## 8. Erinnerungen und Hintergrundjobs

### 8.1 Benachrichtigungsarten
| Key in `notify_prefs` | Auslöser | Zeitpunkt | Standard |
| --- | --- | --- | --- |
| `chore_next_week` | Aufgabe der kommenden Woche | So 18:00 | an |
| `chore_open` | eigene Aufgabe der laufenden Woche noch `open` | Fr 18:00 | an |
| `settlement_received` | jemand hat mir einen Ausgleich eingetragen | sofort | an |
| `expense_new` | neue Ausgabe, an der ich beteiligt bin (nicht von mir) | sofort | aus |
| `supply_shopping` | Vorrat leer oder neuer Einkaufsartikel (nicht von mir) | sofort | aus |
| `event_tomorrow` | Termin morgen | Vortag 19:00 | aus |

Keine Putz-Erinnerungen während einer Abwesenheit, die die betreffende Woche komplett abdeckt.

### 8.2 Versand
```
POST {NTFY_BASE_URL}      (JSON-Publish, keine Header-Kodierungsprobleme mit Umlauten)
{"topic": member.ntfy_topic, "title": "...", "message": "...",
 "tags": ["broom"], "click": "{APP_BASE_URL}/chores", "priority": 3}
```
- Texte aus i18n in der Sprache des Empfängers, kurz und **ohne Beträge** (z. B. „Clara hat dir eine Überweisung eingetragen.“).
- Versand nach dem DB-Commit über FastAPI `BackgroundTasks` bzw. im Job. Timeout 5 s, 1 Wiederholung, Fehler nur loggen.
- Profil: Topic anzeigen, Button „In ntfy öffnen“ (`https://ntfy.sh/<topic>` bzw. `ntfy://ntfy.sh/<topic>`, beide Varianten testen) und QR-Code.
- Admin-Topic (`settings.admin_ntfy_topic`): Backup fehlgeschlagen, ungewöhnlich viele Join-Fehlversuche, App-Start nach Absturz.

### 8.3 Jobs (APScheduler, Zeitzone Europe/Berlin, `coalesce=True`, `misfire_grace_time=3600`)
| Job | Zeitplan | Phase |
| --- | --- | --- |
| Backup | täglich 03:30 | 1 |
| Papierkorb leeren (> 30 Tage), abgelaufene Notizen | täglich 04:00 | 1 |
| Wiederkehrende Ausgaben anlegen | täglich 06:00 | 2 |
| Erinnerung „Aufgabe nächste Woche“ | So 18:00 | 2 |
| Erinnerung „Aufgabe noch offen“ | Fr 18:00 | 2 |
| Erinnerung „Termin morgen“ | täglich 19:00 | 3 |

**Backup:** SQLite-Online-Backup-API (`sqlite3.Connection.backup`) in eine temporäre Datei, dann gzip nach `BACKUP_DIR/wg-YYYY-MM-DD.db.gz`. Ältere als `BACKUP_KEEP_DAYS` (14) löschen. Erfolg/Fehler protokollieren.

## 9. Querschnitt

### 9.1 Lokalisierung
- `app/i18n/de.json`, `en.json`: flache Schlüssel mit Punkten (`chores.status.done`). Platzhalter im Format `{name}`.
- Jinja-Global `t(key, **params)`. Sprache = `member.language` (vor der Namenswahl: Cookie `wg_lang` oder `settings.default_language`).
- Formatierung mit Babel: `format_currency(Decimal(c)/100, "EUR", locale="de_DE")` → `28,80 €`, in `en_GB` → `€28.80`. Datumsangaben wie „Mo, 19.10.“ bzw. „Mon 19 Oct“. Kalenderwoche „KW 43“ / „Week 43“.
- Negative Beträge mit echtem Minuszeichen `−` (U+2212).
- Aufgaben- und Kategorienamen kommen aus der DB (`name_de`/`name_en`).

### 9.2 PWA
- `manifest.webmanifest`: Name aus `settings.wg_name`, `display: standalone`, `start_url: "/"`, `theme_color: #1F6F5C`, `background_color: #F4F5F1`, Icons 192 und 512 (maskable). Einbinden mit `<link rel="manifest" href="/manifest.webmanifest" crossorigin="use-credentials">` (das Cookie wird gebraucht).
- `sw.js`: statische Assets per Cache-First (versioniert), HTML per Network-First, Offline-Fallback-Seite „Keine Verbindung“. Keine POSTs cachen.

### 9.3 CSV-Export (Phase 3)
Semikolon-getrennt, UTF-8 mit BOM (Excel DE), Dezimalkomma. Spalten: Datum; Beschreibung; Kategorie; Betrag; Bezahlt von; Teilnehmer; Anteil je Mitglied (eine Spalte pro Mitglied).

### 9.4 Logging
Strukturiertes Logging nach stdout (`LOG_LEVEL`). Keine Tokens oder Cookies loggen. Zugriffslogs ohne Query-Strings für `/join`.

### 9.5 Konfiguration (`.env`)
| Variable | Beispiel | Pflicht |
| --- | --- | --- |
| `APP_ENV` | `prod` \| `dev` | ja |
| `APP_BASE_URL` | `https://203.0.113.10` | ja |
| `PUBLIC_IP` | `203.0.113.10` | ja (Caddy) |
| `ACME_EMAIL` | `name@example.org` | empfohlen |
| `SECRET_KEY` | 64 Hex-Zeichen | ja |
| `DATABASE_PATH` | `/data/wg.db` | ja |
| `BACKUP_DIR` | `/data/backups` | ja |
| `BACKUP_KEEP_DAYS` | `14` | nein |
| `NTFY_BASE_URL` | `https://ntfy.sh` | nein |
| `TZ` | `Europe/Berlin` | ja |
| `LOG_LEVEL` | `info` | nein |

## 10. Testvektoren (Pflicht)

### 10.1 Rotation (Seed-Konfiguration)
| Woche (Montag) | KW | Boden | Küche & Müll | Großes Bad | Kleines Bad |
| --- | --- | --- | --- | --- | --- |
| 2026-10-19 | 43 | Clara | Bato | Jakob | Daniel |
| 2026-10-26 | 44 | Daniel | Clara | Bato | Jakob |
| 2026-11-02 | 45 | Jakob | Daniel | Clara | Bato |
| 2026-11-09 | 46 | Bato | Jakob | Daniel | Clara |
| 2026-11-16 | 47 | Clara | Bato | Jakob | Daniel |

Weitere Fälle:
- Woche vor dem 2026-10-19 → leere Zuteilung.
- `skip` in KW 43 für Jakob → KW 44 unverändert (Jakob Kleines Bad).
- Tausch Jakob ↔ Clara in KW 44 → Jakob Küche & Müll, Clara Kleines Bad; KW 45 wieder laut Tabelle.
- Bato komplett abwesend in KW 44 (2026-10-26 bis 2026-11-01) → Großes Bad KW 44 = `skipped`, Grund „abwesend“; KW 45 laut Tabelle.
- Neues Mitglied „Eva“ ab KW 45 (5 Personen, 4 Aufgaben): In KW 45 behalten alle vier ihre Aufgabe laut Tabelle, Eva ist „frei“. KW 46: Jakob Küche & Müll, Daniel Großes Bad, Clara Kleines Bad, Bato frei, Eva Boden. (Slots `[Jakob, Daniel, Clara, Bato, Eva]` → k=1: Eva Slot 4 → Index 0 = Boden.)
- Daniel zieht ab KW 45 aus (3 Personen, 4 Aufgaben): KW 45 Boden Jakob, Großes Bad Clara, Kleines Bad Bato, Küche & Müll unbesetzt.
- Datumsgrenzen: Sonntag 23:59 gehört zur alten, Montag 00:00 zur neuen Woche (Europe/Berlin, auch über die Zeitumstellung am 2026-10-25).

### 10.2 Abrechnung (Beispiel aus der Vorschau)
Mitglieder (position): Jakob 0, Clara 1, Daniel 2, Bato 3.
| # | Beschreibung | Bezahlt von | Betrag | Teilnehmer |
| --- | --- | --- | --- | --- |
| 1 | Großeinkauf | Clara | 48,60 € | alle 4 (je 12,15) |
| 2 | Putzmittel & Müllbeutel | Daniel | 15,80 € | alle 4 (je 3,95) |
| 3 | Klopapier & Spülmittel | Jakob | 12,40 € | alle 4 (je 3,10) |
| 4 | Internet Oktober | Bato | 40,00 € | alle 4 (je 10,00) |
| 5 | Pizza WG-Abend | Clara | 36,00 € | Jakob, Clara, Daniel (je 12,00) |

Erwartet:
- Salden: Clara **+43,40**, Bato **+10,80**, Daniel **−25,40**, Jakob **−28,80** (Summe 0).
- Überweisungen: Jakob → Clara **28,80**, Daniel → Clara **14,60**, Daniel → Bato **10,80**.
- Nach dem Ausgleich Jakob → Clara 28,80: Jakob 0, Clara +14,60; neue Vorschläge: Daniel → Clara 14,60, Daniel → Bato 10,80.
- Rundung: 10,00 € auf 3 Teilnehmer → Anteile 334 / 333 / 333 Cent, Summe 1000. Bei Expense-ID 4 und 3 Teilnehmern ist der Startindex `4 % 3 = 1`, also bekommt der zweite Teilnehmer (nach position) den Extra-Cent.
- Gelöschte Ausgabe zählt nicht mehr, nach dem Wiederherstellen wieder.
- Eigenschaftstest (z. B. 200 zufällige Fälle): Summe der Anteile = Betrag, Summe der Salden = 0, Anzahl der Überweisungen ≤ n − 1, nach Anwendung aller Überweisungen sind alle Salden 0.

### 10.3 Zugang
- `GET /` ohne Cookie → 404, Body `Not Found`, kein `Set-Cookie`.
- `GET /join/<falsch>` → 404. Der 11. Fehlversuch derselben IP innerhalb von 15 Minuten → 404, auch mit richtigem Token.
- `GET /join/<richtig>` → 303 nach `/welcome`, Cookie `wg_auth` mit `HttpOnly`, `Secure`, `SameSite=Lax`.
- Nach `rotate-link`: alter Token → 404, bestehendes Cookie bleibt gültig.
- Nach `logout-all`: bestehendes Cookie → 404.
- POST ohne CSRF-Token oder mit fremdem `Origin` → 403.
- Inaktives Mitglied im `wg_member`-Cookie → 303 nach `/welcome`.

### 10.4 i18n und Templates
- Schlüsselmenge `de.json` == `en.json`.
- Alle `t("…")`-Aufrufe in Templates und Python (statisch per Regex gesucht) existieren in beiden Dateien.
- Jede HTML-Seite rendert für beide Sprachen ohne Fehler (Smoke-Test über alle GET-Routen mit Seed-Daten).
