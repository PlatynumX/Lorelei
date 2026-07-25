#ifndef ROTT64_AUDIO_H
#define ROTT64_AUDIO_H

/* ROTT64_R90E_AUDIO_CHANNEL_CONTRACT
 *
 * One owner for libdragon audio/mixer initialization and channel routing.
 *
 * FX channels:      0..7
 * Music owner:      8
 * Music stereo sub: 9
 *
 * libdragon stereo waveforms consume the owner channel and owner+1.  The old
 * 9-channel contract made channel 8 usable for mono music only; stereo music
 * needs channel 9 to exist as the reserved subchannel.  Keep FX isolated from
 * the music pair and initialize the mixer with all 10 channels.
 */
#define ROTT64_FX_CHANNELS 8
#define ROTT64_MUSIC_CHANNEL 8
#define ROTT64_MUSIC_STEREO_SUBCHANNEL 9
#define ROTT64_MIXER_CHANNELS 10

#define ROTT64_AUDIO_FREQUENCY 22050
#define ROTT64_AUDIO_BUFFERS 4

#ifdef __N64__
#include <mixer.h>
#else
typedef struct waveform_s waveform_t;
#endif

#ifdef __cplusplus
extern "C" {
#endif

int rott64_audio_init_once(void);
void rott64_audio_shutdown(void);
void rott64_audio_pump(void);

void rott64_audio_play_channel_checked(int ch, waveform_t *wave,
                                       const char *file, int line);
void rott64_audio_stop_channel_checked(int ch, const char *file, int line);
int rott64_audio_channel_playing_checked(int ch, const char *file, int line);
void rott64_audio_set_channel_vol_checked(int ch, float lvol, float rvol,
                                          const char *file, int line);
void rott64_audio_set_channel_vol_pan_checked(int ch, float vol, float pan,
                                              const char *file, int line);
void rott64_audio_set_channel_freq_checked(int ch, float frequency,
                                           const char *file, int line);

#ifdef __cplusplus
}
#endif

#if defined(__N64__) && !defined(ROTT64_AUDIO_IMPLEMENTATION)
/*
 * Generated Taradino code can still call libdragon's normal mixer API.  These
 * macros route those calls through the ROTT64 contract without rewriting or
 * silencing generated audio functions.
 */
#define mixer_ch_play(ch, wave) \
    rott64_audio_play_channel_checked((ch), (wave), __FILE__, __LINE__)
#define mixer_ch_stop(ch) \
    rott64_audio_stop_channel_checked((ch), __FILE__, __LINE__)
#define mixer_ch_playing(ch) \
    rott64_audio_channel_playing_checked((ch), __FILE__, __LINE__)
#define mixer_ch_set_vol(ch, lvol, rvol) \
    rott64_audio_set_channel_vol_checked((ch), (lvol), (rvol), __FILE__, __LINE__)
#define mixer_ch_set_vol_pan(ch, vol, pan) \
    rott64_audio_set_channel_vol_pan_checked((ch), (vol), (pan), __FILE__, __LINE__)
#define mixer_ch_set_freq(ch, frequency) \
    rott64_audio_set_channel_freq_checked((ch), (frequency), __FILE__, __LINE__)
#endif

#endif /* ROTT64_AUDIO_H */
