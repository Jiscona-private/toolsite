# Design-System – WG-App

Grundlage ist die klickbare Vorschau aus der Planungsphase. Die Screens liegen als eigenständige HTML-Dateien in `docs/design/screens/` (`index.html` im Browser öffnen). Sie sind **verbindlich für Aufbau, Inhalte, Abstände und Farben**. Umsetzung in der App:

- Alle Styles als Klassen in `app/static/css/app.css` mit CSS-Variablen (Tokens unten). Keine Inline-Styles: die CSP verbietet sie, und die Mockups nutzen sie nur der Einfachheit halber.
- Kein CSS-Framework, kein Build-Schritt.
- Mobile-first. Ab 600 px Breite wird der Inhalt mittig mit `max-width: 480px` dargestellt, die Bottom-Bar ebenfalls.

Charakter: ruhig, freundlich, aufgeräumt. Ein grüner Akzent („Seifengrün“), viel Weißraum, große Touch-Ziele. Keine Verläufe, keine Emojis, keine Schatten außer dem Ring am „+“-Button.

## 1. Tokens

### 1.1 Farben (hell, Standard)
```css
:root {
  --bg: #F4F5F1;              /* Seitenhintergrund */
  --surface: #FFFFFF;         /* Karten, Bottom-Bar, Sheet */
  --border: #E2E5DF;          /* Kartenrand, Bar-Oberkante */
  --divider: #EEF0EC;         /* Trennlinien in Listen, neutrale Flächen */
  --control-border: #CDD2CB;  /* Rand von Sekundär-Buttons und Inputs */
  --ink: #1B1F1D;             /* Haupttext */
  --ink-2: #4A524E;           /* Feldbeschriftungen */
  --muted: #5B635F;           /* Sekundärtext (Kontrast auf Weiß ≈ 6:1) */
  --checkbox-border: #8E9690;

  --accent: #1F6F5C;          /* Primär-Buttons, aktive Navigation, Links */
  --accent-strong: #174F42;   /* Hover, Text auf --accent-soft */
  --accent-soft: #DCEBE5;     /* eigener Avatar, ausgewählte Chips */
  --on-accent-muted: #D6EDE5; /* Sekundärtext auf --accent-Fläche */
  --accent-outline: #9CCDBD;  /* Outline-Button auf --accent-Fläche */

  --status-done-bg: #E1F0EA;    --status-done-fg: #1A6150;
  --status-open-bg: #EEF0EC;    --status-open-fg: #3F4743;
  --status-skipped-bg: #FBEBD6; --status-skipped-fg: #8A4B07;
  --status-empty-bg: #F7DCD2;   --status-empty-fg: #93300F;

  --money-plus: #1A6150;      /* bekommt Geld, mit "+" */
  --money-minus: #A9480C;     /* schuldet Geld, mit "−" */

  --segmented-bg: #E7E9E3;
  --overlay: rgba(27, 31, 29, 0.5);
}
```

### 1.2 Avatar-Palette (`members.color`)
| Index | Hintergrund | Schrift | Seed |
| --- | --- | --- | --- |
| 0 | `#DCEBE5` | `#1F6F5C` | Jakob |
| 1 | `#E4E6F7` | `#3B4A9E` | Clara |
| 2 | `#FBE7D3` | `#8A4B07` | Daniel |
| 3 | `#EDE3F3` | `#6B3F8A` | Bato |
| 4 | `#E3EEF6` | `#22577A` | |
| 5 | `#F6E3E7` | `#8E3049` | |
| 6 | `#EEF0D9` | `#55601A` | |
| 7 | `#EEF0EC` | `#3F4743` | |

Avatare zeigen den Anfangsbuchstaben (fett) und sind für Screenreader `aria-hidden`, weil der Name daneben steht.

