# Architecture

## Goals

- **Modular**: adding or removing a tool should never require touching
  another tool's code.
- **Light**: this runs on a netcup Pico VPS — minimal RAM/CPU/disk. No
  frameworks or services bigger than the job needs.
- **Boring**: one reverse proxy, one compose convention per module, SQLite
  instead of a database server. Fewer moving parts to break on a tiny box.

## Pieces

```
                         ┌──────────────┐
  https://domain/      → │              │
  https://domain/wg/*  → │    Caddy     │ (reverse proxy + automatic HTTPS)
                         └──────┬───────┘
                   ┌────────────┼─────────────┐
                   ▼                           ▼
            ┌─────────────┐             ┌──────────────┐
            │   landing   │             │  wg-manager  │   ...more modules
            │ (Express)   │             │ (Express +   │
            │ lists       │             │  SQLite)     │
            │ modules/    │             └──────────────┘
            └─────────────┘
```

- **Caddy** terminates TLS, requests/renews Let's Encrypt certificates
  automatically for `DOMAIN`, and routes by path prefix to the right
  container over an internal Docker network (`toolsite_net`). It's the only
  container with ports published to the host.
- **landing** is a public, stateless page. At request time it scans
  `/modules/*/module.json` (mounted read-only) and renders a card per
  module it finds. Adding a module never requires editing landing's code.
- **Each module** is a self-contained app (its own Dockerfile, dependencies,
  and — if needed — its own SQLite file under `data/`). It knows its own
  `BASE_PATH` (e.g. `/wg`) and bakes that prefix into every link and route
  it serves, so Caddy can forward the full path upstream unchanged
  (`handle`, not `handle_path` — see the Caddyfile).

## Why path-based routing instead of subdomains

Free dynamic-DNS providers (DuckDNS etc.) typically hand out one hostname,
not a wildcard. Subdomain-per-module (`wg.example.duckdns.org`) would need
wildcard DNS plus a DNS-01 ACME challenge (a custom Caddy build with a
provider-specific plugin). Path-based routing (`example.duckdns.org/wg/`)
needs none of that — one certificate for one hostname covers every module —
at the cost of each module needing to be aware of its own path prefix. That
trade favors a Pico-tier box: fewer build steps, fewer secrets, one cert to
renew.

## Why Docker Compose `include:` instead of one monolithic compose file

Each module owns its `compose.yaml`. The root `docker-compose.yml` just
lists which modules are active:

```yaml
include:
  - landing/compose.yaml
  - modules/wg-manager/compose.yaml
```

Removing a module is deleting one line (and its directory); adding one is
adding one line (see `docs/ADDING_MODULES.md`). No other file needs to
change. All included services join the same shared `toolsite_net` network
so Caddy can reach them by service name.

## Why SQLite instead of Postgres/MySQL

A Pico VPS has very little RAM. A shared database server is one more
always-on process competing for memory, and most personal-tools workloads
(a handful of users, modest write volume) don't need it. `better-sqlite3`
gives each module an isolated, file-backed database with no separate
process, WAL mode for reasonable concurrent reads, and trivial backups
(`scripts/backup.sh` just tars the file). If a future module genuinely
needs a shared relational database, it can add one in its own
`compose.yaml` — nothing here prevents that, it's just not the default.

## Security posture

- Caddy handles HTTPS end-to-end; nothing is served over plain HTTP except
  the ACME challenge and the automatic HTTP→HTTPS redirect.
- Modules holding personal data (e.g. `wg-manager`) sit behind HTTP Basic
  Auth configured directly in the `Caddyfile`, in front of the proxy — the
  module itself doesn't need to implement auth. This is appropriate for a
  small trusted group (e.g. flatmates) sharing one login; it is not meant
  for a module that needs per-user accounts or public signup.
- The landing page is intentionally public and holds no sensitive data —
  it only lists module names/descriptions from `module.json` files that you
  control.
