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

echo "==> Pulling latest changes"
git pull --ff-only

echo "==> Building images"
docker compose build

echo "==> Starting/updating containers"
docker compose up -d --remove-orphans

echo "==> Current status"
docker compose ps
