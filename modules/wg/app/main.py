from fastapi import APIRouter, Depends, FastAPI
from fastapi.responses import PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware

from app import models  # noqa: F401  # registers every table with Base.metadata
from app.auth import access_gate
from app.auth import router as auth_router
from app.config import settings
from app.db import get_db


def create_app() -> FastAPI:
    # No Swagger/Redoc: both pull their JS/CSS from a CDN, which the app's
    # CSP (no external resources, see CLAUDE.md rule 5) blocks anyway.
    app = FastAPI(title="WG-App", docs_url=None, redoc_url=None)
    app.add_middleware(BaseHTTPMiddleware, dispatch=access_gate)

    router = APIRouter(prefix=settings.base_path)

    @router.get("/healthz")
    def healthz(db: Session = Depends(get_db)) -> PlainTextResponse:
        db.execute(text("SELECT 1"))
        return PlainTextResponse("ok")

    app.include_router(router)
    app.include_router(auth_router)
    return app


app = create_app()
