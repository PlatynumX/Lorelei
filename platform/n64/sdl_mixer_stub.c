#include "SDL_mixer.h"
#include <stdlib.h>
#include <string.h>

static int opened;
static int channel_count = 8;
static int music_volume = MIX_MAX_VOLUME;
static void (*finished_callback)(int);

int Mix_OpenAudioDevice(int frequency, Uint16 format, int channels, int chunksize, const char *device, int allowed_changes)
{
    (void)device; (void)allowed_changes;
    return Mix_OpenAudio(frequency, format, channels, chunksize);
}

int Mix_MasterVolume(int volume) { return volume; }

int Mix_OpenAudio(int frequency, Uint16 format, int channels, int chunksize)
{ (void)frequency; (void)format; (void)channels; (void)chunksize; opened = 1; return 0; }
void Mix_CloseAudio(void) { opened = 0; }
int Mix_QuerySpec(int *frequency, Uint16 *format, int *channels)
{ if (!opened) return 0; if (frequency) *frequency=MIX_DEFAULT_FREQUENCY; if (format) *format=MIX_DEFAULT_FORMAT; if (channels) *channels=MIX_DEFAULT_CHANNELS; return 1; }
int Mix_AllocateChannels(int numchans) { if (numchans >= 0) channel_count=numchans; return channel_count; }
void Mix_ChannelFinished(void (*callback)(int)) { finished_callback=callback; (void)finished_callback; }
Mix_Chunk *Mix_LoadWAV_RW(SDL_RWops *src, int freesrc) { if (freesrc && src) SDL_RWclose(src); return NULL; }
void Mix_FreeChunk(Mix_Chunk *chunk) { if (chunk) { if (chunk->allocated) free(chunk->abuf); free(chunk); } }
int Mix_PlayChannelTimed(int channel, Mix_Chunk *chunk, int loops, int ticks)
{ (void)channel; (void)chunk; (void)loops; (void)ticks; return -1; }
int Mix_HaltChannel(int channel) { (void)channel; return 0; }
int Mix_Playing(int channel) { (void)channel; return 0; }
int Mix_Volume(int channel, int volume) { (void)channel; return volume; }
int Mix_VolumeChunk(Mix_Chunk *chunk, int volume) { int old=chunk?chunk->volume:0; if (chunk && volume>=0) chunk->volume=(Uint8)volume; return old; }
int Mix_SetPanning(int channel, Uint8 left, Uint8 right) { (void)channel; (void)left; (void)right; return 1; }
void Mix_Pause(int channel) { (void)channel; }
void Mix_Resume(int channel) { (void)channel; }
const char *Mix_GetError(void) { return "ROTT64 audio disabled in first-level candidate"; }
void Mix_HookMusic(void (*mix_func)(void *, Uint8 *, int), void *arg) { (void)mix_func; (void)arg; }
void Mix_HaltMusic(void) { }
int Mix_PlayingMusic(void) { return 0; }
void Mix_PauseMusic(void) { }
void Mix_ResumeMusic(void) { }
int Mix_VolumeMusic(int volume) { int old=music_volume; if (volume>=0) music_volume=volume; return old; }
