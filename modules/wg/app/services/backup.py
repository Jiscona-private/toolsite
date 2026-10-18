from __future__ import annotations

import gzip
import shutil
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

from app.config import settings


def run_backup() -> Path:
    """SQLite online-backup into a timestamped, gzip'd copy, pruning
    anything older than BACKUP_KEEP_DAYS. See spec.md §8.3."""
    backup_dir = Path(settings.backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)

    stamp = datetime.now(UTC).strftime("%Y-%m-%d")
    target = backup_dir / f"wg-{stamp}.db.gz"
    tmp_path = backup_dir / f".wg-{stamp}.db.tmp"

    source = sqlite3.connect(settings.database_path)
    try:
        dest = sqlite3.connect(tmp_path)
        try:
            source.backup(dest)
        finally:
            dest.close()
    finally:
        source.close()

    with tmp_path.open("rb") as raw, gzip.open(target, "wb") as gz:
        shutil.copyfileobj(raw, gz)
    tmp_path.unlink()

    _prune_old_backups(backup_dir)
    return target


def _prune_old_backups(backup_dir: Path) -> None:
    cutoff = time.time() - settings.backup_keep_days * 86400
    for backup_file in backup_dir.glob("wg-*.db.gz"):
        if backup_file.stat().st_mtime < cutoff:
            backup_file.unlink()
