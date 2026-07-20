#ifndef ROTT64_AUDIO_H
#define ROTT64_AUDIO_H

/* Taradino FX owns channels 0..7. Native sequenced MIDI owns 8..15.
 * Each MIDI note is a tiny looped waveform resampled/mixed by libdragon's RSP
 * mixer, avoiding CPU-per-sample synthesis stalls. */
#define ROTT64_FX_CHANNELS 8
#define ROTT64_MUSIC_CHANNEL_BASE 8
#define ROTT64_MUSIC_VOICES 8
#define ROTT64_MUSIC_CHANNEL ROTT64_MUSIC_CHANNEL_BASE
#define ROTT64_MIXER_CHANNELS 16

/* Service non-blocking music restart logic from the normal audio pump. */
void rott64_music_pump(void);

#endif
