from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Request
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlalchemy import text
from sqlalchemy.orm import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.staticfiles import StaticFiles

from app import models  # noqa: F401  # registers every table with Base.metadata
from app.auth import access_gate
from app.auth import router as auth_router
from app.config import settings
from app.db import get_db
from app.routes.board import router as board_router
from app.routes.chores import router as chores_router
from app.routes.expenses import router as expenses_router
from app.routes.expenses import settlements_router
from app.routes.home import router as home_router
from app.routes.profile import router as profile_router
from app.routes.settings import router as settings_router
from app.routes.shopping import router as shopping_router
from app.scheduler import start_scheduler
from app.templating import base_context, templates


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    # TestClient(app) used without "with" (as every test in this repo does)
    # never triggers lifespan, so the scheduler only ever runs under a real
    # Uvicorn process - see CLAUDE.md rule 7, one worker, one scheduler.
    scheduler = start_scheduler()
    yield
    scheduler.shutdown(wait=False)


def create_app() -> FastAPI:
    # No Swagger/Redoc: both pull their JS/CSS from a CDN, which the app's
    # CSP (no external resources, see CLAUDE.md rule 5) blocks anyway.
    app = FastAPI(title="WG-App", docs_url=None, redoc_url=None, lifespan=_lifespan)
    app.add_middleware(BaseHTTPMiddleware, dispatch=access_gate)
    app.mount(
        f"{settings.base_path}/static",
        StaticFiles(directory=str(Path(__file__).parent / "static")),
        name="static",
    )

    router = APIRouter(prefix=settings.base_path)

    @router.get("/healthz")
    def healthz(db: Session = Depends(get_db)) -> PlainTextResponse:
        db.execute(text("SELECT 1"))
        return PlainTextResponse("ok")

    @router.get("/new")
    def new_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse:
        return templates.TemplateResponse(request, "pages/new.html", base_context(request, db))

    app.include_router(router)
    app.include_router(home_router)
    app.include_router(auth_router)
    app.include_router(chores_router)
    app.include_router(expenses_router)
    app.include_router(settlements_router)
    app.include_router(shopping_router)
    app.include_router(board_router)
    app.include_router(profile_router)
    app.include_router(settings_router)
    return app


app = create_app()
