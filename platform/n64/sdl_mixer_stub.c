/* ROTT64_R90_SDL_MIXER_USES_AUDIO_CONTRACT
 *
 * SDL_mixer compatibility for Taradino routed through the shared ROTT64
 * libdragon audio contract.  This is intentionally not a silent diagnostic:
 * Mix_* calls decode VOC chunks and play them on FX channels 0..7, while the
 * generated music path uses the reserved music channel pair 8/9.
 */

#include "SDL_mixer.h"
#include "rott64_audio.h"

#include <limits.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef __N64__
#include <samplebuffer.h>
#endif

#define VOC_SIGNATURE "Creative Voice File\x1a"
#define VOC_SIGNATURE_LEN 20u
#define ROTT64_SDL_CHANNELS ROTT64_FX_CHANNELS

static int opened;
static int output_frequency = MIX_DEFAULT_FREQUENCY;
static int channel_count = ROTT64_SDL_CHANNELS;
static int master_volume = MIX_MAX_VOLUME;
static int music_volume = MIX_MAX_VOLUME;
static int channel_volume[ROTT64_SDL_CHANNELS];
static Mix_Chunk *last_chunk[ROTT64_SDL_CHANNELS];
static void (*finished_callback)(int);

#ifdef __N64__
typedef struct rott64_chunk_wave_s
{
    waveform_t wave;
    Mix_Chunk *chunk;
} rott64_chunk_wave_t;

static void rott64_chunk_wave_read(void *ctx, samplebuffer_t *sbuf,
                                   int wpos, int wlen, bool seeking)
{
    rott64_chunk_wave_t *backend = (rott64_chunk_wave_t *)ctx;
    Mix_Chunk *chunk = backend ? backend->chunk : NULL;
    int available = 0;
    int copy = 0;
    int8_t *dest;

    (void)seeking;

    if (wlen <= 0)
        return;

    dest = (int8_t *)samplebuffer_append(sbuf, wlen);
    if (dest == NULL)
        return;

    if (chunk != NULL && chunk->abuf != NULL && wpos < (int)chunk->alen)
    {
        available = (int)chunk->alen - wpos;
        copy = available < wlen ? available : wlen;
        if (copy > 0)
            memcpy(dest, chunk->abuf + wpos, (size_t)copy);
    }

    if (copy < wlen)
        memset(dest + copy, 0, (size_t)(wlen - copy));
}

static int rott64_chunk_make_backend(Mix_Chunk *chunk)
{
    rott64_chunk_wave_t *backend;

    if (chunk == NULL)
        return -1;

    backend = (rott64_chunk_wave_t *)calloc(1u, sizeof(*backend));
    if (backend == NULL)
        return SDL_SetError("out of memory allocating N64 waveform backend");

    backend->chunk = chunk;
    backend->wave.name = "ROTT64 VOC";
    backend->wave.bits = chunk->bits ? chunk->bits : 8u;
    backend->wave.channels = chunk->channels ? chunk->channels : 1u;
    backend->wave.frequency = chunk->frequency ? (float)chunk->frequency
                                               : (float)MIX_DEFAULT_FREQUENCY;
    backend->wave.len = (int)chunk->alen;
    backend->wave.loop_len = 0;
    backend->wave.start = NULL;
    backend->wave.read = rott64_chunk_wave_read;
    backend->wave.ctx = backend;
    backend->wave.state_size = 0;

    chunk->backend = backend;
    return 0;
}
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
    return (Uint32)p[0]
        | ((Uint32)p[1] << 8)
        | ((Uint32)p[2] << 16)
        | ((Uint32)p[3] << 24);
}

