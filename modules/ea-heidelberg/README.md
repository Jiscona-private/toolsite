# EA Heidelberg concept draft (`/ea/`)

A persuasion-focused redesign concept for [eaheidelberg.de](https://eaheidelberg.de)
(currently a Squarespace site for the Effective Altruism Heidelberg
university group), in English and German. The goal of this draft isn't a
cosmetic refresh — it's a site built to actually get more students to
attend events, using a mix of real content from the live site, structural
and visual inspiration from GiveWell/Giving What We Can/80,000 Hours/
effectivealtruism.org, and persuasion-psychology research. See
`docs/decisions` in the project history (plan: "EA Heidelberg redesign —
content, persuasion, visuals & bilingual structure") for the full research
and rationale.

```
modules/ea-heidelberg/
  public/
    index.html          # language gate: redirects by navigator.language,
                         # with manual EN/DE links as fallback
    style.css            # shared design system (teal/cream/amber, Sora+Inter)
    script.js             # shared vanilla JS: nav toggle, count-up stats,
                           # scroll-reveal, animated/interactive chart,
                           # generic reveal-groups (quiz + spending compare),
                           # accordion, lazy video embed, birth-lottery-style
                           # random luck reveal
    en/
      index.html          # Home — hook, 3-line cost-effectiveness list,
                           # drowning-child video, proof strip, featured
                           # event, CTA
      what-is-ea.html      # the persuasive core: origin story, scale/
                            # neglectedness/tractability, cause areas, a
                            # mobile-safe HTML/CSS cost-effectiveness chart,
                            # cause-area mini-quiz, luck reveal, spending
                            # accordion, 80,000-hours time framing
      about.html           # the Heidelberg chapter itself (who/what/books)
      events.html           # featured upcoming event + de-emphasized past events
      contact.html           # address, map link, email
    de/
      index.html, was-ist-ea.html, ueber-uns.html, veranstaltungen.html,
      kontakt.html           # natively written German, not a translation pass
  compose.yaml            # caddy:2-alpine file server, ./public bind-mounted
  module.json
```

No app code and no build: a minimal Caddy file server serves `public/`, same
pattern as `modules/hoema`. Adding/editing a page is just editing the HTML
file and `git push` — no rebuild needed once the module is running.

## Design notes

- **Colors**: `#0388a0` teal is EA Heidelberg's own actual accent color
  (reverse-engineered from their live Squarespace CSS, not guessed) —
  carried over per the brief to keep "the official EA color scheme." Warm
  cream background, near-black text, and one amber/terracotta accent for
  CTAs round it out, echoing the broader effectivealtruism.org/GWWC
  palette family without copying either site's exact hues.
- **Structure/visuals** take cues from Giving What We Can's actual brand
  CSS (pill buttons, rounded cards, alternating color-blocked sections) and
  its flagship interactive pages (`/birth-lottery`, `/how-rich-am-i`) — but
  every interactive component here is original content, and the
  self-relevant-comparison idea was deliberately *not* built as an
  income-percentile tool, since the audience is students who mostly don't
  have a real income yet. It's a birth-lottery-style luck framing plus a
  small-everyday-spending comparison instead.
- **Persuasion approach**: combines social proof, authority, low-friction
  CTAs, and personal relevance (per Cialdini + EA Forum message-testing
  discussion) rather than leaning on one rhetorical trick. Every borrowed
  statistic is attributed to its real source (GiveWell, GWWC, 80,000 Hours,
  WHO/UNICEF, World Bank, ILO, UNDP) — nothing is presented as EA
  Heidelberg's own data.

## Why it's password-protected

Still gated with HTTP Basic Auth in the root `Caddyfile` (`handle
/ea*`) and kept out of search engines via the site-wide
`noindex` header — this is a draft for internal review, not the live site,
and some of its content (quotes, cause-area framing) is adapted from other
organizations' material. The Caddyfile only stores a bcrypt hash of the
password, never the plaintext.

## The video

`en/index.html` and `de/index.html` embed The Life You Can Save's
"Drowning Child" video (a lazy click-to-play facade — nothing loads from
YouTube until clicked) right after the hero, as the emotional lead-in
before the proof strip and chart. `what-is-ea.html`/`was-ist-ea.html` keep
their own written version of the same thought experiment as the fuller
textual case, so the two aren't redundant — one is the hook, the other is
the argument.

## Status

Content and interactions are drafted and wired up across all 10 pages in
both languages, iterated against a design-preview Artifact through
several rounds of feedback (palette brightness, headline tone, mobile
chart legibility, a birth-lottery logic bug, more concrete/felt phrasing).
No live visual QA has been done in a real browser from this session (no
browser tool available here) — worth a real look before calling it final,
especially on an actual phone.
