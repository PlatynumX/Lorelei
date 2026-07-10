#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCK_FILE="$ROOT/config/taradino.lock"
DEST="${TARADINO_DEST:-$ROOT/vendor/taradino/source}"

if [[ ! -f "$LOCK_FILE" ]]; then
    echo "Missing Taradino lock file: $LOCK_FILE" >&2
    exit 1
fi

# shellcheck disable=SC1090
source "$LOCK_FILE"

: "${TARADINO_REPOSITORY:?missing TARADINO_REPOSITORY in lock file}"
: "${TARADINO_REF:?missing TARADINO_REF in lock file}"
: "${TARADINO_EXPECTED_COMMIT_PREFIX:?missing expected commit prefix in lock file}"

rm -rf "$DEST"
mkdir -p "$(dirname "$DEST")"

git clone --depth 1 --branch "$TARADINO_REF" \
    "$TARADINO_REPOSITORY" "$DEST"

actual_commit="$(git -C "$DEST" rev-parse HEAD)"
case "$actual_commit" in
    "$TARADINO_EXPECTED_COMMIT_PREFIX"*) ;;
    *)
        echo "Taradino revision mismatch." >&2
        echo "Expected prefix: $TARADINO_EXPECTED_COMMIT_PREFIX" >&2
        echo "Actual commit:  $actual_commit" >&2
        exit 1
        ;;
esac

printf '%s\n' "$actual_commit" > "$DEST/.rott64-upstream-commit"
echo "Taradino $TARADINO_REF fetched at $actual_commit"
