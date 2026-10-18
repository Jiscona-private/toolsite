from app.scheduler import start_scheduler


def _field(job, name: str):
    return next(f for f in job.trigger.fields if f.name == name)


def test_start_scheduler_registers_the_daily_purge_job() -> None:
    scheduler = start_scheduler()
    try:
        job = scheduler.get_job("daily_purge")
        assert job is not None
        assert _field(job, "hour").expressions[0].first == 4
        assert _field(job, "minute").expressions[0].first == 0
    finally:
        scheduler.shutdown(wait=False)
