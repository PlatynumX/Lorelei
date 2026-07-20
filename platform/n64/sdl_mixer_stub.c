#include "SDL_mixer.h"
#include "rott64_audio.h"
#include "n64_platform.h"

#include <stdbool.h>
#include <math.h>
#include <stdlib.h>
#include <string.h>

#ifdef __N64__
#include <libdragon.h>
#endif

#define VOC_SIGNATURE "Creative Voice File\x1a"
#define VOC_SIGNATURE_LEN 20u

static int opened;
static int output_frequency = MIX_DEFAULT_FREQUENCY;
static int channel_count = ROTT64_FX_CHANNELS;
static int master_volume = MIX_MAX_VOLUME;
static int music_volume = MIX_MAX_VOLUME;
static int channel_volume[ROTT64_FX_CHANNELS];
static Uint8 channel_left[ROTT64_FX_CHANNELS];
static Uint8 channel_right[ROTT64_FX_CHANNELS];
static Mix_Chunk *channel_chunk[ROTT64_FX_CHANNELS];
static void (*finished_callback)(int);

#ifdef __N64__
typedef struct {
    waveform_t wave;
} rott64_chunk_backend_t;
#endif

static Uint16 read_le16(const Uint8 *p)
{
    return (Uint16)((Uint16)p[0] | ((Uint16)p[1] << 8));
}

static Uint32 read_le24(const Uint8 *p)
{
    return (Uint32)p[0] | ((Uint32)p[1] << 8) | ((Uint32)p[2] << 16);
}

static Uint32 read_le32(const Uint8 *p)
{
    return (Uint32)p[0] | ((Uint32)p[1] << 8) | ((Uint32)p[2] << 16)
        | ((Uint32)p[3] << 24);
}

static int append_pcm(Uint8 **pcm, size_t *length, size_t *capacity,
                      const Uint8 *source, size_t count)
{
    size_t needed;
    Uint8 *resized;

    if (count == 0u) {
        return 0;
    }
    if (*length > SIZE_MAX - count) {
        return -1;
    }
    needed = *length + count;
    if (needed > *capacity) {
        size_t next = *capacity ? *capacity : 4096u;
        while (next < needed) {
            if (next > SIZE_MAX / 2u) {
                next = needed;
                break;
            }
            next *= 2u;
        }
        resized = realloc(*pcm, next);
        if (resized == NULL) {
            return -1;
        }
        *pcm = resized;
        *capacity = next;
    }

    /* Creative VOC PCM is unsigned 8-bit. Libdragon's 8-bit waveform path
       expects signed PCM, so flip the sign bit while copying. */
    for (size_t i = 0; i < count; ++i) {
        (*pcm)[*length + i] = (Uint8)(source[i] ^ 0x80u);
    }
    *length = needed;
    return 0;
}

