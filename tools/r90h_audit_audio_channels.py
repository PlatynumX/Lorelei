#!/usr/bin/env python3
from __future__ import annotations
from pathlib import Path
import re
import sys

def scrub(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//.*", "", text)
    text = re.sub(r'"(?:\\.|[^"\\])*"', '""', text)
    text = re.sub(r"'(?:\\.|[^'\\])*'", "''", text)
    return text

def read_define(header: str, name: str) -> int:
    m = re.search(rf"(?m)^#define[ \t]+{re.escape(name)}[ \t]+([0-9]+)\b", header)
    if not m:
        raise SystemExit("ERROR: missing audio define " + name)
    return int(m.group(1))

def main(argv: list[str]) -> int:
    if len(argv) != 2:
        raise SystemExit("ERROR: usage: r90h_audit_audio_channels.py generated/rott")

    gen = Path(argv[1])
    header = Path("platform/n64/rott64_audio.h").read_text(encoding="utf-8")
    mixer_channels = read_define(header, "ROTT64_MIXER_CHANNELS")
    music_ch = read_define(header, "ROTT64_MUSIC_CHANNEL")
    music_sub = read_define(header, "ROTT64_MUSIC_STEREO_SUBCHANNEL")

    if (mixer_channels, music_ch, music_sub) != (10, 8, 9):
        raise SystemExit("ERROR: unexpected r90h audio channel contract")

    max_literal = -1
    literal_hits = 0

    for p in sorted(gen.glob("*.c")):
        text = scrub(p.read_text(encoding="utf-8", errors="ignore"))

        for name in (
            "mixer_init",
            "mixer_poll",
            "audio_init",
            "audio_write_begin",
            "audio_write_end",
            "rspq_highpri_sync",
            "rott64_audio_play_channel_checked",
            "rott64_audio_stop_channel_checked",
            "rott64_audio_channel_playing_checked",
            "rott64_audio_set_channel_vol_checked",
        ):
            if re.search(r"\b" + re.escape(name) + r"\s*\(", text):
                raise SystemExit(f"ERROR: generated code bypasses real mixer backend: {p}:{name}")

        for m in re.finditer(r"\bmixer_ch_(?:play|stop|playing|set_vol|set_vol_pan|set_freq)\s*\(\s*([0-9]+)\b", text):
            ch = int(m.group(1))
            max_literal = max(max_literal, ch)
            literal_hits += 1
            if ch >= mixer_channels:
                raise SystemExit(f"ERROR: generated mixer channel {ch} exceeds count {mixer_channels}: {p}")

    print("PASS: ROTT64_R90H_AUDIO_CHANNEL_AUDIT")
    print(f"PASS: mixer channels: {mixer_channels}; music pair: {music_ch}/{music_sub}; max literal channel: {max_literal}")
    print(f"PASS: literal generated channel calls audited: {literal_hits}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
