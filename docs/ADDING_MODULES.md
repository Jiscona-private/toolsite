# Adding a module

A module is any self-contained web app that:

1. Lives in `modules/<module-id>/`.
2. Has a `module.json` manifest the landing page reads.
3. Has its own `compose.yaml` the root `docker-compose.yml` includes.
4. Knows its own `BASE_PATH` and bakes that prefix into every link, form
   action, and route it serves.

## Quick start

```bash
scripts/new-module.sh book-club "Book Club" "Pick and track what we're reading"
```

This copies `modules/_template/` into `modules/book-club/`, replacing the
`__MODULE_ID__` / `__MODULE_NAME__` / `__MODULE_DESCRIPTION__` placeholders.
It prints two steps you still need to do by hand:

1. Add a line to `docker-compose.yml`:
   ```yaml
   include:
     - landing/compose.yaml
     - modules/wg-manager/compose.yaml
     - modules/book-club/compose.yaml   # <- new
   ```
2. Decide whether the module needs protecting. If it holds anything
   personal, copy the `/wg*` block in the `Caddyfile` and change the path
   prefix, service name, and (ideally) its own separate Basic Auth
   credentials/env vars.

Then build and start it:

```bash
docker compose up -d --build
```

The landing page picks it up automatically on next page load — no landing
page code changes needed.

## The manifest (`module.json`)

```json
{
  "id": "book-club",
  "name": "Book Club",
  "description": "Pick and track what we're reading",
  "path": "/book-club/",
  "icon": "📚"
}
```

- `path` must match the prefix Caddy routes to this module, with a
  trailing slash — it's used verbatim as the landing page card's link.
- A directory starting with `_` (like `_template`) is ignored by the
  landing page and should never be included in `docker-compose.yml`.

## Why the module must be prefix-aware

Caddy forwards requests to modules with `handle` (not `handle_path`), so the
full path — including the `/book-club` prefix — reaches your container
unchanged. Your app must therefore:

- Mount its routes under `BASE_PATH` (an env var, default `/<module-id>`),
  not at `/`.
- Use that same prefix in every `<a href>`, `<form action>`, and redirect it
  emits.

This is more upfront plumbing than stripping the prefix would be, but it
means your module's own links are always correct regardless of where Caddy
mounts it, and nothing needs path-rewriting in the proxy layer. See
`modules/wg-manager/src/server.js` and `src/views.js` for the pattern:
a `req.basePath` set once in middleware, threaded through every route and
template.

## Persistent data

If your module needs storage, give it its own SQLite file (the convention
every other module here follows) under `data/`, mounted as a volume in its
`compose.yaml`:

```yaml
services:
  book-club:
    build: .
    volumes:
      - ./data:/app/data
    environment:
      - DB_PATH=/app/data/book-club.db
```

Add `modules/book-club/data/*` to version control exclusion (already
covered by the root `.gitignore` pattern `modules/*/data/*`) and it's
automatically picked up by `scripts/backup.sh`.

## Native dependencies

If your module needs a package with native bindings (like
`better-sqlite3`), use a multi-stage `Dockerfile` so the final image doesn't
carry build tools — see `modules/wg-manager/Dockerfile` for the pattern.
Plain JS-only dependencies can use the simpler single-stage Dockerfile in
`modules/_template/Dockerfile`.

## Checklist

- [ ] `modules/<id>/module.json` with a unique `id` and matching `path`
- [ ] `modules/<id>/compose.yaml` joining the external `toolsite_net` network
- [ ] App reads `PORT` and `BASE_PATH` from the environment
- [ ] Every link/redirect the app emits includes `BASE_PATH`
- [ ] Added to `docker-compose.yml`'s `include:` list
- [ ] Added Basic Auth in `Caddyfile` if it holds personal data
- [ ] `docker compose up -d --build` and confirm it loads at its `path`