static Mix_Chunk *decode_voc(const Uint8 *data, size_t size)
{
    size_t pos;
    size_t pcm_length = 0u;
    size_t pcm_capacity = 0u;
    Uint8 *pcm = NULL;
    Uint32 sample_rate = 0u;
    Mix_Chunk *chunk = NULL;

    if (data == NULL || size < 26u
        || memcmp(data, VOC_SIGNATURE, VOC_SIGNATURE_LEN) != 0) {
        SDL_SetError("unsupported sound lump (expected Creative VOC)");
        return NULL;
    }

    pos = read_le16(data + 20u);
    if (pos < 26u || pos >= size) {
        SDL_SetError("invalid VOC header offset");
        return NULL;
    }

    while (pos < size) {
        Uint8 block_type = data[pos++];
        Uint32 block_length;
        const Uint8 *payload;

        if (block_type == 0u) {
            break;
        }
        if (pos + 3u > size) {
            SDL_SetError("truncated VOC block header");
            goto fail;
        }
        block_length = read_le24(data + pos);
        pos += 3u;
        if ((size_t)block_length > size - pos) {
            SDL_SetError("truncated VOC block payload");
            goto fail;
        }
        payload = data + pos;

        switch (block_type) {
            case 1u: /* Sound data: time constant, codec, unsigned 8-bit PCM. */
                if (block_length < 2u || payload[1] != 0u) {
                    SDL_SetError("unsupported VOC type-1 codec");
                    goto fail;
                }
                {
                    Uint32 rate = 1000000u / (256u - (Uint32)payload[0]);
                    if (sample_rate != 0u && sample_rate != rate) {
                        SDL_SetError("VOC sample rate changes are unsupported");
                        goto fail;
                    }
                    sample_rate = rate;
                }
                if (append_pcm(&pcm, &pcm_length, &pcm_capacity,
                               payload + 2u, (size_t)block_length - 2u) != 0) {
                    SDL_SetError("out of memory decoding VOC");
                    goto fail;
                }
                break;

            case 2u: /* Continuation of previous 8-bit PCM block. */
                if (sample_rate == 0u) {
                    SDL_SetError("VOC continuation without a sound block");
                    goto fail;
                }
                if (append_pcm(&pcm, &pcm_length, &pcm_capacity,
                               payload, block_length) != 0) {
                    SDL_SetError("out of memory decoding VOC continuation");
                    goto fail;
                }
                break;

            case 6u: /* Repeat start. ROTT has one looping missile sound.
                        First audio milestone decodes one pass only. */
            case 7u: /* Repeat end. */
                break;

            case 9u: /* New sound data block. */
                if (block_length < 12u) {
                    SDL_SetError("truncated VOC type-9 block");
                    goto fail;
                }
                {
                    Uint32 rate = read_le32(payload);
                    Uint8 bits = payload[4];
                    Uint8 channels = payload[5];
                    Uint16 codec = read_le16(payload + 6u);
                    if (rate == 0u || bits != 8u || channels != 1u || codec != 0u) {
                        SDL_SetError("unsupported VOC type-9 format");
                        goto fail;
                    }
                    if (sample_rate != 0u && sample_rate != rate) {
                        SDL_SetError("VOC sample rate changes are unsupported");
                        goto fail;
                    }
                    sample_rate = rate;
                }
                if (append_pcm(&pcm, &pcm_length, &pcm_capacity,
                               payload + 12u, (size_t)block_length - 12u) != 0) {
                    SDL_SetError("out of memory decoding VOC type-9 data");
                    goto fail;
                }
                break;

            default:
                /* Metadata/silence blocks are not present in the shareware
                   DIGISTRT..DIGISTOP bank. Ignore unknown non-audio blocks so
                   a harmless marker does not kill all sound initialization. */
                break;
        }

        pos += block_length;
    }

    if (pcm_length == 0u || sample_rate == 0u || pcm_length > UINT32_MAX) {
        SDL_SetError("VOC contains no supported PCM data");
        goto fail;
    }

    chunk = calloc(1u, sizeof(*chunk));
    if (chunk == NULL) {
        SDL_SetError("out of memory allocating sound chunk");
        goto fail;
    }
    chunk->allocated = 1;
    chunk->abuf = pcm;
    chunk->alen = (Uint32)pcm_length;
    chunk->volume = MIX_MAX_VOLUME;
    chunk->frequency = sample_rate;
    chunk->channels = 1u;
    chunk->bits = 8u;

#ifdef __N64__
    {
        rott64_chunk_backend_t *backend = calloc(1u, sizeof(*backend));
        if (backend == NULL) {
            SDL_SetError("out of memory allocating N64 waveform");
            free(chunk->abuf);
            free(chunk);
            return NULL;
        }
        chunk->backend = backend;
    }
#endif

    return chunk;

fail:
    free(pcm);
    return NULL;
}

#ifdef __N64__
static void chunk_waveform_read(void *ctx, samplebuffer_t *sbuf,
                                int wpos, int wlen, bool seeking)
{
    Mix_Chunk *chunk = ctx;
    Uint8 *out;
    int available = 0;

    (void)seeking;
    if (wlen <= 0) {
        return;
    }

    out = samplebuffer_append(sbuf, wlen);
    if (wpos >= 0 && (Uint32)wpos < chunk->alen) {
        Uint32 remain = chunk->alen - (Uint32)wpos;
        available = remain < (Uint32)wlen ? (int)remain : wlen;
        memcpy(out, chunk->abuf + wpos, (size_t)available);
    }
    if (available < wlen) {
        memset(out + available, 0, (size_t)(wlen - available));
    }
}

