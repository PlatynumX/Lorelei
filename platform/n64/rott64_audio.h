#ifndef ROTT64_AUDIO_H
#define ROTT64_AUDIO_H

/* Taradino's FX backend owns channels 0..7. Keep one independent mono
 * streaming channel for music so rapid sound effects cannot steal it. */
#define ROTT64_FX_CHANNELS 8
#define ROTT64_MUSIC_CHANNEL 8
#define ROTT64_MIXER_CHANNELS 9

/* Service non-blocking music restart logic from the normal audio pump. */
void rott64_music_pump(void);

#endif
