# Toolsite

A small, self-hosted collection of tools running on a single VPS, built so
that each tool is an independent module you can add, change, or remove
without touching anything else.

```
https://<your-domain>/        → landing page, lists every installed module
https://<your-domain>/wg/     → WG-Manager v1 (chores, shared expenses, shopping list, ...)
https://<your-domain>/hoema/  → HöMa I lesson pages (static, public)
```

A plain IPv4 address can't get a trusted HTTPS certificate on its own — see
`docs/SETUP.md` for pointing a free domain/subdomain at the VPS, which is
what Caddy uses to get automatic Let's Encrypt certificates.

## Stack

- **[Caddy](https://caddyserver.com/)** — reverse proxy, automatic HTTPS, the only container exposed to the internet.
- **Docker Compose**, using the `include:` feature so every module ships its own `compose.yaml`.
- Each module picks its own stack - mostly **Node.js + Express**, **SQLite** for anything that needs storage. `modules/wg` is Python/FastAPI (its own `CLAUDE.md`/`docs/` explain why). No shared database server, no build pipeline for the Node modules - this runs on a netcup *Pico* tier VPS with very little RAM to spare.

## Repository layout

```
docker-compose.yml       # root — includes every active module
Caddyfile                # routing + automatic TLS (Basic Auth available per-module, see Caddyfile)
.env.example             # copy to .env on the server, fill in real values

landing/                 # public landing page (auto-lists modules)

modules/
  wg/                     # WG-Manager v1: chores, shared expenses, shopping list, ...
  hoema/                  # HöMa I lesson pages (static, public)
  _template/              # starting point for new modules (never deployed)

scripts/
  new-module.sh           # scaffold a new module from _template
  deploy.sh                # git pull + rebuild + restart, run on the VPS
  backup.sh                 # tar up every module's data/ directory

docs/
  SETUP.md                 # VPS provisioning, step by step
  ARCHITECTURE.md          # why it's built this way
  ADDING_MODULES.md        # the contract a new module follows
```

## Getting started

1. **Deploying to the VPS:** follow `docs/SETUP.md` top to bottom (domain →
   Docker install → firewall → `.env` → first launch).
2. **Adding a new tool:** `scripts/new-module.sh <id> "<Name>" "<description>"`,
   then follow `docs/ADDING_MODULES.md`.
3. **Why it's structured this way:** `docs/ARCHITECTURE.md`.

## Local development

Set `DOMAIN=localhost` in `.env` — Caddy then issues a locally-trusted
development certificate instead of talking to Let's Encrypt, so
`docker compose up --build` works the same way locally as it will in
production.

## What's included today

**HöMa I – Lernprogramme** (`modules/hoema`, public at `/hoema/`) — static,
interactive lesson pages for a maths self-study. No server-side state: answers
and progress stay in each visitor's browser. See `modules/hoema/README.md`.

**WG-Manager v1** (`modules/wg`, at `/wg/`) — for a shared flat:
- A weekly rotating chore plan, with swaps, substitutions, and a "skipped"
  state that always needs a reason.
- Shared expenses with automatic, rounding-correct splitting and a "who
  pays whom to settle up" suggestion.
- A shared shopping list, a pinboard, and a protocol/trash with 30-day
  undo for anything deleted.
- Installable as a PWA.

No accounts or passwords: access is a secret join-link shared only within
the household, after which every request without a valid session 404s
(never a login prompt) - see `modules/wg/CLAUDE.md` for the full design.
The landing page itself is public.