### 1.3 Dunkelmodus (Vorschlag, Kontrast beim Umsetzen prüfen)
Aktiv über `@media (prefers-color-scheme: dark)`.
```css
--bg: #111513; --surface: #1A1F1C; --border: #2B322E; --divider: #252B28;
--control-border: #3A423E; --ink: #ECEFEC; --ink-2: #C3CAC5; --muted: #A2AAA5;
--accent: #267A64;          /* Fläche für Primär-Buttons, weiße Schrift ≥ 4,5:1 */
--accent-text: #6CC4A6;     /* Links und aktive Navigation auf dunklem Grund */
--accent-soft: #1E3B32; --accent-strong: #8FD9BE;
--status-done-bg: #1E3B32;    --status-done-fg: #8FD9BE;
--status-open-bg: #2B312E;    --status-open-fg: #C9D0CB;
--status-skipped-bg: #3D2E17; --status-skipped-fg: #F2C27E;
--status-empty-bg: #3F241B;   --status-empty-fg: #F4A88C;
--money-plus: #6FD0AE; --money-minus: #F29B62;
```
Hinweis: Im Hellmodus sind Linkfarbe und Akzentfläche identisch (`--accent`). Im Dunkelmodus braucht es dafür zwei Tokens (`--accent` für Flächen, `--accent-text` für Text). Deshalb in `app.css` von Anfang an `--accent-text` verwenden (hell = `#1F6F5C`).

### 1.4 Typografie
| Rolle | Schrift | Größe / Gewicht | Einsatz |
| --- | --- | --- | --- |
| Display | Bricolage Grotesque | 28 px / 700, `letter-spacing: -0.01em` | Seitentitel (H1) |
| Display groß | Bricolage Grotesque | 24–34 px / 700, tabular-nums | Beträge, „Deine Aufgabe“ (26 px) |
| Sheet-Titel | Bricolage Grotesque | 22 px / 700 | |
| Abschnitt | Figtree | 16 px / 700 | Kartenüberschriften (H2) |
| Zeilentitel | Figtree | 15–15,5 px / 600–700 | Listenzeilen |
| Fließtext | Figtree | 14–16 px / 400 | |
| Sekundär | Figtree | 13 px / 400–600, `--muted` | Untertitel, Metadaten |
| Chip | Figtree | 12,5 px / 600 | Status |
| Navigation | Figtree | 11,5 px / 600 (aktiv 700) | Bottom-Bar |
| Code | `ui-monospace` | 13,5 px | ntfy-Topic |

Schriften selbst hosten (OFL-Lizenz), z. B. über Fontsource (npm-Pakete für Figtree und Bricolage Grotesque) oder google-webfonts-helper. Benötigt: Figtree 400/500/600/700 und Bricolage Grotesque 600/700 (optische Größe 12–96, oder statischer Schnitt). Als `woff2` nach `app/static/fonts/`, `font-display: swap`. Fallback: `system-ui, sans-serif`.

### 1.5 Abstände und Formen
- Seitenrand 20 px, vertikaler Abstand zwischen Karten 14 px.
- Karten: weiß, 1 px `--border`, Radius 20 px, Innenabstand 14–16 px.
- Listenzeilen in Karten: Trennlinie 1 px `--divider`, Zeilenhöhe ≥ 46 px.
- Buttons: Höhe 44 px (Primär im Formular 52 px), Radius 12 px (groß 14 px).
- Chips: Radius 999 px, Innenabstand 4 × 10 px.
- Inputs: Höhe 48 px, Radius 12 px, Rand `--control-border`. Betragsfeld 68 px hoch, 2 px Rand in `--accent`, Schrift 34 px Display.
- Fokus: `outline: 2px solid var(--accent); outline-offset: 2px` (nur `:focus-visible`).
- Unten: `padding-bottom: calc(96px + env(safe-area-inset-bottom))` für die Bar.

## 2. Komponenten

