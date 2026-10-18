#!/usr/bin/env bash
# Scaffold a new module from modules/_template.
#
# Usage: scripts/new-module.sh <module-id> "<Module Name>" "<description>"
set -euo pipefail

if [ $# -lt 2 ]; then
  echo "Usage: $0 <module-id> \"<Module Name>\" [\"<description>\"]" >&2
  exit 1
fi

MODULE_ID="$1"
MODULE_NAME="$2"
MODULE_DESCRIPTION="${3:-}"

if ! [[ "$MODULE_ID" =~ ^[a-z0-9][a-z0-9-]*$ ]]; then
  echo "Error: module-id must be lowercase letters, digits, and hyphens (e.g. 'book-club')." >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE_DIR="$ROOT_DIR/modules/_template"
TARGET_DIR="$ROOT_DIR/modules/$MODULE_ID"

if [ -e "$TARGET_DIR" ]; then
  echo "Error: $TARGET_DIR already exists." >&2
  exit 1
fi

cp -r "$TEMPLATE_DIR" "$TARGET_DIR"
rm -f "$TARGET_DIR/README.md"

# Substitute placeholders in every copied file (module.json, compose.yaml,
# package.json, server.js).
find "$TARGET_DIR" -type f -print0 | while IFS= read -r -d '' file; do
  sed -i \
    -e "s/__MODULE_ID__/$MODULE_ID/g" \
    -e "s/__MODULE_NAME__/$MODULE_NAME/g" \
    -e "s/__MODULE_DESCRIPTION__/$MODULE_DESCRIPTION/g" \
    "$file"
done

echo "Created modules/$MODULE_ID/"
echo
echo "Two manual steps left:"
echo "  1. Add this line to docker-compose.yml under 'include:':"
echo "       - modules/$MODULE_ID/compose.yaml"
echo "  2. If this module will hold personal/sensitive data, add a Basic"
echo "     Auth block for it in the Caddyfile (copy the /wg* block as a"
echo "     starting point)."
echo
echo "Then: docker compose up -d --build"
