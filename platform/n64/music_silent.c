/* Silent music backend for the first playable ROTT64 milestone. */
#include <stddef.h>
#include "music.h"

const int num_music_modules = 1;
unsigned char *music_songdata;
size_t music_songdatasize;
int music_loopflag = MUSIC_PlayOnce;
double float_music_volume;
char *soundfont_cfg;

/* Keep both public module symbols linkable even though audio is forced off. */
music_module_t sdl_music_module = {
    MUSIC_Init, MUSIC_Shutdown, MUSIC_SongPlaying, MUSIC_Continue, MUSIC_Pause,
    MUSIC_StopSong, MUSIC_PlaySong, MUSIC_FadeVolume, MUSIC_FadeActive
};
music_module_t adl_music_module = {
    MUSIC_Init, MUSIC_Shutdown, MUSIC_SongPlaying, MUSIC_Continue, MUSIC_Pause,
    MUSIC_StopSong, MUSIC_PlaySong, MUSIC_FadeVolume, MUSIC_FadeActive
};

int MUSIC_Init(int mode) { (void)mode; return MUSIC_Ok; }
int MUSIC_Shutdown(void) { music_songdata = NULL; music_songdatasize = 0; return MUSIC_Ok; }
void MUSIC_SetVolume(int volume) { float_music_volume = (double)volume / 255.0; }
int MUSIC_SongPlaying(void) { return __FX_FALSE; }
void MUSIC_Continue(void) { }
void MUSIC_Pause(void) { }
int MUSIC_StopSong(void) { music_songdata = NULL; music_songdatasize = 0; return MUSIC_Ok; }
int MUSIC_PlaySong(unsigned char *song, int size, int loopflag)
{
    music_songdata = song;
    music_songdatasize = size > 0 ? (size_t)size : 0u;
    music_loopflag = loopflag;
    return MUSIC_Ok;
}
void MUSIC_SetSongTime(unsigned long milliseconds) { (void)milliseconds; }
void MUSIC_GetSongPosition(songposition *position) { if (position != NULL) *position = (songposition){0}; }
int MUSIC_FadeVolume(int volume, int milliseconds) { (void)milliseconds; MUSIC_SetVolume(volume); return MUSIC_Ok; }
int MUSIC_FadeActive(void) { return __FX_FALSE; }

void rott64_music_pump(void) { }
