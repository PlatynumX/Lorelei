#ifndef ROTT64_AUDIO_H
#define ROTT64_AUDIO_H

/* ROTT64_R90H_AUDIO_CHANNEL_CONTRACT
 *
 * Constants only. No mixer wrapper macros, no generated-source call rewriting.
 *
 * FX channels:      0..7
 * Music owner:      8
 * Music stereo sub: 9
 * Mixer channels:   10
 */
#define ROTT64_FX_CHANNELS 8
#define ROTT64_MUSIC_CHANNEL 8
#define ROTT64_MUSIC_STEREO_SUBCHANNEL 9
#define ROTT64_MIXER_CHANNELS 10

#endif /* ROTT64_AUDIO_H */
