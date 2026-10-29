# EA Heidelberg concept draft (`/ea-heidelberg/`)

A content-only skeleton for a possible redesign of
[eaheidelberg.de](https://eaheidelberg.de) (currently a Squarespace site for
the Effective Altruism Heidelberg university group). No visual design has
been applied — plain HTML/CSS, four pages (Home, About, Events, Contact),
content copied from the live site as of October 2026 so the real design pass
has something to work from.

```
modules/ea-heidelberg/
  public/            # served as-is under https://<DOMAIN>/ea-heidelberg/
    index.html
    about.html
    events.html
    contact.html
    style.css        # deliberately bare — layout only, no theme
  compose.yaml        # caddy:2-alpine file server, ./public bind-mounted
  module.json
```

No app code and no build: a minimal Caddy file server serves `public/`, same
pattern as `modules/hoema`.

## Why it's password-protected

The content on these pages is copied from eaheidelberg.de for internal
comparison while a new design is worked out — it isn't original content yet,
so it's gated with HTTP Basic Auth in the root `Caddyfile` (`handle
/ea-heidelberg*`) rather than left public, and kept out of search engines via
the site-wide `noindex` header. The Caddyfile only stores a bcrypt hash of
the password, never the plaintext.

## Status

This is intentionally minimal — a skeleton to react to, not a finished
draft. Next step is a real visual design pass (fonts, colors, layout) once
that direction is decided.