static void setup_waveform(Mix_Chunk *chunk)
{
    rott64_chunk_backend_t *backend = chunk ? chunk->backend : NULL;
    if (backend == NULL) {
        return;
    }
    backend->wave.name = "ROTT VOC";
    backend->wave.bits = chunk->bits;
    backend->wave.channels = chunk->channels;
    backend->wave.frequency = (float)chunk->frequency;
    backend->wave.len = (int)chunk->alen;
    backend->wave.loop_len = 0;
    backend->wave.read = chunk_waveform_read;
    backend->wave.ctx = chunk;
}

static void apply_channel_mix(int channel)
{
    Mix_Chunk *chunk;
    float base;
    float left;
    float right;

    if (channel < 0 || channel >= channel_count) {
        return;
    }
    chunk = channel_chunk[channel];
    base = (float)channel_volume[channel] / (float)MIX_MAX_VOLUME;
    base *= (float)master_volume / (float)MIX_MAX_VOLUME;
    if (chunk != NULL) {
        base *= (float)chunk->volume / (float)MIX_MAX_VOLUME;
    }
    left = base * ((float)channel_left[channel] / 255.0f);
    right = base * ((float)channel_right[channel] / 255.0f);

    /* Taradino's positional mixer can request near-field sounds at almost
       full gain in both stereo channels.  On libdragon that can produce a
       hotter-than-unity stereo vector, making immediately-nearby effects
       distort or behave harshly while distant/panned sounds remain fine.
       Preserve the requested pan direction and overall base volume, but
       normalize only vectors whose combined power exceeds unity. */
    {
        float power = left * left + right * right;
        if (power > 1.0f) {
            float inv = 1.0f / sqrtf(power);
            left *= inv;
            right *= inv;
        }
    }

    mixer_ch_set_vol(channel, left, right);
}
#endif

void rott64_mixer_pump(void)
{
#ifdef __N64__
    if (!opened) {
        return;
    }
    while (audio_can_write()) {
        short *buffer = audio_write_begin();
        mixer_poll(buffer, audio_get_buffer_length());
        audio_write_end();
    }

    for (int i = 0; i < channel_count; ++i) {
        if (channel_chunk[i] != NULL && !mixer_ch_playing(i)) {
            channel_chunk[i] = NULL;
            if (finished_callback != NULL) {
                finished_callback(i);
            }
        }
    }
#endif
}

int Mix_OpenAudioDevice(int frequency, Uint16 format, int channels, int chunksize,
                        const char *device, int allowed_changes)
{
    (void)device;
    (void)allowed_changes;
    return Mix_OpenAudio(frequency, format, channels, chunksize);
}

int Mix_MasterVolume(int volume)
{
    int old = master_volume;
    if (volume >= 0) {
        if (volume > MIX_MAX_VOLUME) volume = MIX_MAX_VOLUME;
        master_volume = volume;
#ifdef __N64__
        if (opened) {
            for (int i = 0; i < channel_count; ++i) {
                apply_channel_mix(i);
            }
        }
#endif
    }
    return old;
}

int Mix_OpenAudio(int frequency, Uint16 format, int channels, int chunksize)
{
    (void)chunksize;
    if (channels != 2 || SDL_AUDIO_BITSIZE(format) != 16 || !SDL_AUDIO_ISSIGNED(format)) {
        return SDL_SetError("ROTT64 audio output requires signed 16-bit stereo");
    }
    if (opened) {
        return 0;
    }

    output_frequency = frequency > 0 ? frequency : 44100;
    channel_count = ROTT64_FX_CHANNELS;
    for (int i = 0; i < ROTT64_FX_CHANNELS; ++i) {
        channel_volume[i] = MIX_MAX_VOLUME;
        channel_left[i] = 255u;
        channel_right[i] = 255u;
        channel_chunk[i] = NULL;
    }

#ifdef __N64__
    audio_init(output_frequency, 4);
    output_frequency = audio_get_frequency();
    mixer_init(ROTT64_MIXER_CHANNELS);
    mixer_set_vol(1.0f);
#endif

    opened = 1;
    rott64_mixer_pump();
    return 0;
}

