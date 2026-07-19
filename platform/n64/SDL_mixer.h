#ifndef ROTT64_SDL_MIXER_COMPAT_H
#define ROTT64_SDL_MIXER_COMPAT_H
#include "SDL.h"
#ifdef __cplusplus
extern "C" {
#endif
#define MIX_DEFAULT_FREQUENCY 22050
#define MIX_DEFAULT_FORMAT 0x8010
#define MIX_DEFAULT_CHANNELS 2
#define MIX_MAX_VOLUME 128
#define MIX_CHANNEL_POST -2
#define SDL_MIXER_VERSION_ATLEAST(X, Y, Z) 1
typedef struct Mix_Chunk {
    int allocated;
    Uint8 *abuf;
    Uint32 alen;
    Uint8 volume;
    void *backend;
    Uint32 frequency;
    Uint8 channels;
    Uint8 bits;
} Mix_Chunk;
typedef struct Mix_Music { int unused; } Mix_Music;
int Mix_OpenAudio(int frequency, Uint16 format, int channels, int chunksize);
int Mix_OpenAudioDevice(int frequency, Uint16 format, int channels, int chunksize, const char *device, int allowed_changes);
int Mix_MasterVolume(int volume);
void Mix_CloseAudio(void);
int Mix_QuerySpec(int *frequency, Uint16 *format, int *channels);
int Mix_AllocateChannels(int numchans);
void Mix_ChannelFinished(void (*channel_finished)(int channel));
Mix_Chunk *Mix_LoadWAV_RW(SDL_RWops *src, int freesrc);
#define Mix_LoadWAV(file) Mix_LoadWAV_RW(SDL_RWFromFile((file), "rb"), 1)
void Mix_FreeChunk(Mix_Chunk *chunk);
int Mix_PlayChannelTimed(int channel, Mix_Chunk *chunk, int loops, int ticks);
#define Mix_PlayChannel(channel, chunk, loops) Mix_PlayChannelTimed((channel), (chunk), (loops), -1)
int Mix_HaltChannel(int channel);
int Mix_Playing(int channel);
int Mix_Volume(int channel, int volume);
int Mix_VolumeChunk(Mix_Chunk *chunk, int volume);
int Mix_SetPanning(int channel, Uint8 left, Uint8 right);
void Mix_Pause(int channel);
void Mix_Resume(int channel);
const char *Mix_GetError(void);
void Mix_HookMusic(void (*mix_func)(void *udata, Uint8 *stream, int len), void *arg);
void Mix_HaltMusic(void);
int Mix_PlayingMusic(void);
void Mix_PauseMusic(void);
void Mix_ResumeMusic(void);
int Mix_VolumeMusic(int volume);
void rott64_mixer_pump(void);
#ifdef __cplusplus
}
#endif
#endif
