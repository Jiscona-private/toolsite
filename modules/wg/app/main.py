from fastapi import APIRouter, FastAPI
from fastapi.responses import PlainTextResponse

from app.config import settings


def create_app() -> FastAPI:
    # No Swagger/Redoc: both pull their JS/CSS from a CDN, which the app's
    # CSP (no external resources, see CLAUDE.md rule 5) blocks anyway.
    app = FastAPI(title="WG-App", docs_url=None, redoc_url=None)

    router = APIRouter(prefix=settings.base_path)

    @router.get("/healthz")
    def healthz() -> PlainTextResponse:
        return PlainTextResponse("ok")

    app.include_router(router)
    return app


app = create_app()
