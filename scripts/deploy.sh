#!/usr/bin/env bash
# Pull the latest code and (re)build/restart the whole stack on the VPS.
# Run this from the repo root on the server itself.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [ ! -f .env ]; then
  echo "Error: .env not found. Copy .env.example to .env and fill it in first." >&2
  exit 1
fi

caddyfile_hash() { sha256sum Caddyfile 2>/dev/null | cut -d' ' -f1; }
BEFORE_CADDY="$(caddyfile_hash)"

echo "==> Pulling latest changes"
git pull --ff-only

echo "==> Building images"
docker compose build

echo "==> Starting/updating containers"
docker compose up -d --remove-orphans

# The Caddyfile is a single-file bind mount. `git pull` replaces the file
# (new inode), so the running caddy container keeps seeing the old one.
# Recreate caddy whenever the Caddyfile changed so new routes take effect.
if [ "$BEFORE_CADDY" != "$(caddyfile_hash)" ]; then
  echo "==> Caddyfile changed, recreating caddy"
  docker compose up -d --force-recreate caddy
fi

echo "==> Current status"
docker compose ps
