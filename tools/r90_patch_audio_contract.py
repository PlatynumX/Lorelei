#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path
import re
import sys

MARK = "ROTT64_R90_GENERATED_AUDIO_CONTRACT"

CONTRACT_CALLS = (
    "mixer_ch_play",
    "mixer_ch_stop",
    "mixer_ch_playing",
    "mixer_ch_set_vol",
    "mixer_ch_set_vol_pan",
    "mixer_ch_set_freq",
)

FORBIDDEN_DIRECT = (
    "mixer_init",
    "mixer_poll",
    "audio_init",
    "audio_write_begin",
    "audio_write_end",
    "rspq_highpri_sync",
    "rspq_block_begin",
    "rspq_block_run",
)

def scrub(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
    return text

def has_call(text: str, name: str) -> bool:
    return re.search(r"\b" + re.escape(name) + r"\s*\(", scrub(text)) is not None

def add_contract_include(text: str) -> str:
    if '#include "rott64_audio.h"' in text:
        return text
    includes = list(re.finditer(r"(?m)^#include[^\n]*\n", text))
    if includes:
        pos = includes[-1].end()
        return text[:pos] + '#include "rott64_audio.h"\n' + text[pos:]
    return '#include "rott64_audio.h"\n' + text

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("ERROR: usage: r90_patch_audio_contract.py generated/rott")

    gen = Path(argv[1])
    if not gen.is_dir():
        raise SystemExit("ERROR: generated/rott directory not found")

    changed = []
    forbidden = []

    for path in sorted(gen.glob("*.c")):
        text = path.read_text(encoding="utf-8", errors="strict")
        clean = scrub(text)

        for name in FORBIDDEN_DIRECT:
            if re.search(r"\b" + re.escape(name) + r"\s*\(", clean):
                forbidden.append(f"{path}:{name}")

        if any(re.search(r"\b" + re.escape(name) + r"\s*\(", clean)
               for name in CONTRACT_CALLS):
            patched = add_contract_include(text)
            if MARK not in patched:
                patched = "/* " + MARK + " */\n" + patched
            if patched != text:
                path.write_text(patched.rstrip() + "\n", encoding="utf-8", newline="\n")
                changed.append(str(path))

    if forbidden:
        raise SystemExit(
            "ERROR: generated code bypasses ROTT64 audio contract:\n"
            + "\n".join(forbidden[:80])
        )

    print("PASS: " + MARK)
    if changed:
        print("PASS: generated files made contract-explicit:")
        for item in changed:
            print("  " + item)
    else:
        print("PASS: generated audio contract already explicit or no mixer channel calls found")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
