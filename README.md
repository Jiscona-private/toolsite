# Toolsite

A small, self-hosted collection of tools running on a single VPS, built so
that each tool is an independent module you can add, change, or remove
without touching anything else.

```
https://<your-domain>/        → landing page, lists every installed module
https://<your-domain>/wg/     → WG Manager (shared expenses, chores, shopping list)
```

A plain IPv4 address can't get a trusted HTTPS certificate on its own — see
`docs/SETUP.md` for pointing a free domain/subdomain at the VPS, which is
what Caddy uses to get automatic Let's Encrypt certificates.

## Stack

- **[Caddy](https://caddyserver.com/)** — reverse proxy, automatic HTTPS, the only container exposed to the internet.
- **Docker Compose**, using the `include:` feature so every module ships its own `compose.yaml`.
- **Node.js + Express** per module, **SQLite** (`better-sqlite3`) for anything that needs storage. No shared database server, no build pipeline — this runs on a netcup *Pico* tier VPS with very little RAM to spare.

## Repository layout

```
docker-compose.yml       # root — includes every active module
Caddyfile                # routing + TLS + Basic Auth for sensitive modules
.env.example             # copy to .env on the server, fill in real values

landing/                 # public landing page (auto-lists modules)

modules/
  wg-manager/             # shared expenses, chore rotation, shopping list
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

**WG Manager** (`modules/wg-manager`) — for a shared flat:
- Shared expenses, split evenly across residents, with running balances and
  a "who pays whom to settle up" suggestion.
- Chores that rotate round-robin across residents as they're marked done.
- A shared shopping list.

It sits behind HTTP Basic Auth (shared credentials for the household,
configured in `.env`/`Caddyfile`) since it holds personal data; the landing
page itself is public.