| Komponente | Beschreibung |
| --- | --- |
| **Hero-Karte „Deine Aufgabe“** | Fläche `--accent`, Radius 20. Oben „Deine Aufgabe diese Woche“ (13/600, `--on-accent-muted`), Aufgabenname (26/700 Display, weiß), „Fällig bis Sonntag, 25.10.“. Zwei Buttons nebeneinander: „✓ Erledigt“ (weiß, Schrift `--accent`) und „Auslassen …“ (Outline `--accent-outline`, weiße Schrift). Zustände: erledigt → „Erledigt – danke!“ mit „Rückgängig“-Link; frei → „Diese Woche frei“; ausgelassen → Grund anzeigen. |
| **Personenzeile** | Avatar 34 px, Titel (15/600), Untertitel (13 muted), rechts Status-Chip. Im Putzplan ist der Titel die Aufgabe und der Untertitel die Person. |
| **Status-Chip** | offen (`open`), erledigt (`done`), ausgelassen (`skipped`), nicht erledigt (`open`-Farben, kursiv), leer (`empty`, Vorräte). Immer mit Text. |
| **Kachel** | Halbe Breite (2er-Grid, Abstand 12). Label (13/600 muted), Wert (24/700 Display), Zusatz (13 muted), Pfeil `›` oben rechts. Ganze Kachel ist ein Link. |
| **Link-Karte** | Ganze Karte ist ein `<a>`. Kopfzeile Titel + „Öffnen ›“ / „Alle Wochen ›“. |
| **Checkbox-Zeile** | 44 px Trefferfläche, sichtbares Kästchen 22 px, Radius 7, Rand 2 px `--checkbox-border`. Abgehakt: Fläche `--accent` mit weißem Haken, Text durchgestrichen und muted. `role="checkbox"` + `aria-checked` am Button. |
| **Schalter** | Spur 44 × 26, Knopf 20. An: `--accent`, aus: `--control-border`. `role="switch"` + `aria-checked`, Trefferfläche 52 × 44. Label über `aria-labelledby`. |
| **Segment-Umschalter** | Hintergrund `--segmented-bg` / `--divider`, Radius 12, aktive Option weiß, 700. `aria-pressed`. |
| **Auswahl-Chips (Formular)** | Höhe 40–44, Radius 999 oder 12. Ausgewählt: Fläche `--accent`, weiße Schrift oder `--accent-soft` mit Rand `--accent`. `aria-pressed`. |
| **Personen-Auswahl (Aufteilung)** | 4er-Grid, Avatar 40 px mit 2 px Ring `--accent` wenn ausgewählt, Name darunter. Darunter: „Gleichmäßig auf 4 Personen · je 1,60 €“. |
| **Datums-Badge** | 44 × 44, Radius 12, Wochentag (10,5/700) über Tageszahl (17/700). Nächster wichtiger Termin in `--accent-soft`. |
| **Bottom-Sheet** | Weiß, oben Radius 24, Griff 40 × 5. Dahinter Overlay `--overlay`, Tippen schließt. Titel 22/700 Display. Optionen als Zeilen 64 px: Icon-Kachel 44 px (Radius 14, Avatar-Farben), Titel 16/700, Hinweis 13 muted, Pfeil. Unten „Abbrechen“ (Outline, 48 px). Umsetzung als `<dialog>` mit htmx, ohne JS als eigene Seite `/new`. |
| **Leerzustände** | Kurzer Satz plus Aktion, z. B. „Noch keine Ausgaben. Trag die erste über das + ein.“ |
| **Fehlermeldungen** | Unter dem Feld, 13 px, `--money-minus`, plus `aria-describedby`. |
| **Bestätigungsdialog** | Für gefährliche Aktionen: `<dialog>` mit klarer Konsequenz („Der alte Link funktioniert danach nicht mehr.“). |
| **Toast** | Nach Aktionen kurz unten über der Bar: „Gespeichert“, mit „Rückgängig“, wo sinnvoll. `role="status"`. |

Icons: einfache Stroke-SVGs (24er-Raster, Linienstärke 1,9, runde Enden). Die verwendeten Pfade stehen in den Screen-Dateien. Als SVG-Sprite in `app/static/icons/sprite.svg` ablegen und mit `<svg><use href="…#icon">` nutzen.

## 3. Navigation

```
Bottom-Bar (76 px, weiß, Rand oben):  Start · Putzplan · ( + ) · Ausgaben · Einkauf
```
- 5-Spalten-Grid. Die aktive Seite ist `--accent` und 700, `aria-current="page"`.
- **(+)**: Kreis 56 px in `--accent`, 26 px über die Bar angehoben, 5 px weißer Ring (`box-shadow: 0 0 0 5px var(--surface)`), `aria-label="Neu eintragen"`. Öffnet das Sheet mit:
  1. **Ausgabe** → `/expenses/new`
  2. **Einkaufsliste** → `/shopping?focus=1`
  3. **Notiz an die Pinnwand** → `/board/notes/new`
  4. **Termin oder Abstimmung** → `/board/new` (Phase 3; vorher ausblenden)
  5. **Abwesenheit** → `/absences/new` (Phase 2; vorher ausblenden)
