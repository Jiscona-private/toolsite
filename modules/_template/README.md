# Module template

This directory is a starting point for a new Toolsite module. It is never
built or deployed itself — the leading underscore on `_template` excludes it
from both the landing page's module discovery and git history of real
modules.

**Don't edit this directory.** Instead run:

```bash
scripts/new-module.sh my-module-id "My Module Name" "One-line description"
```

which copies this template into `modules/my-module-id/`, fills in the
placeholders, and prints the two remaining manual steps (adding the
`include:` line to the root `docker-compose.yml`, and deciding whether the
module needs Basic Auth in the `Caddyfile`).

See `docs/ADDING_MODULES.md` for the full contract new modules are expected
to follow.
