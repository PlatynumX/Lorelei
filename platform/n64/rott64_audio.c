#define ROTT64_AUDIO_IMPLEMENTATION 1
#include "rott64_audio.h"

#ifdef __N64__
#include <audio.h>
#include <debug.h>
#include <mixer.h>
#include <stdbool.h>
#include <stddef.h>
#else
#include <stddef.h>
#endif

#ifdef __N64__

static int rott64_audio_ready;

static int rott64_audio_wave_channels(const waveform_t *wave)
{
    if (wave == NULL)
        return 1;

    return wave->channels == 2 ? 2 : 1;
}

static int rott64_audio_normalize_channel(int ch, int required,
                                          const char *op,
                                          const char *file, int line)
{
    int mapped = ch;

    if (required < 1)
        required = 1;
    if (required > 2)
        required = 2;

    if (mapped < 0)
        mapped = 0;

    if (mapped < ROTT64_FX_CHANNELS)
    {
        if (mapped + required <= ROTT64_FX_CHANNELS)
            return mapped;

        debugf("ROTT64 audio: remap %s channel %d -> 0"
               " (%s:%d, needs %d channels)\n",
               op, ch, file ? file : "?", line, required);
        return 0;
    }

    if (ROTT64_MUSIC_CHANNEL + required <= ROTT64_MIXER_CHANNELS)
    {
        if (mapped != ROTT64_MUSIC_CHANNEL)
        {
            debugf("ROTT64 audio: remap %s channel %d -> music channel %d"
                   " (%s:%d, needs %d channels)\n",
                   op, ch, ROTT64_MUSIC_CHANNEL, file ? file : "?", line,
                   required);
        }
        return ROTT64_MUSIC_CHANNEL;
    }

    debugf("ROTT64 audio: drop %s channel %d (%s:%d, needs %d channels,"
           " mixer has %d)\n",
           op, ch, file ? file : "?", line, required, ROTT64_MIXER_CHANNELS);
    return -1;
}

int rott64_audio_init_once(void)
{
    if (rott64_audio_ready)
        return 1;

    audio_init(ROTT64_AUDIO_FREQUENCY, ROTT64_AUDIO_BUFFERS);
    mixer_init(ROTT64_MIXER_CHANNELS);
    mixer_set_vol(1.0f);

    rott64_audio_ready = 1;
    debugf("ROTT64 audio: init %d Hz, %d buffers, %d mixer channels"
           " (fx 0-%d, music %d/%d)\n",
           ROTT64_AUDIO_FREQUENCY,
           ROTT64_AUDIO_BUFFERS,
           ROTT64_MIXER_CHANNELS,
           ROTT64_FX_CHANNELS - 1,
           ROTT64_MUSIC_CHANNEL,
           ROTT64_MUSIC_STEREO_SUBCHANNEL);
    return 1;
}

void rott64_audio_shutdown(void)
{
    if (!rott64_audio_ready)
        return;

    mixer_close();
    audio_close();
    rott64_audio_ready = 0;
}

void rott64_audio_pump(void)
{
    int guard = 4;

    if (!rott64_audio_ready)
        return;

    while (guard-- > 0 && audio_can_write())
    {
        short *buffer = audio_write_begin();
        if (buffer == NULL)
            break;

        mixer_poll(buffer, audio_get_buffer_length());
        audio_write_end();
    }
}

void rott64_audio_play_channel_checked(int ch, waveform_t *wave,
                                       const char *file, int line)
{
    int mapped;

    if (wave == NULL)
        return;

    if (!rott64_audio_init_once())
        return;

    mapped = rott64_audio_normalize_channel(
        ch, rott64_audio_wave_channels(wave), "play", file, line);

    if (mapped < 0)
        return;

    mixer_ch_play(mapped, wave);
}

void rott64_audio_stop_channel_checked(int ch, const char *file, int line)
{
    int mapped;

    if (!rott64_audio_ready)
        return;

    mapped = rott64_audio_normalize_channel(ch, 1, "stop", file, line);
    if (mapped < 0)
        return;

    mixer_ch_stop(mapped);
}

int rott64_audio_channel_playing_checked(int ch, const char *file, int line)
{
    int mapped;

    if (!rott64_audio_ready)
        return 0;

    mapped = rott64_audio_normalize_channel(ch, 1, "playing", file, line);
    if (mapped < 0)
        return 0;

    return mixer_ch_playing(mapped) ? 1 : 0;
}

void rott64_audio_set_channel_vol_checked(int ch, float lvol, float rvol,
                                          const char *file, int line)
{
    int mapped;

    if (!rott64_audio_init_once())
        return;

    mapped = rott64_audio_normalize_channel(ch, 1, "set_vol", file, line);
    if (mapped < 0)
        return;

    mixer_ch_set_vol(mapped, lvol, rvol);
}

void rott64_audio_set_channel_vol_pan_checked(int ch, float vol, float pan,
                                              const char *file, int line)
{
    int mapped;

    if (!rott64_audio_init_once())
        return;

    mapped = rott64_audio_normalize_channel(ch, 1, "set_vol_pan", file, line);
    if (mapped < 0)
        return;

    mixer_ch_set_vol_pan(mapped, vol, pan);
}

void rott64_audio_set_channel_freq_checked(int ch, float frequency,
                                           const char *file, int line)
{
    int mapped;

    if (!rott64_audio_init_once())
        return;

    mapped = rott64_audio_normalize_channel(ch, 1, "set_freq", file, line);
    if (mapped < 0)
        return;

    mixer_ch_set_freq(mapped, frequency);
}

#else

int rott64_audio_init_once(void) { return 1; }
void rott64_audio_shutdown(void) {}
void rott64_audio_pump(void) {}

void rott64_audio_play_channel_checked(int ch, waveform_t *wave,
                                       const char *file, int line)
{
    (void)ch;
    (void)wave;
    (void)file;
    (void)line;
}

void rott64_audio_stop_channel_checked(int ch, const char *file, int line)
{
    (void)ch;
    (void)file;
    (void)line;
}

int rott64_audio_channel_playing_checked(int ch, const char *file, int line)
{
    (void)ch;
    (void)file;
    (void)line;
    return 0;
}

void rott64_audio_set_channel_vol_checked(int ch, float lvol, float rvol,
                                          const char *file, int line)
{
    (void)ch;
    (void)lvol;
    (void)rvol;
    (void)file;
    (void)line;
}

void rott64_audio_set_channel_vol_pan_checked(int ch, float vol, float pan,
                                              const char *file, int line)
{
    (void)ch;
    (void)vol;
    (void)pan;
    (void)file;
    (void)line;
}

void rott64_audio_set_channel_freq_checked(int ch, float frequency,
                                           const char *file, int line)
{
    (void)ch;
    (void)frequency;
    (void)file;
    (void)line;
}

#endif
