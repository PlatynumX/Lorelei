/* Silent sound-effects backend for the first playable ROTT64 milestone. */
#include "fx_man.h"

static int reverse_stereo;

char *FX_ErrorString(int error_number)
{
    (void)error_number;
    return "ROTT64 sound disabled";
}

int FX_SetupCard(void) { return FX_Ok; }
int FX_Init(void) { return FX_Ok; }
int FX_Shutdown(void) { return FX_Ok; }
int FX_SetCallBack(void (*function)(unsigned long)) { (void)function; return FX_Ok; }
void FX_SetVolume(int volume) { (void)volume; }
void FX_SetReverseStereo(int setting) { reverse_stereo = setting; }
int FX_GetReverseStereo(void) { return reverse_stereo; }
void FX_SetReverb(int reverb) { (void)reverb; }
int FX_VoiceAvailable(int priority) { (void)priority; return 0; }
int FX_SetPan(int handle, int volume, int left, int right)
{
    (void)handle; (void)volume; (void)left; (void)right; return FX_Ok;
}
int FX_SetPitch(int handle, int pitch_offset) { (void)handle; (void)pitch_offset; return FX_Ok; }
int FX_Play(int handle, int sound, int pitch_offset, int angle, int distance, int priority)
{
    (void)sound; (void)pitch_offset; (void)angle; (void)distance; (void)priority; return handle;
}
int FX_Pan3D(int handle, int angle, int distance) { (void)handle; (void)angle; (void)distance; return FX_Ok; }
int FX_SoundActive(int handle) { (void)handle; return 0; }
int FX_StopSound(int handle) { (void)handle; return FX_Ok; }
int FX_StopAllSounds(void) { return FX_Ok; }
int FX_SetXY(int handle, int x, int y) { (void)handle; (void)x; (void)y; return FX_Ok; }
int FX_AllSoundsRTP(void) { return FX_Ok; }
