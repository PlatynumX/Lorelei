#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LIBDRAGON_REF="${LIBDRAGON_REF:-trunk}"
cd "$ROOT"

make test-host
tools/fetch_shareware.sh
tools/fetch_taradino.sh
tools/fetch_rottds.sh || echo "ROTTDS reference download failed; continuing with the pinned policy notes"
make prepare
make preflight
make reports
mkdir -p ci-reports
cp -a build/reports/. ci-reports/ 2>/dev/null || true

set -o pipefail
docker run --rm \
  -e LIBDRAGON_REF="$LIBDRAGON_REF" \
  -v "$ROOT:/project" \
  -w /project \
  ghcr.io/dragonminded/libdragon:latest \
  sh -lc '
    set -eux
    rm -rf /tmp/libdragon
    git clone --depth 1 --branch "$LIBDRAGON_REF" \
      https://github.com/DragonMinded/libdragon.git /tmp/libdragon
    make -C /tmp/libdragon -j2 install tools-install
    make -j2
  ' 2>&1 | tee ci-reports/n64-build.log

sha256sum rott64.z64 | tee rott64.z64.sha256
