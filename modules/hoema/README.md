# HöMa I – Lernprogramme (`/hoema/`)

Public, static lesson pages for a self-study of *Höhere Mathematik I*
(Uni Heidelberg, WS 2026/27). Each lesson is one self-contained HTML page,
originally built as a Claude artifact in the study project.

```
modules/hoema/
  public/            # served as-is under https://<DOMAIN>/hoema/
    index.html       # overview, rendered from lessons.json
    lessons.json     # all planned units; "file" set once a lesson exists
    le01.html …      # one file per lesson
  tools/add-lesson.py
  compose.yaml       # caddy:2-alpine file server, ./public bind-mounted
  module.json
```

No app code and no build: a minimal Caddy file server serves `public/`.
Because the folder is bind-mounted, **publishing or updating a lesson only
needs `git pull` on the server** (or `scripts/deploy.sh`). Only adding the
module the first time needs `docker compose up -d`.

## Adding or updating a lesson

```bash
python3 modules/hoema/tools/add-lesson.py LE02 /path/to/lesson.html
git add modules/hoema/public && git commit -m "hoema: add LE02" && git push
```

The script copies the page to `public/le02.html`, sets `lang="de"`, adds a
"← Alle Lektionen" link, and marks the unit as available in `lessons.json`
(section count and localStorage prefix are read from the page, so the
overview can show each visitor's own progress). Running it again for the
same unit replaces the page. Unknown unit IDs are appended.

## Privacy rule (do not break)

Lessons are public. **A visitor's answers and progress stay in that
visitor's browser** (`localStorage`, key prefix `homa1-<unit>-`). Nothing is
sent to the server, there is no database, no analytics, no logging of
answers. This is deliberate: repetition planning for the study project uses
only the owner's own answers and reported weak points, never data from other
visitors.

`add-lesson.py` therefore refuses pages whose own scripts use `fetch`,
`XMLHttpRequest`, `sendBeacon`, `WebSocket`, `window.claude` or a form
`action`. Loading libraries via `<script src>` (KaTeX) and fonts is fine.
If a lesson ever needs to hand results back, do it as a local export the
visitor copies themselves, not as an upload.

The lecture notes PDF itself is not published here.