void Mix_CloseAudio(void)
{
    if (!opened) {
        return;
    }
#ifdef __N64__
    for (int i = 0; i < ROTT64_MIXER_CHANNELS; ++i) {
        mixer_ch_stop(i);
        if (i < channel_count) {
            channel_chunk[i] = NULL;
        }
    }
    mixer_close();
    audio_close();
#endif
    opened = 0;
}

int Mix_QuerySpec(int *frequency, Uint16 *format, int *channels)
{
    if (!opened) return 0;
    if (frequency) *frequency = output_frequency;
    if (format) *format = AUDIO_S16SYS;
    if (channels) *channels = 2;
    return 1;
}

int Mix_AllocateChannels(int numchans)
{
    if (numchans >= 0) {
        if (numchans > ROTT64_FX_CHANNELS) {
            numchans = ROTT64_FX_CHANNELS;
        }
        channel_count = numchans;
    }
    return channel_count;
}

void Mix_ChannelFinished(void (*callback)(int))
{
    finished_callback = callback;
}

Mix_Chunk *Mix_LoadWAV_RW(SDL_RWops *src, int freesrc)
{
    Sint64 rw_size;
    Uint8 *encoded = NULL;
    Mix_Chunk *chunk = NULL;

    if (src == NULL) {
        SDL_SetError("Mix_LoadWAV_RW: NULL source");
        return NULL;
    }
    rw_size = SDL_RWsize(src);
    if (rw_size <= 0 || (Uint64)rw_size > SIZE_MAX) {
        SDL_SetError("Mix_LoadWAV_RW: invalid source size");
        goto done;
    }

    encoded = malloc((size_t)rw_size);
    if (encoded == NULL) {
        SDL_SetError("Mix_LoadWAV_RW: out of memory");
        goto done;
    }
    if (SDL_RWseek(src, 0, SEEK_SET) < 0
        || SDL_RWread(src, encoded, 1u, (size_t)rw_size) != (size_t)rw_size) {
        SDL_SetError("Mix_LoadWAV_RW: could not read source");
        goto done;
    }

    chunk = decode_voc(encoded, (size_t)rw_size);
#ifdef __N64__
    if (chunk != NULL) {
        setup_waveform(chunk);
    }
#endif

done:
    free(encoded);
    if (freesrc) {
        SDL_RWclose(src);
    }
    return chunk;
}

void Mix_FreeChunk(Mix_Chunk *chunk)
{
    if (chunk == NULL) {
        return;
    }
#ifdef __N64__
    for (int i = 0; i < channel_count; ++i) {
        if (channel_chunk[i] == chunk) {
            mixer_ch_stop(i);
            channel_chunk[i] = NULL;
        }
    }
    free(chunk->backend);
#endif
    if (chunk->allocated) {
        free(chunk->abuf);
    }
    free(chunk);
}

int Mix_PlayChannelTimed(int channel, Mix_Chunk *chunk, int loops, int ticks)
{
    (void)ticks;
    if (!opened || chunk == NULL || loops != 0) {
        return -1;
    }

    if (channel < 0) {
        for (int i = 0; i < channel_count; ++i) {
#ifdef __N64__
            if (!mixer_ch_playing(i)) {
                channel = i;
                break;
            }
#else
            if (channel_chunk[i] == NULL) {
                channel = i;
                break;
            }
#endif
        }
    }
    if (channel < 0 || channel >= channel_count) {
        return -1;
    }

#ifdef __N64__
    {
        rott64_chunk_backend_t *backend = chunk->backend;
        if (backend == NULL) {
            return -1;
        }
        mixer_ch_play(channel, &backend->wave);
    }
#endif
    channel_chunk[channel] = chunk;
#ifdef __N64__
    apply_channel_mix(channel);
#endif
    return channel;
}