- **Profil:** Avatar-Button (44 px, eigene Farbe) oben rechts auf allen vier Hauptscreens, `aria-label="Mein Profil"`.
- **Pinnwand:** über die Karte „Pinnwand“ auf der Startseite. Die Seite hat oben „‹ Start“, in der Bar ist Start aktiv.
- **Unterseiten** (Pinnwand, Profil, Einstellungen, Alle Ausgaben): oben links „‹ Zurück-Ziel“ (44 px hoch).
- **Formulare** (Neue Ausgabe usw.): oben links „✕ Abbrechen“, keine Bottom-Bar, Speichern-Button unten volle Breite.
- Die Startseite ist der Hub: Jede Karte führt in ihren Bereich.

## 4. Texte und Ton

- Duzen, kurz, freundlich, kein Behördendeutsch. Beispiel: „Wer mit Grund auslässt, bekommt nichts nachgetragen.“
- Zahlen und Datum lokalisiert (§9.1 der Spec).
- Der eigene Name erscheint als „Jakob (du)“ bzw. „Jakob (you)“. In Sätzen heißt es „Du an Clara“.
- Keine Schuldzuweisung im Putzplan („nicht erledigt“ statt „versäumt“).

## 5. Screens (Referenz: `docs/design/screens/`)

Die Beispieldaten in den Screens entsprechen den Testvektoren in `docs/spec.md` §10 (KW 43, Abrechnungsbeispiel).

### 5.1 Beitreten (`Beitreten.html`) – `/welcome`
App-Icon (72 px, Radius 24, `--accent`), „Willkommen in der WG“, „Wer bist du? Die App merkt sich deine Auswahl auf diesem Gerät.“ Darunter vier große Namens-Buttons (60 px, Avatar + Name) und ein Sprachumschalter Deutsch/English. Ganz unten der Hinweis: „Kein Passwort nötig: Wer diesen Link hat, gehört zur WG. Teile ihn nur in eurer WG-Gruppe.“

### 5.2 Start (`Main.html`) – `/`
1. Kopf: „Hallo Jakob“ (H1) und „KW 43 · 19.–25. Oktober“, rechts Profil-Avatar.
2. Hero-Karte „Deine Aufgabe diese Woche“.
3. Link-Karte „Putzplan diese Woche · Alle Wochen ›“ mit vier Personenzeilen (Person, Aufgabe, Status). Die eigene Zeile zuerst.
4. Zwei Kacheln: „Dein Saldo −28,80 € · an Clara überweisen“ → Ausgaben; „Einkaufsliste · 4 offen · Müllbeutel wird knapp“ → Einkauf.
5. Link-Karte „Pinnwand · Öffnen ›“ mit den zwei wichtigsten Einträgen (offene Abstimmung, nächster Termin, sonst neueste Notiz; Abwesenheiten anderer).

### 5.3 „+“-Sheet (`Neu.html`) – `/new`
Siehe Komponente Bottom-Sheet und Navigation.

### 5.4 Putzplan (`Putzplan.html`) – `/chores`
1. Kopf „Putzplan“, „Jeden Montag rückt jeder weiter“, Avatar.
2. Wochenwechsler: ‹ „KW 43 · 19.–25. Okt“ / „diese Woche“ ›.
3. Karte mit vier Zeilen (Aufgabe als Titel, „Person · Detail“ als Untertitel, Status-Chip). Die eigene Aufgabe zuerst, mit drei Buttons: Erledigt (primär), Auslassen, Tauschen. „Auslassen“ öffnet einen Dialog mit Pflichtfeld „Grund“.
4. Karte „Nächste Wochen“: Tabelle KW 44–46 × vier Aufgaben (Kurzformen „Küche“, „Gr. Bad“, „Kl. Bad“), eigener Name fett in `--accent`.
5. Hinweistext: „Wer mit Grund auslässt, bekommt nichts nachgetragen: Die Rotation läuft normal weiter.“
Zurückblättern zeigt vergangene Wochen mit Status, inklusive „nicht erledigt“.

