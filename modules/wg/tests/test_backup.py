import os
import time
from pathlib import Path

import pytest

from app.config import settings
from app.services.backup import run_backup


def test_run_backup_creates_gzip_and_prunes_old_ones(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "wg.db"
    db_path.write_bytes(b"")  # sqlite3 treats a 0-byte file as a valid empty database
    backup_dir = tmp_path / "backups"
    backup_dir.mkdir()

    monkeypatch.setattr(settings, "database_path", str(db_path))
    monkeypatch.setattr(settings, "backup_dir", str(backup_dir))
    monkeypatch.setattr(settings, "backup_keep_days", 1)

    stale = backup_dir / "wg-2000-01-01.db.gz"
    stale.write_bytes(b"old")
    two_days_ago = time.time() - 2 * 86400
    os.utime(stale, (two_days_ago, two_days_ago))

    target = run_backup()

    assert target.exists()
    assert target.read_bytes()[:2] == b"\x1f\x8b"  # gzip magic number
    assert not stale.exists()