static int append_pcm(Uint8 **pcm, size_t *length, size_t *capacity,
                      const Uint8 *source, size_t count)
{
    size_t needed;
    Uint8 *resized;

    if (count == 0u)
        return 0;

    if (*length > SIZE_MAX - count)
        return -1;

    needed = *length + count;
    if (needed > *capacity)
    {
        size_t next = *capacity ? *capacity : 4096u;

        while (next < needed)
        {
            if (next > SIZE_MAX / 2u)
            {
                next = needed;
                break;
            }
            next *= 2u;
        }

        resized = (Uint8 *)realloc(*pcm, next);
        if (resized == NULL)
            return -1;

        *pcm = resized;
        *capacity = next;
    }

    /* Creative VOC PCM is unsigned 8-bit. libdragon waveforms expect signed. */
    for (size_t i = 0; i < count; ++i)
        (*pcm)[*length + i] = (Uint8)(source[i] ^ 0x80u);

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
        || memcmp(data, VOC_SIGNATURE, VOC_SIGNATURE_LEN) != 0)
    {
        SDL_SetError("unsupported sound lump (expected Creative VOC)");
        return NULL;
    }

    pos = read_le16(data + 20u);
    if (pos < 26u || pos >= size)
    {
        SDL_SetError("invalid VOC header offset");
        return NULL;
    }

    while (pos < size)
    {
        Uint8 block_type = data[pos++];
        Uint32 block_length;
        const Uint8 *payload;

        if (block_type == 0u)
            break;

        if (pos + 3u > size)
        {
            SDL_SetError("truncated VOC block header");
            goto fail;
        }

        block_length = read_le24(data + pos);
        pos += 3u;

        if ((size_t)block_length > size - pos)
        {
            SDL_SetError("truncated VOC block payload");
            goto fail;
        }

        payload = data + pos;

        switch (block_type)
        {
            case 1u:
                if (block_length < 2u || payload[1] != 0u)
                {
                    SDL_SetError("unsupported VOC type-1 codec");
                    goto fail;
                }
                {
                    Uint32 rate = 1000000u / (256u - (Uint32)payload[0]);
                    if (sample_rate != 0u && sample_rate != rate)
                    {
                        SDL_SetError("VOC sample rate changes are unsupported");
                        goto fail;
                    }
                    sample_rate = rate;
                }
                if (append_pcm(&pcm, &pcm_length, &pcm_capacity,
                               payload + 2u, (size_t)block_length - 2u) != 0)
                {
                    SDL_SetError("out of memory decoding VOC");
                    goto fail;
                }
                break;

            case 2u:
                if (sample_rate == 0u)
                {
                    SDL_SetError("VOC continuation without a sound block");
                    goto fail;
                }
                if (append_pcm(&pcm, &pcm_length, &pcm_capacity,
                               payload, block_length) != 0)
                {
                    SDL_SetError("out of memory decoding VOC continuation");
                    goto fail;
                }
                break;

            case 6u:
            case 7u:
                break;

            case 9u:
                if (block_length < 12u)
                {
                    SDL_SetError("truncated VOC type-9 block");
                    goto fail;
                }
                {
                    Uint32 rate = read_le32(payload);
                    Uint8 bits = payload[4];
                    Uint8 channels = payload[5];
                    Uint16 codec = read_le16(payload + 6u);

                    if (rate == 0u || bits != 8u || channels != 1u || codec != 0u)
                    {
                        SDL_SetError("unsupported VOC type-9 format");
                        goto fail;
                    }

                    if (sample_rate != 0u && sample_rate != rate)
                    {
                        SDL_SetError("VOC sample rate changes are unsupported");
                        goto fail;
                    }

                    sample_rate = rate;
                }
                if (append_pcm(&pcm, &pcm_length, &pcm_capacity,
                               payload + 12u, (size_t)block_length - 12u) != 0)
                {
                    SDL_SetError("out of memory decoding VOC type-9 data");
                    goto fail;
                }
                break;

            default:
                break;
        }

        pos += block_length;
    }

    if (pcm_length == 0u || sample_rate == 0u || pcm_length > UINT32_MAX)
    {
        SDL_SetError("VOC contains no supported PCM data");
        goto fail;
    }

    chunk = (Mix_Chunk *)calloc(1u, sizeof(*chunk));
    if (chunk == NULL)
    {
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
    if (rott64_chunk_make_backend(chunk) != 0)
        goto fail_chunk;
#endif

    return chunk;

#ifdef __N64__
fail_chunk:
    free(chunk);
#endif
fail:
    free(pcm);
    return NULL;
}

void rott64_mixer_pump(void)
{
    rott64_audio_pump();
}