### 5.5 Ausgaben (`Ausgaben.html`) – `/expenses`
1. Kopf „Ausgaben“ und Avatar.
2. Karte „Dein Saldo“: großer Betrag (32 px, Farbe nach Vorzeichen), Satz „Du hast 12,40 € bezahlt, dein Anteil liegt bei 41,20 €.“, darunter die drei anderen Salden im 3er-Grid.
3. Karte „Wer zahlt wem“: eigene Zeile zuerst (Avatar → Avatar, „Du an Clara“, Betrag) mit Button „Als überwiesen markieren“. Danach die übrigen Zeilen. Wenn alles ausgeglichen ist: „Alles ausgeglichen.“
4. Karte „Letzte Ausgaben · Alle (n)“: drei Einträge (Beschreibung, „Person · Datum · alle 4 / ohne Bato“, Betrag). Antippen öffnet die Bearbeitung.

### 5.6 Neue Ausgabe (`NeueAusgabe.html`) – `/expenses/new`
„✕ Abbrechen“, H1 „Neue Ausgabe“, Betragsfeld (groß, `inputmode="decimal"`, Autofokus), „Wofür?“, „Bezahlt von“ (4 Buttons, Standard: ich), „Kategorie“ (Chips), „Aufgeteilt auf“ (Avatar-Grid, alle aktiv vorausgewählt, Live-Anteil „je 1,60 €“), „Datum“ (Standard heute) und Schalter „Monatlich“ (Phase 2), „Speichern“ (52 px, volle Breite).

### 5.7 Einkauf & Vorräte (`Einkauf.html`) – `/shopping`
1. Kopf „Einkauf · Einkaufsliste und Vorräte“ und Avatar.
2. Eingabezeile „Artikel hinzufügen …“ und +-Button (48 px).
3. Karte „Einkaufsliste · 4 offen“: Checkbox-Zeilen mit Menge, Hinzufüger oder Chip „aus Vorräten“. Abschnitt „Im Wagen“ mit abgehakten Artikeln und dem Outline-Button „2 Artikel als Ausgabe eintragen“.
4. Karte „Vorräte · Tippen zum Ändern“: Zeilen mit Status-Button (genug / wird knapp / leer).

### 5.8 Pinnwand (`WG.html`) – `/board`
„‹ Start“, H1 „Pinnwand“. Karte Abstimmung (Frage, Fortschrittsbalken als `<progress>`, „2 × Ja · 0 × Nein · noch offen: du, Bato“, Buttons Ja/Nein), Karte „Termine · Im Kalender abonnieren“ (Datums-Badges), Karte „Pinnwand · + Notiz“ (angepinnt mit Pin-Icon, Autor · Tag) und Link-Zeile „WG-Infos“.

### 5.9 Profil (`Profil.html`) – `/profile`
„‹ Start“, H1 „Mein Profil“. Karte: Avatar, Name, „auf diesem Gerät“, Button „Wechseln“, Sprache (Segment). Karte „Erinnerungen über ntfy“: Topic in Monospace und „In ntfy öffnen“, darunter sechs Schalter mit Zeitpunkt. Link-Liste: „Abwesenheit eintragen“, „WG-Einstellungen“.

### 5.10 Nicht als Mockup vorhanden – nach denselben Mustern bauen
- **WG-Einstellungen** `/settings`: Abschnitte Mitglieder, Aufgaben, Rotation (Vorschau 4 Wochen), Kategorien, Zugang (Link + QR, „Link erneuern“, „Alle abmelden“), Daten (Protokoll, Papierkorb, CSV-Export, Kalender-Abo).
- **Alle Ausgaben**, **Ausgabe bearbeiten**, **Auslassen-Dialog**, **Tauschen**, **Abwesenheit eintragen**, **Notiz**, **WG-Info bearbeiten**, **Termin/Abstimmung anlegen**, **Protokoll**, **Papierkorb**, **Offline-Seite**, **403-Seite**.
