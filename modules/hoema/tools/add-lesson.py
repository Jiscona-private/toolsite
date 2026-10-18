#!/usr/bin/env python3
"""Add or update a HöMa I lesson page in modules/hoema/public/.

Usage:
    python3 modules/hoema/tools/add-lesson.py LE02 path/to/lesson.html [--title "..."]

What it does:
  * copies the lesson HTML to public/<id lowercased>.html (e.g. le02.html),
  * sets <html lang="de"> and adds a "← Alle Lektionen" link (idempotent),
  * refuses pages that could send answers anywhere (see PRIVACY below),
  * marks the lesson as available in public/lessons.json (file, section
    count, localStorage prefix, last update).

PRIVACY: lessons are public. A visitor's answers and progress must stay in
that visitor's own browser (localStorage). A lesson page must never send
answers to a server, so that only the owner's own answers (reported in the
study chat) feed into repetition planning. The script rejects pages that use
network or Claude-runtime APIs in their own code.
"""
import argparse
import datetime
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PUBLIC = HERE.parent / "public"
INDEX = PUBLIC / "lessons.json"
BACK_MARK = "<!-- hoema:back -->"
BACK_LINK = BACK_MARK + '<a href="./" style="color:inherit">← Alle Lektionen</a> · '

# Network/runtime calls a lesson's own script must not make. Script tags that
# load libraries (KaTeX, fonts) are fine; these patterns target code that
# would transmit data.
FORBIDDEN = [
    (r"\bfetch\s*\(", "fetch()"),
    (r"XMLHttpRequest", "XMLHttpRequest"),
    (r"sendBeacon", "navigator.sendBeacon"),
    (r"\bWebSocket\b", "WebSocket"),
    (r"window\.claude", "window.claude (Artifact runtime)"),
    (r"<form[^>]*\baction\s*=", "<form action=...>"),
]


def inline_scripts(html: str) -> str:
    """Return the bodies of inline <script> tags (no src attribute)."""
    return "\n".join(
        m.group(1)
        for m in re.finditer(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", html, re.S | re.I)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("lesson_id", help="e.g. LE02, R1, K1")
    ap.add_argument("source", type=Path, help="lesson HTML (e.g. the published artifact)")
    ap.add_argument("--title", help="override the title shown in the overview")
    args = ap.parse_args()

    lid = args.lesson_id.upper()
    html = args.source.read_text(encoding="utf-8")

    code = inline_scripts(html)
    problems = [
        name for pat, name in FORBIDDEN
        if re.search(pat, html if pat.startswith("<form") else code, re.I)
    ]
    if problems:
        print(f"refusing {args.source}: page could transmit data ({', '.join(problems)})", file=sys.stderr)
        return 1

    # lang attribute
    html, n = re.subn(r"<html(?![^>]*\blang=)", '<html lang="de"', html, count=1, flags=re.I)

    # back link into the hero eyebrow (or right after <body> as fallback)
    if BACK_MARK not in html:
        html, n = re.subn(r'(<div class="eyebrow">)', r"\1" + BACK_LINK.replace("\\", "\\\\"), html, count=1)
        if n == 0:
            html = re.sub(r"(<body[^>]*>)", r'\1<p style="margin:8px 16px;font:14px sans-serif">' + BACK_LINK + "</p>", html, count=1, flags=re.I)

    sections = len(re.findall(r"<section[^>]*\bdata-sec\b", html))
    prefix_m = re.search(r'var\s+PREFIX\s*=\s*"([^"]+)"', html)

    fname = lid.lower() + ".html"
    (PUBLIC / fname).write_text(html, encoding="utf-8")

    data = json.loads(INDEX.read_text(encoding="utf-8"))
    entry = next((l for l in data["lessons"] if l["id"] == lid), None)
    if entry is None:
        entry = {"id": lid, "title": args.title or lid, "week": ""}
        data["lessons"].append(entry)
    if args.title:
        entry["title"] = args.title
    entry["file"] = fname
    entry["sections"] = sections
    if prefix_m:
        entry["storagePrefix"] = prefix_m.group(1)
    entry["updated"] = datetime.date.today().isoformat()
    INDEX.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"{lid}: wrote public/{fname} ({sections} sections, prefix {entry.get('storagePrefix')})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
