/* ROTT64 streaming music backend.
 *
 * ROTT's MIDI lumps are rendered to mono WAV at build time and converted by
 * libdragon's audioconv64 to streaming WAV64/VADPCM files in DragonFS. At
 * runtime, Taradino still selects songs by its original MIDI lump. We match
 * that lump to the pre-rendered track using (size, CRC32).
 */
#include <stddef.h>
#include <stdint.h>
#include <string.h>

#include "SDL_mixer.h"
#include "music.h"
#include "rott64_audio.h"
#include "n64_music_map_generated.h"

#ifdef __N64__
#include <libdragon.h>
#endif

const int num_music_modules = 2;
unsigned char *music_songdata;
size_t music_songdatasize;
int music_loopflag = MUSIC_PlayOnce;
double float_music_volume;
char *soundfont_cfg;

/* These symbols are part of Taradino's public music API. ROTT64 implements
 * MUSIC_* directly, so the module structs are only compatibility exports. */
music_module_t sdl_music_module = {0};
music_module_t adl_music_module = {0};

#ifdef __N64__
static wav64_t current_wav;
#endif
static int current_open;
static int current_paused;
static float paused_sample_position;
static int current_volume = 255;

static uint32_t rott64_crc32(const unsigned char *data, size_t size)
{
    uint32_t crc = 0xFFFFFFFFu;
    for (size_t i = 0; i < size; ++i) {
        crc ^= data[i];
        for (int bit = 0; bit < 8; ++bit) {
            uint32_t mask = (uint32_t)-(int32_t)(crc & 1u);
            crc = (crc >> 1) ^ (0xEDB88320u & mask);
        }
    }
    return crc ^ 0xFFFFFFFFu;
}

static const rott64_music_map_entry_t *find_track(const unsigned char *song, int size)
{
    uint32_t crc;
    if (song == NULL || size <= 0) {
        return NULL;
    }
    crc = rott64_crc32(song, (size_t)size);
    for (size_t i = 0; i < rott64_music_map_count; ++i) {
        if (rott64_music_map[i].size == (uint32_t)size
            && rott64_music_map[i].crc32 == crc) {
            return &rott64_music_map[i];
        }
    }
    return NULL;
}

static void apply_music_volume(void)
{
#ifdef __N64__
    float volume = (float)current_volume / 255.0f;
    mixer_ch_set_vol(ROTT64_MUSIC_CHANNEL, volume, volume);
#endif
    float_music_volume = (double)current_volume / 255.0;
}

int MUSIC_Init(int mode)
{
    int frequency = 0;
    (void)mode;
    if (Mix_QuerySpec(&frequency, NULL, NULL) == 0) {
        SDL_SetError("ROTT64 music requires the libdragon mixer to be initialized first");
        return MUSIC_Error;
    }
    current_open = 0;
    current_paused = 0;
    paused_sample_position = 0.0f;
    apply_music_volume();
    return MUSIC_Ok;
}

int MUSIC_Shutdown(void)
{
    (void)MUSIC_StopSong();
    return MUSIC_Ok;
}

void MUSIC_SetVolume(int volume)
{
    if (volume < 0) volume = 0;
    if (volume > 255) volume = 255;
    current_volume = volume;
    apply_music_volume();
}

int MUSIC_SongPlaying(void)
{
    if (!current_open) {
        return __FX_FALSE;
    }
#ifdef __N64__
    return (current_paused || mixer_ch_playing(ROTT64_MUSIC_CHANNEL))
        ? __FX_TRUE : __FX_FALSE;
#else
    return current_paused ? __FX_TRUE : __FX_FALSE;
#endif
}

void MUSIC_Continue(void)
{
    if (!current_open || !current_paused) {
        return;
    }
#ifdef __N64__
    wav64_play(&current_wav, ROTT64_MUSIC_CHANNEL);
    mixer_ch_set_pos(ROTT64_MUSIC_CHANNEL, paused_sample_position);
#endif
    current_paused = 0;
    apply_music_volume();
}

void MUSIC_Pause(void)
{
    if (!current_open || current_paused) {
        return;
    }
#ifdef __N64__
    paused_sample_position = mixer_ch_get_pos(ROTT64_MUSIC_CHANNEL);
    mixer_ch_stop(ROTT64_MUSIC_CHANNEL);
#endif
    current_paused = 1;
}

int MUSIC_StopSong(void)
{
#ifdef __N64__
    if (current_open) {
        mixer_ch_stop(ROTT64_MUSIC_CHANNEL);
        wav64_close(&current_wav);
    }
#endif
    current_open = 0;
    current_paused = 0;
    paused_sample_position = 0.0f;
    music_songdata = NULL;
    music_songdatasize = 0u;
    music_loopflag = MUSIC_PlayOnce;
    return MUSIC_Ok;
}

int MUSIC_PlaySong(unsigned char *song, int size, int loopflag)
{
    const rott64_music_map_entry_t *track;
    (void)MUSIC_StopSong();

    track = find_track(song, size);
    if (track == NULL) {
        SDL_SetError("ROTT64 could not map MIDI lump to a rendered WAV64 track");
        return MUSIC_Error;
    }

    music_songdata = song;
    music_songdatasize = (size_t)size;
    music_loopflag = loopflag;
#ifdef __N64__
    wav64_open(&current_wav, track->path);
    wav64_set_loop(&current_wav, loopflag == MUSIC_LoopSong);
    wav64_play(&current_wav, ROTT64_MUSIC_CHANNEL);
#endif
    current_open = 1;
    current_paused = 0;
    paused_sample_position = 0.0f;
    apply_music_volume();
    return MUSIC_Ok;
}

void MUSIC_SetSongTime(unsigned long milliseconds)
{
    if (!current_open) {
        return;
    }
#ifdef __N64__
    {
        float position = ((float)milliseconds * current_wav.wave.frequency) / 1000.0f;
        if (position < 0.0f) position = 0.0f;
        if (current_wav.wave.len > 0 && position > (float)current_wav.wave.len) {
            position = (float)current_wav.wave.len;
        }
        if (current_paused) {
            paused_sample_position = position;
        } else {
            mixer_ch_set_pos(ROTT64_MUSIC_CHANNEL, position);
        }
    }
#else
    (void)milliseconds;
#endif
}

void MUSIC_GetSongPosition(songposition *position)
{
    float samples = 0.0f;
    float frequency = 0.0f;
    if (position == NULL) {
        return;
    }
    memset(position, 0, sizeof(*position));
    if (!current_open) {
        return;
    }
#ifdef __N64__
    samples = current_paused ? paused_sample_position
        : mixer_ch_get_pos(ROTT64_MUSIC_CHANNEL);
    frequency = current_wav.wave.frequency;
#endif
    if (frequency > 0.0f && samples > 0.0f) {
        position->milliseconds = (unsigned long)((samples * 1000.0f) / frequency);
    }
}

int MUSIC_FadeVolume(int tovolume, int milliseconds)
{
    /* First music milestone: transition immediately. Keeping this synchronous
     * prevents ROTT's fade wait loops from stalling while we validate playback. */
    (void)milliseconds;
    MUSIC_SetVolume(tovolume);
    return MUSIC_Ok;
}

int MUSIC_FadeActive(void)
{
    return __FX_FALSE;
}