int Mix_HaltChannel(int channel)
{
    if (channel == -1) {
        for (int i = 0; i < channel_count; ++i) {
            (void)Mix_HaltChannel(i);
        }
        return 0;
    }
    if (channel < 0 || channel >= channel_count) {
        return -1;
    }
#ifdef __N64__
    mixer_ch_stop(channel);
#endif
    if (channel_chunk[channel] != NULL) {
        channel_chunk[channel] = NULL;
        if (finished_callback != NULL) {
            finished_callback(channel);
        }
    }
    return 0;
}

int Mix_Playing(int channel)
{
    rott64_mixer_pump();
    if (channel == -1) {
        int count = 0;
        for (int i = 0; i < channel_count; ++i) {
#ifdef __N64__
            if (mixer_ch_playing(i)) ++count;
#else
            if (channel_chunk[i] != NULL) ++count;
#endif
        }
        return count;
    }
    if (channel < 0 || channel >= channel_count) {
        return 0;
    }
#ifdef __N64__
    return mixer_ch_playing(channel) ? 1 : 0;
#else
    return channel_chunk[channel] != NULL ? 1 : 0;
#endif
}

int Mix_Volume(int channel, int volume)
{
    if (channel == -1) {
        int previous = channel_count > 0 ? channel_volume[0] : 0;
        if (volume >= 0) {
            for (int i = 0; i < channel_count; ++i) {
                (void)Mix_Volume(i, volume);
            }
        }
        return previous;
    }
    if (channel < 0 || channel >= channel_count) {
        return 0;
    }
    {
        int old = channel_volume[channel];
        if (volume >= 0) {
            if (volume > MIX_MAX_VOLUME) volume = MIX_MAX_VOLUME;
            channel_volume[channel] = volume;
#ifdef __N64__
            apply_channel_mix(channel);
#endif
        }
        return old;
    }
}

int Mix_VolumeChunk(Mix_Chunk *chunk, int volume)
{
    int old = chunk ? chunk->volume : 0;
    if (chunk != NULL && volume >= 0) {
        if (volume > MIX_MAX_VOLUME) volume = MIX_MAX_VOLUME;
        chunk->volume = (Uint8)volume;
#ifdef __N64__
        for (int i = 0; i < channel_count; ++i) {
            if (channel_chunk[i] == chunk) {
                apply_channel_mix(i);
            }
        }
#endif
    }
    return old;
}

int Mix_SetPanning(int channel, Uint8 left, Uint8 right)
{
    if (channel < 0 || channel >= channel_count) {
        return 0;
    }
    channel_left[channel] = left;
    channel_right[channel] = right;
#ifdef __N64__
    apply_channel_mix(channel);

    /* Taradino applies 3D panning after starting a voice. A loud sound that
       is nearly centered is generally at or very near the player: weapon
       impacts, incoming damage, explosions, doors, etc. Give those events a
       brief tactile accent. This deliberately stays below the explicit fire
       recoil strength and is non-blocking. */
    if (channel_chunk[channel] != NULL && mixer_ch_playing(channel)) {
        unsigned total = (unsigned)left + (unsigned)right;
        unsigned spread = left > right ? (unsigned)(left - right) : (unsigned)(right - left);
        if (total >= 390u && spread <= 48u) {
            n64_platform_rumble_pulse(48u, 145u);
        }
    }
#endif
    return 1;
}

void Mix_Pause(int channel) { (void)channel; }
void Mix_Resume(int channel) { (void)channel; }
const char *Mix_GetError(void) { return SDL_GetError(); }

/* Music remains intentionally silent in this milestone. */
void Mix_HookMusic(void (*mix_func)(void *, Uint8 *, int), void *arg)
{
    (void)mix_func;
    (void)arg;
}
void Mix_HaltMusic(void) { }
int Mix_PlayingMusic(void) { return 0; }
void Mix_PauseMusic(void) { }
void Mix_ResumeMusic(void) { }
int Mix_VolumeMusic(int volume)
{
    int old = music_volume;
    if (volume >= 0) music_volume = volume;
    return old;
}