int Mix_OpenAudio(int frequency, Uint16 format, int channels, int chunksize)
{
    (void)chunksize;

    if (channels != 2 || SDL_AUDIO_BITSIZE(format) != 16
        || !SDL_AUDIO_ISSIGNED(format))
    {
        return SDL_SetError("ROTT64 audio output requires signed 16-bit stereo");
    }

    output_frequency = frequency > 0 ? frequency : MIX_DEFAULT_FREQUENCY;
    opened = 1;

    for (int i = 0; i < ROTT64_SDL_CHANNELS; ++i)
    {
        channel_volume[i] = MIX_MAX_VOLUME;
        last_chunk[i] = NULL;
    }

#ifdef __N64__
    if (!rott64_audio_init_once())
        return SDL_SetError("ROTT64 audio initialization failed");
#endif

    return 0;
}

int Mix_OpenAudioDevice(int frequency, Uint16 format, int channels,
                        int chunksize, const char *device, int allowed_changes)
{
    (void)device;
    (void)allowed_changes;
    return Mix_OpenAudio(frequency, format, channels, chunksize);
}

int Mix_MasterVolume(int volume)
{
    int old = master_volume;

    if (volume >= 0)
    {
        if (volume > MIX_MAX_VOLUME)
            volume = MIX_MAX_VOLUME;
        master_volume = volume;
#ifdef __N64__
        rott64_audio_init_once();
#endif
    }

    return old;
}

void Mix_CloseAudio(void)
{
    for (int i = 0; i < ROTT64_SDL_CHANNELS; ++i)
        last_chunk[i] = NULL;

    opened = 0;
}

int Mix_QuerySpec(int *frequency, Uint16 *format, int *channels)
{
    if (!opened)
        return 0;

    if (frequency != NULL)
        *frequency = output_frequency;
    if (format != NULL)
        *format = AUDIO_S16SYS;
    if (channels != NULL)
        *channels = 2;

    return 1;
}

