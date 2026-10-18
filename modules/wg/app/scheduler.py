from __future__ import annotations

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from app.db import SessionLocal
from app.services import activity


def _run_daily_purge() -> None:
    db = SessionLocal()
    try:
        activity.run_daily_purge(db)
        db.commit()
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    """One BackgroundScheduler per process, per CLAUDE.md rule 7 (exactly
    one Uvicorn worker) - a second worker would run every job twice.
    spec.md §8.3: trash/expired notes are purged daily at 04:00."""
    scheduler = BackgroundScheduler(timezone="Europe/Berlin")
    scheduler.add_job(_run_daily_purge, CronTrigger(hour=4, minute=0), id="daily_purge")
    scheduler.start()
    return scheduler
