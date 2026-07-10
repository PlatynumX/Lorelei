#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1090
source "$ROOT/config/rottds.lock"
ARCHIVE="$ROOT/vendor/rottds/rottds-source.tar.bz2"
DEST="$ROOT/vendor/rottds/source"
mkdir -p "$(dirname "$ARCHIVE")"
if [[ ! -s "$ARCHIVE" ]]; then
  curl --fail --location --retry 3 --retry-delay 2 \
    --user-agent "ROTT64 reference fetcher" -o "$ARCHIVE.part" "$ROTTDS_SOURCE_URL"
  mv "$ARCHIVE.part" "$ARCHIVE"
fi
rm -rf "$DEST"
mkdir -p "$DEST"
tar -xjf "$ARCHIVE" -C "$DEST" --strip-components=1 2>/dev/null || {
  rm -rf "$DEST"; mkdir -p "$DEST"; tar -xjf "$ARCHIVE" -C "$DEST";
}
printf '%s\n' "$ROTTDS_VERSION" > "$DEST/.rott64-version"
echo "ROTTDS $ROTTDS_VERSION reference source extracted"