int Mix_AllocateChannels(int numchans)
{
    if (numchans >= 0)
    {
        if (numchans > ROTT64_SDL_CHANNELS)
            numchans = ROTT64_SDL_CHANNELS;
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

    if (src == NULL)
    {
        SDL_SetError("Mix_LoadWAV_RW: NULL source");
        return NULL;
    }

    rw_size = SDL_RWsize(src);
    if (rw_size <= 0 || (Uint64)rw_size > SIZE_MAX)
    {
        SDL_SetError("Mix_LoadWAV_RW: invalid source size");
        goto done;
    }

    encoded = (Uint8 *)malloc((size_t)rw_size);
    if (encoded == NULL)
    {
        SDL_SetError("Mix_LoadWAV_RW: out of memory");
        goto done;
    }

    if (SDL_RWseek(src, 0, SEEK_SET) < 0
        || SDL_RWread(src, encoded, 1u, (size_t)rw_size) != (size_t)rw_size)
    {
        SDL_SetError("Mix_LoadWAV_RW: could not read source");
        goto done;
    }

    chunk = decode_voc(encoded, (size_t)rw_size);

done:
    free(encoded);
    if (freesrc)
        SDL_RWclose(src);
    return chunk;
}

void Mix_FreeChunk(Mix_Chunk *chunk)
{
    if (chunk == NULL)
        return;

    for (int i = 0; i < ROTT64_SDL_CHANNELS; ++i)
    {
        if (last_chunk[i] == chunk)
            last_chunk[i] = NULL;
    }

#ifdef __N64__
    free(chunk->backend);
#endif
    if (chunk->allocated)
        free(chunk->abuf);
    free(chunk);
}

int Mix_PlayChannelTimed(int channel, Mix_Chunk *chunk, int loops, int ticks)
{
    int chosen = channel;

    (void)ticks;

    if (!opened || chunk == NULL || loops != 0)
        return -1;

    if (chosen < 0)
        chosen = 0;

    if (chosen >= channel_count)
        return -1;

#ifdef __N64__
    if (chunk->backend != NULL)
    {
        rott64_chunk_wave_t *backend = (rott64_chunk_wave_t *)chunk->backend;
        rott64_audio_play_channel_checked(chosen, &backend->wave, __FILE__, __LINE__);
        rott64_audio_set_channel_vol_pan_checked(
            chosen,
            (float)chunk->volume / (float)MIX_MAX_VOLUME,
            0.5f,
            __FILE__,
            __LINE__);
    }
#endif

    last_chunk[chosen] = chunk;
    return chosen;
}

int Mix_HaltChannel(int channel)
{
    if (channel == -1)
    {
        for (int i = 0; i < channel_count; ++i)
            (void)Mix_HaltChannel(i);
        return 0;
    }

    if (channel < 0 || channel >= channel_count)
        return -1;

#ifdef __N64__
    rott64_audio_stop_channel_checked(channel, __FILE__, __LINE__);
#endif
    last_chunk[channel] = NULL;

    if (finished_callback != NULL)
        finished_callback(channel);

    return 0;
}

int Mix_Playing(int channel)
{
    if (channel == -1)
    {
        int count = 0;
        for (int i = 0; i < channel_count; ++i)
            count += Mix_Playing(i) ? 1 : 0;
        return count;
    }

    if (channel < 0 || channel >= channel_count)
        return 0;

#ifdef __N64__
    if (last_chunk[channel] != NULL
        && rott64_audio_channel_playing_checked(channel, __FILE__, __LINE__))
    {
        return 1;
    }
    last_chunk[channel] = NULL;
    return 0;
#else
    return last_chunk[channel] != NULL ? 1 : 0;
#endif
}

int Mix_Volume(int channel, int volume)
{
    if (channel == -1)
    {
        int previous = channel_count > 0 ? channel_volume[0] : 0;

        if (volume >= 0)
        {
            for (int i = 0; i < channel_count; ++i)
                channel_volume[i] = volume > MIX_MAX_VOLUME ? MIX_MAX_VOLUME : volume;
        }

        return previous;
    }

    if (channel < 0 || channel >= channel_count)
        return 0;

    {
        int old = channel_volume[channel];
        if (volume >= 0)
            channel_volume[channel] = volume > MIX_MAX_VOLUME ? MIX_MAX_VOLUME : volume;
        return old;
    }
}

int Mix_VolumeChunk(Mix_Chunk *chunk, int volume)
{
    int old = chunk ? chunk->volume : 0;

    if (chunk != NULL && volume >= 0)
    {
        if (volume > MIX_MAX_VOLUME)
            volume = MIX_MAX_VOLUME;
        chunk->volume = (Uint8)volume;
    }

    return old;
}

int Mix_SetPanning(int channel, Uint8 left, Uint8 right)
{
    if (channel < 0 || channel >= channel_count)
        return 0;

#ifdef __N64__
    {
        float lvol = (float)left / 255.0f;
        float rvol = (float)right / 255.0f;
        rott64_audio_set_channel_vol_checked(channel, lvol, rvol, __FILE__, __LINE__);
    }
#else
    (void)left;
    (void)right;
#endif

    return 1;
}

void Mix_Pause(int channel)
{
    (void)channel;
}

void Mix_Resume(int channel)
{
    (void)channel;
}

const char *Mix_GetError(void)
{
    return SDL_GetError();
}

void Mix_HookMusic(void (*mix_func)(void *, Uint8 *, int), void *arg)
{
    (void)mix_func;
    (void)arg;
}

void Mix_HaltMusic(void)
{
#ifdef __N64__
    rott64_audio_stop_channel_checked(ROTT64_MUSIC_CHANNEL, __FILE__, __LINE__);
#endif
}

int Mix_PlayingMusic(void)
{
#ifdef __N64__
    return rott64_audio_channel_playing_checked(ROTT64_MUSIC_CHANNEL, __FILE__, __LINE__);
#else
    return 0;
#endif
}

void Mix_PauseMusic(void)
{
}

void Mix_ResumeMusic(void)
{
}

int Mix_VolumeMusic(int volume)
{
    int old = music_volume;

    if (volume >= 0)
    {
        music_volume = volume > MIX_MAX_VOLUME ? MIX_MAX_VOLUME : volume;
#ifdef __N64__
        rott64_audio_set_channel_vol_pan_checked(
            ROTT64_MUSIC_CHANNEL,
            (float)music_volume / (float)MIX_MAX_VOLUME,
            0.5f,
            __FILE__,
            __LINE__);
#endif
    }

    return old;
}
