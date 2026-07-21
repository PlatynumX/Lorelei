# Taradino 20251222 pinned startup fixture

`tests/fixtures/taradino-20251222-rt_main-startup.c` mirrors the startup shape
of upstream Taradino tag 20251222 / release commit 7ecc532.

The upstream startup statements use one-space indentation. Earlier R41 tests
used a synthetic four-space fixture, while the patcher matched exact
indentation. R41c removes that mismatch by using whitespace-tolerant regular
expressions anchored to actual C statements rather than comments.
