#!/usr/bin/env bash
# Parse every page with MyST, resolve every cross-reference, and fail on any warning.
#
# MyST is a parser here, not a renderer: scripts/build-site.py renders the site from the parse in
# _build/site/content. A local template manifest lets MyST export the content without pulling a
# rendering theme. A broken reference, missing literalinclude anchor or unknown directive fails
# the build.
set -uo pipefail
cd "$(dirname "$0")/.."

if ! command -v myst >/dev/null 2>&1; then
  echo "ERROR: myst is not installed. Install the pinned version with:" >&2
  echo "  npm install -g \"mystmd@$(node -p "require('./package.json').devDependencies.mystmd")\"" >&2
  exit 1
fi

log=$(mktemp)
rm -rf _build/site
myst build --site --strict > "$log" 2>&1
status=$?

if ! grep -qE "Built [0-9]+ pages" "$log"; then
  echo "ERROR: MyST did not parse the book:" >&2
  tail -25 "$log" >&2
  rm -f "$log"
  exit 1
fi
if grep -E "⚠|⛔" "$log" >&2; then
  echo "ERROR: MyST reported warnings (broken reference, anchor or directive) above." >&2
  rm -f "$log"
  exit 1
fi
if [ "$status" -ne 0 ]; then
  echo "ERROR: MyST failed after parsing:" >&2
  tail -25 "$log" >&2
  rm -f "$log"
  exit 1
fi
echo "  $(grep -oE 'Built [0-9]+ pages' "$log" | tail -1), no warnings"
rm -f "$log"
