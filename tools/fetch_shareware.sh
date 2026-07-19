#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARCHIVE="${1:-$ROOT/vendor/shareware/rottds-data.tar.bz2}"
ROTTDS_URL="${ROTT_SHAREWARE_URL:-https://vespenegas.com/rottds-data.tar.bz2}"
FALLBACK_URL="https://image.dosgamesarchive.com/games/huntbgin-box.zip"
mkdir -p "$(dirname "$ARCHIVE")"
if [[ ! -s "$ARCHIVE" ]]; then
  echo "[shareware] Downloading the official ROTTDS shareware data pack"
  if ! curl --fail --location --retry 3 --retry-delay 2 \
      --user-agent "ROTT64 first-level builder" -o "$ARCHIVE.part" "$ROTTDS_URL"; then
    echo "[shareware] ROTTDS data unavailable; using installed v1.3 shareware ZIP"
    ARCHIVE="$ROOT/vendor/shareware/huntbgin-box.zip"
    curl --fail --location --retry 3 --retry-delay 2 \
      --user-agent "ROTT64 first-level builder" -o "$ARCHIVE.part" "$FALLBACK_URL"
  fi
  mv "$ARCHIVE.part" "$ARCHIVE"
else
  echo "[shareware] Reusing $ARCHIVE"
fi
python3 "$ROOT/tools/prepare_shareware.py" "$ARCHIVE" "$ROOT/filesystem/rott"
