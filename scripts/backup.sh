#!/usr/bin/env bash
# Tar up every module's persistent data/ directory into ./backups/.
# Run from the repo root (e.g. via a cron job on the VPS).
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_DIR="backups"
ARCHIVE="$BACKUP_DIR/toolsite-data-$TIMESTAMP.tar.gz"

mkdir -p "$BACKUP_DIR"

DATA_DIRS=()
for dir in modules/*/data; do
  [ -d "$dir" ] && DATA_DIRS+=("$dir")
done

if [ ${#DATA_DIRS[@]} -eq 0 ]; then
  echo "No module data/ directories found — nothing to back up."
  exit 0
fi

tar -czf "$ARCHIVE" "${DATA_DIRS[@]}"
echo "Wrote $ARCHIVE"

# Keep the last 14 backups, prune older ones.
ls -1t "$BACKUP_DIR"/toolsite-data-*.tar.gz 2>/dev/null | tail -n +15 | xargs -r rm --
