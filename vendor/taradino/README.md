# Taradino source staging

Run `tools/fetch_taradino.sh` to place the upstream engine in `source/`.
It is intentionally not compiled by milestone 0. The first milestone proves the
N64 build, filesystem, Expansion Pak detection, and endian-safe WAD access before
large SDL-dependent engine modules are introduced.
