from __future__ import annotations

import logging

import httpx
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Setting

logger = logging.getLogger(__name__)

NTFY_TIMEOUT_SECONDS = 5.0


def send_ntfy(
    topic: str,
    *,
    title: str,
    message: str,
    tags: list[str] | None = None,
    click: str | None = None,
    priority: int = 3,
) -> bool:
    """spec.md §8.2: JSON-Publish, 5s timeout, one retry. Rule 9 ("eine
    Benachrichtigung darf nie eine Anfrage scheitern lassen") - failures
    are logged and swallowed, never raised."""
    payload: dict = {"topic": topic, "title": title, "message": message, "priority": priority}
    if tags:
        payload["tags"] = tags
    if click:
        payload["click"] = click

    for attempt in range(2):
        try:
            response = httpx.post(
                settings.ntfy_base_url, json=payload, timeout=NTFY_TIMEOUT_SECONDS
            )
            response.raise_for_status()
            return True
        except httpx.HTTPError:
            if attempt == 1:
                logger.warning("ntfy delivery failed for topic %s", topic, exc_info=True)
    return False


def send_admin_alert(db: Session, message: str) -> bool:
    """settings.admin_ntfy_topic per spec.md §8.2: backup failures,
    unusual join failures, restart after a crash. Plain German text, not
    an i18n key - this is an operational alert for the one admin, not
    user-facing UI text (CLAUDE.md rule 2)."""
    setting = db.get(Setting, "admin_ntfy_topic")
    if setting is None:
        return False
    return send_ntfy(setting.value, title="WG-App", message=message, tags=["warning"])
