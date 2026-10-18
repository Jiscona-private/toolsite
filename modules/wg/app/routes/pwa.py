from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Setting
from app.templating import base_context, templates

router = APIRouter(prefix=settings.base_path)

# design.md §1.1: accent / page background.
THEME_COLOR = "#1F6F5C"
BACKGROUND_COLOR = "#F4F5F1"


@router.get("/manifest.webmanifest")
def manifest(db: Session = Depends(get_db)) -> JSONResponse:
    wg_name_setting = db.get(Setting, "wg_name")
    wg_name = wg_name_setting.value if wg_name_setting else "WG-App"
    base = settings.base_path
    data = {
        "name": wg_name,
        "short_name": wg_name,
        "start_url": f"{base}/",
        "scope": f"{base}/",
        "display": "standalone",
        "theme_color": THEME_COLOR,
        "background_color": BACKGROUND_COLOR,
        "icons": [
            {
                "src": f"{base}/static/icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable",
            },
            {
                "src": f"{base}/static/icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable",
            },
        ],
    }
    return JSONResponse(data, media_type="application/manifest+json")


@router.get("/offline")
def offline_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
    return templates.TemplateResponse(
        request, "pages/offline.html", base_context(request, db, active_nav=None)
    )


# Bump this on every deploy that changes a precached file - the activate
# handler below drops any cache under a different name.
_CACHE_NAME = "wg-static-v1"
_PRECACHE_PATHS = (
    "/static/css/app.css",
    "/static/js/htmx.min.js",
    "/static/js/app.js",
    "/static/icons/sprite.svg",
    "/static/icons/icon-192.png",
    "/offline",
)


@router.get("/sw.js")
def service_worker() -> PlainTextResponse:
    """spec.md §9.2: static assets cache-first, HTML network-first with an
    offline fallback, no POSTs ever cached (the fetch handler below only
    ever looks at GET requests)."""
    base = settings.base_path
    precache_urls = ", ".join(f'"{base}{path}"' for path in _PRECACHE_PATHS)
    script = f"""const CACHE_NAME = "{_CACHE_NAME}";
const OFFLINE_URL = "{base}/offline";
const PRECACHE_URLS = [{precache_urls}];

self.addEventListener("install", (event) => {{
  event.waitUntil(caches.open(CACHE_NAME).then((cache) => cache.addAll(PRECACHE_URLS)));
}});

self.addEventListener("activate", (event) => {{
  event.waitUntil(
    caches.keys().then((keys) => {{
      const stale = keys.filter((key) => key !== CACHE_NAME);
      return Promise.all(stale.map((key) => caches.delete(key)));
    }})
  );
}});

self.addEventListener("fetch", (event) => {{
  const request = event.request;
  if (request.method !== "GET" || new URL(request.url).origin !== self.location.origin) {{
    return;
  }}

  if (request.mode === "navigate") {{
    event.respondWith(
      fetch(request)
        .then((response) => {{
          if (response.ok) {{
            const copy = response.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(request, copy));
          }}
          return response;
        }})
        .catch(() => caches.match(request).then((cached) => cached || caches.match(OFFLINE_URL)))
    );
    return;
  }}

  if (request.url.includes("/static/")) {{
    event.respondWith(caches.match(request).then((cached) => cached || fetch(request)));
  }}
}});
"""
    # access_gate's _security_headers always forces Cache-Control: no-store
    # on the way out (it can't see this route's real media_type once
    # BaseHTTPMiddleware has wrapped the response) - fine here too: it
    # means the browser always refetches sw.js, which is what you want.
    return PlainTextResponse(script, media_type="application/javascript")
