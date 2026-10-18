import pytest

from app import scheduler as scheduler_module
from app.scheduler import start_scheduler


def _field(job, name: str):
    return next(f for f in job.trigger.fields if f.name == name)


@pytest.mark.parametrize(("job_id", "hour", "minute"), [("backup", 3, 30), ("daily_purge", 4, 0)])
def test_start_scheduler_registers_both_jobs(job_id: str, hour: int, minute: int) -> None:
    scheduler = start_scheduler()
    try:
        job = scheduler.get_job(job_id)
        assert job is not None
        assert _field(job, "hour").expressions[0].first == hour
        assert _field(job, "minute").expressions[0].first == minute
        # spec.md §8.3: a missed run (app down over its own job window)
        # doesn't fire twice back to back, and gets a generous grace period.
        assert job.coalesce is True
        assert job.misfire_grace_time == 3600
    finally:
        scheduler.shutdown(wait=False)


def test_run_backup_sends_an_admin_alert_on_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom():
        raise RuntimeError("disk full")

    sent: list[str] = []
    monkeypatch.setattr(scheduler_module, "run_backup", _boom)
    monkeypatch.setattr(
        scheduler_module.notify, "send_admin_alert", lambda db, message: sent.append(message)
    )

    scheduler_module._run_backup()

    assert sent == ["Das nächtliche Backup ist fehlgeschlagen. Bitte Logs prüfen."]
