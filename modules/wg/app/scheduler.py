from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db import SessionLocal
from app.services import activity, notify
from app.services.backup import run_backup

logger = logging.getLogger(__name__)

# spec.md §8.3: both jobs run with coalesce=True (a missed run doesn't
# fire twice back to back) and a generous misfire_grace_time (the app may
# have been down briefly over its own nightly window).
_JOB_DEFAULTS = {"coalesce": True, "misfire_grace_time": 3600}


def _run_daily_purge() -> None:
    db = SessionLocal()
    try:
        activity.run_daily_purge(db)
        db.commit()
    finally:
        db.close()


def _run_backup() -> None:
    try:
        run_backup()
    except Exception:
        logger.exception("Scheduled backup failed")
        db = SessionLocal()
        try:
            notify.send_admin_alert(
                db, "Das nächtliche Backup ist fehlgeschlagen. Bitte Logs prüfen."
            )
        finally:
            db.close()


def start_scheduler() -> BackgroundScheduler:
    """One BackgroundScheduler per process, per CLAUDE.md rule 7 (exactly
    one Uvicorn worker) - a second worker would run every job twice."""
    scheduler = BackgroundScheduler(timezone="Europe/Berlin")
    scheduler.add_job(_run_backup, CronTrigger(hour=3, minute=30), id="backup", **_JOB_DEFAULTS)
    scheduler.add_job(
        _run_daily_purge, CronTrigger(hour=4, minute=0), id="daily_purge", **_JOB_DEFAULTS
    )
    scheduler.start()
    return scheduler
