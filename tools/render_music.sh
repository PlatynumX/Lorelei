#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MUSIC_DIR="${1:-$ROOT/assets/music}"

command -v timidity >/dev/null 2>&1 || {
  echo "render_music.sh: timidity is required" >&2
  exit 1
}
command -v ffmpeg >/dev/null 2>&1 || {
  echo "render_music.sh: ffmpeg is required" >&2
  exit 1
}

shopt -s nullglob
midis=("$MUSIC_DIR"/*.mid)
if (( ${#midis[@]} == 0 )); then
  echo "render_music.sh: no MIDI files found in $MUSIC_DIR" >&2
  exit 1
fi

timidity_args=()
if [[ -f /etc/timidity/freepats.cfg ]]; then
  timidity_args=(-c /etc/timidity/freepats.cfg)
fi

for midi in "${midis[@]}"; do
  stem="${midi%.mid}"
  raw="${stem}.timidity.wav"
  wav="${stem}.wav"
  echo "[music] render $(basename "$midi")"
  # ROTTDS used TiMidity at 22050 Hz for its console music conversion. Render
  # offline here so no MIDI synthesizer or SoundFont is needed on the N64.
  timidity "${timidity_args[@]}" "$midi" -Ow1sM -s 22050 -o "$raw" >/dev/null 2>&1
  ffmpeg -y -loglevel error -i "$raw" -ar 22050 -ac 1 -c:a pcm_s16le "$wav"
  rm -f "$raw"
done

echo "[music] rendered ${#midis[@]} tracks to mono 22050 Hz PCM WAV"
