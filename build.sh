#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

make test-host

for file in DARKWAR.WAD DARKWAR.RTL DARKWAR.RTC; do
    test -s "filesystem/rott/$file" || {
        echo "Missing or empty filesystem/rott/$file" >&2
        exit 1
    }
done

python3 tools/extract_music.py \
  filesystem/rott/DARKWAR.WAD \
  assets/music \
  platform/n64/n64_music_map_generated.h \
  --mode full
bash tools/render_music.sh assets/music
tools/fetch_taradino.sh
tools/fetch_rottds.sh || echo "ROTTDS reference download failed; continuing with the pinned policy notes"
make prepare
make preflight
make reports
mkdir -p ci-reports
cp -a build/reports/. ci-reports/ 2>/dev/null || true

set -o pipefail
docker run --rm \
  -v "$ROOT:/project" \
  -w /project \
  ghcr.io/dragonminded/libdragon:latest \
  sh -lc '
    set -eux
    rm -rf /tmp/libdragon
    git clone --depth 1 \
      https://github.com/DragonMinded/libdragon.git /tmp/libdragon
    make -C /tmp/libdragon -j2 install tools-install
    make -j2
  ' 2>&1 | tee ci-reports/n64-build.log

sha256sum rott64.z64 | tee rott64.z64.sha256


python3 - <<'PY'
from pathlib import Path
p = Path("rott64.z64")
data = p.read_bytes() if p.is_file() else b""
if len(data) < 1024 * 1024:
    raise SystemExit("Final ROM missing or implausibly small")
if len(data) > 78_000_000:
    raise SystemExit(f"Final ROM exceeds 78,000,000 bytes: {len(data)}")
if data[:4] != bytes.fromhex("80371240"):
    raise SystemExit("Final ROM is not big-endian .z64")
print(f"Validated final ROM: {len(data)} bytes")
PY
