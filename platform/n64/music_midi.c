/* ROTT64 native sequenced MIDI music backend.
 *
 * Taradino passes the original Standard MIDI File lump to MUSIC_PlaySong().
 * ROTT64 parses the sequence in memory and synthesizes a lightweight GM-ish
 * approximation directly into a libdragon mixer waveform. No pre-rendered
 * WAV64 soundtrack is stored in the ROM, so registered/custom MIDI content can
 * play without a build-time render step.
 */
#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

#include "SDL_mixer.h"
#include "music.h"
#include "rott64_audio.h"

#ifdef __N64__
#include <libdragon.h>
#endif

const int num_music_modules = 2;
unsigned char *music_songdata;
size_t music_songdatasize;
int music_loopflag = MUSIC_PlayOnce;
double float_music_volume;
char *soundfont_cfg;
music_module_t sdl_music_module = {0};
music_module_t adl_music_module = {0};

#define ROTT64_MIDI_RATE 22050
#define ROTT64_MIDI_MAX_VOICES 20
#define ROTT64_MIDI_TAIL_SAMPLES (ROTT64_MIDI_RATE / 10)

typedef enum {
    EV_NOTE_OFF = 0,
    EV_NOTE_ON,
    EV_CONTROL,
    EV_PROGRAM,
    EV_PITCH,
    EV_TEMPO,
    EV_END
} seq_event_type_t;

typedef struct {
    uint32_t tick;
    uint32_t order;
    seq_event_type_t type;
    uint8_t channel;
    uint8_t a;
    uint8_t b;
    uint32_t value;
} raw_event_t;

typedef struct {
    uint32_t sample;
    seq_event_type_t type;
    uint8_t channel;
    uint8_t a;
    uint8_t b;
    uint32_t value;
} seq_event_t;

typedef struct {
    uint8_t active;
    uint8_t releasing;
    uint8_t channel;
    uint8_t note;
    uint8_t velocity;
    uint8_t waveform;
    uint32_t phase;
    uint32_t phase_inc;
    int32_t env;
} synth_voice_t;

typedef struct {
    uint8_t program[16];
    uint8_t volume[16];
    uint8_t expression[16];
    uint8_t sustain[16];
    int16_t pitch[16];
    synth_voice_t voices[ROTT64_MIDI_MAX_VOICES];
    uint32_t noise;
    uint32_t rendered_pos;
    size_t next_event;
} synth_state_t;

static seq_event_t *seq_events;
static size_t seq_event_count;
static uint32_t seq_total_samples;
static synth_state_t synth;
static int current_open;
static int current_paused;
static float paused_sample_position;
static int current_volume = 255;

#ifdef __N64__
static waveform_t midi_waves[2];
static int midi_wave_index;
#endif

static uint16_t be16(const uint8_t *p)
{
    return (uint16_t)(((uint16_t)p[0] << 8) | p[1]);
}

static uint32_t be32(const uint8_t *p)
{
    return ((uint32_t)p[0] << 24) | ((uint32_t)p[1] << 16)
         | ((uint32_t)p[2] << 8) | (uint32_t)p[3];
}

static int read_vlq(const uint8_t *data, size_t size, size_t *pos, uint32_t *out)
{
    uint32_t value = 0;
    int count = 0;
    while (*pos < size && count < 4) {
        uint8_t byte = data[(*pos)++];
        value = (value << 7) | (uint32_t)(byte & 0x7F);
        ++count;
        if ((byte & 0x80) == 0) {
            *out = value;
            return 1;
        }
    }
    return 0;
}

static int raw_event_cmp(const void *lhs, const void *rhs)
{
    const raw_event_t *a = (const raw_event_t *)lhs;
    const raw_event_t *b = (const raw_event_t *)rhs;
    if (a->tick < b->tick) return -1;
    if (a->tick > b->tick) return 1;
    /* Tempo changes at a tick take effect before musical events at that tick. */
    if (a->type == EV_TEMPO && b->type != EV_TEMPO) return -1;
    if (b->type == EV_TEMPO && a->type != EV_TEMPO) return 1;
    if (a->order < b->order) return -1;
    if (a->order > b->order) return 1;
    return 0;
}

static int append_raw_event(raw_event_t **events, size_t *count, size_t *capacity,
                            const raw_event_t *event)
{
    if (*count == *capacity) {
        size_t new_capacity = *capacity ? *capacity * 2u : 256u;
        raw_event_t *new_events = (raw_event_t *)realloc(*events,
            new_capacity * sizeof(**events));
        if (!new_events) return 0;
        *events = new_events;
        *capacity = new_capacity;
    }
    (*events)[(*count)++] = *event;
    return 1;
}

static int parse_track(const uint8_t *data, size_t size, raw_event_t **events,
                       size_t *count, size_t *capacity, uint32_t *order)
{
    size_t pos = 0;
    uint32_t tick = 0;
    uint8_t running = 0;

    while (pos < size) {
        uint32_t delta;
        uint8_t status;
        raw_event_t ev;
        if (!read_vlq(data, size, &pos, &delta)) return 0;
        tick += delta;
        if (pos >= size) return 0;
        status = data[pos++];
        if (status < 0x80) {
            if (!running) return 0;
            --pos;
            status = running;
        } else if (status < 0xF0) {
            running = status;
        }

        memset(&ev, 0, sizeof(ev));
        ev.tick = tick;
        ev.order = (*order)++;
        ev.channel = status & 0x0F;

        switch (status & 0xF0) {
        case 0x80:
        case 0x90:
            if (pos + 2 > size) return 0;
            ev.a = data[pos++];
            ev.b = data[pos++];
            ev.type = ((status & 0xF0) == 0x90 && ev.b != 0) ? EV_NOTE_ON : EV_NOTE_OFF;
            if (!append_raw_event(events, count, capacity, &ev)) return 0;
            break;
        case 0xA0:
            if (pos + 2 > size) return 0;
            pos += 2;
            break;
        case 0xB0:
            if (pos + 2 > size) return 0;
            ev.type = EV_CONTROL;
            ev.a = data[pos++];
            ev.b = data[pos++];
            if (!append_raw_event(events, count, capacity, &ev)) return 0;
            break;
        case 0xC0:
            if (pos + 1 > size) return 0;
            ev.type = EV_PROGRAM;
            ev.a = data[pos++];
            if (!append_raw_event(events, count, capacity, &ev)) return 0;
            break;
        case 0xD0:
            if (pos + 1 > size) return 0;
            ++pos;
            break;
        case 0xE0:
            if (pos + 2 > size) return 0;
            ev.type = EV_PITCH;
            ev.value = (uint32_t)data[pos] | ((uint32_t)data[pos + 1] << 7);
            pos += 2;
            if (!append_raw_event(events, count, capacity, &ev)) return 0;
            break;
        case 0xF0:
            if (status == 0xFF) {
                uint8_t meta;
                uint32_t len;
                running = 0;
                if (pos >= size) return 0;
                meta = data[pos++];
                if (!read_vlq(data, size, &pos, &len) || pos + len > size) return 0;
                if (meta == 0x51 && len == 3) {
                    ev.type = EV_TEMPO;
                    ev.value = ((uint32_t)data[pos] << 16)
                             | ((uint32_t)data[pos + 1] << 8)
                             | (uint32_t)data[pos + 2];
                    if (!append_raw_event(events, count, capacity, &ev)) return 0;
                } else if (meta == 0x2F) {
                    ev.type = EV_END;
                    if (!append_raw_event(events, count, capacity, &ev)) return 0;
                }
                pos += len;
            } else if (status == 0xF0 || status == 0xF7) {
                uint32_t len;
                running = 0;
                if (!read_vlq(data, size, &pos, &len) || pos + len > size) return 0;
                pos += len;
            } else {
                return 0;
            }
            break;
        default:
            return 0;
        }
    }
    return 1;
}

static int load_sequence(const unsigned char *song, int size)
{
    const uint8_t *data = song;
    size_t pos;
    uint16_t format, tracks, division;
    raw_event_t *raw = NULL;
    size_t raw_count = 0, raw_capacity = 0;
    uint32_t order = 0;
    uint32_t tempo = 500000;
    uint32_t last_tick = 0;
    double sample_cursor = 0.0;

    free(seq_events);
    seq_events = NULL;
    seq_event_count = 0;
    seq_total_samples = 0;

    if (!song || size < 14 || memcmp(data, "MThd", 4) != 0 || be32(data + 4) < 6)
        return 0;
    format = be16(data + 8);
    tracks = be16(data + 10);
    division = be16(data + 12);
    if (format > 1 || tracks == 0 || (division & 0x8000) || division == 0)
        return 0;

    pos = 8u + be32(data + 4);
    for (uint16_t i = 0; i < tracks; ++i) {
        uint32_t track_size;
        if (pos + 8 > (size_t)size || memcmp(data + pos, "MTrk", 4) != 0) goto fail;
        track_size = be32(data + pos + 4);
        pos += 8;
        if (pos + track_size > (size_t)size) goto fail;
        if (!parse_track(data + pos, track_size, &raw, &raw_count, &raw_capacity, &order)) goto fail;
        pos += track_size;
    }

    qsort(raw, raw_count, sizeof(*raw), raw_event_cmp);
    seq_events = (seq_event_t *)calloc(raw_count ? raw_count : 1u, sizeof(*seq_events));
    if (!seq_events) goto fail;

    for (size_t i = 0; i < raw_count; ++i) {
        uint32_t delta_ticks = raw[i].tick - last_tick;
        sample_cursor += ((double)delta_ticks * (double)tempo * (double)ROTT64_MIDI_RATE)
                       / ((double)division * 1000000.0);
        seq_events[i].sample = (uint32_t)(sample_cursor + 0.5);
        seq_events[i].type = raw[i].type;
        seq_events[i].channel = raw[i].channel;
        seq_events[i].a = raw[i].a;
        seq_events[i].b = raw[i].b;
        seq_events[i].value = raw[i].value;
        last_tick = raw[i].tick;
        if (raw[i].type == EV_TEMPO && raw[i].value > 0)
            tempo = raw[i].value;
    }
    seq_event_count = raw_count;
    seq_total_samples = (raw_count ? seq_events[raw_count - 1].sample : 0u) + ROTT64_MIDI_TAIL_SAMPLES;
    if (seq_total_samples < ROTT64_MIDI_RATE) seq_total_samples = ROTT64_MIDI_RATE;
    free(raw);
    return 1;

fail:
    free(raw);
    free(seq_events);
    seq_events = NULL;
    seq_event_count = 0;
    seq_total_samples = 0;
    return 0;
}


#define ROTT64_MIDI_VOICES 8
#define ROTT64_MIDI_CYCLE_SAMPLES 32
#define ROTT64_MIDI_CYCLE_LEN 96
#define ROTT64_MIDI_PERC_LEN 256

typedef struct {
    uint8_t active;
    uint8_t sustained;
    uint8_t channel;
    uint8_t note;
    uint8_t velocity;
    uint8_t wave_index;
    int mixer_channel;
} midi_voice_t;

typedef struct {
    uint8_t program[16];
    uint8_t volume[16];
    uint8_t expression[16];
    uint8_t sustain[16];
    int16_t pitch[16];
    midi_voice_t voices[ROTT64_MIDI_VOICES];
    size_t next_event;
} sequencer_state_t;

static sequencer_state_t seq_state;
static int current_open;
static int current_paused;
static int current_volume = 255;
static uint32_t song_position_samples;
static uint64_t song_anchor_ms;
static uint32_t paused_position_samples;

#ifdef __N64__
static waveform_t tone_waves[3];
static waveform_t percussion_wave;
#endif

static void sequencer_reset(void)
{
    memset(&seq_state, 0, sizeof(seq_state));
    for (int i = 0; i < 16; ++i) {
        seq_state.volume[i] = 100;
        seq_state.expression[i] = 127;
    }
    for (int i = 0; i < ROTT64_MIDI_VOICES; ++i)
        seq_state.voices[i].mixer_channel = ROTT64_MUSIC_CHANNEL_BASE + i;
}

static float note_hz(uint8_t note, int16_t pitch)
{
    float semitone = (float)((int)note - 69) + ((float)pitch / 8192.0f) * 2.0f;
    return 440.0f * powf(2.0f, semitone / 12.0f);
}

static uint8_t program_waveform(uint8_t program)
{
    if (program < 8) return 2;       /* piano-ish triangle */
    if (program < 24) return 1;      /* organ/chromatic square */
    if (program < 40) return 2;      /* guitar/bass triangle */
    if (program < 56) return 0;      /* strings saw */
    if (program < 80) return 1;      /* brass/reed square */
    if (program < 96) return 2;      /* leads/pads triangle */
    return 0;
}

#ifdef __N64__
static void tone_wave_read(void *ctx, samplebuffer_t *sbuf,
                           int wpos, int wlen, bool seeking)
{
    intptr_t wave = (intptr_t)ctx;
    int16_t *out;
    (void)seeking;
    if (wlen <= 0) return;

    out = (int16_t *)samplebuffer_append(sbuf, wlen);
    for (int i = 0; i < wlen; ++i) {
        unsigned p = (unsigned)(wpos + i) % ROTT64_MIDI_CYCLE_SAMPLES;
        int32_t sample;

        if (wave == 0) {
            /* Saw */
            sample = -24000 + (int32_t)((48000u * p) / ROTT64_MIDI_CYCLE_SAMPLES);
        } else if (wave == 1) {
            /* Square */
            sample = p < (ROTT64_MIDI_CYCLE_SAMPLES / 2) ? 22000 : -22000;
        } else {
            /* Triangle */
            unsigned q = p < 16 ? p : 31u - p;
            sample = -24000 + (int32_t)((48000u * q) / 15u);
        }
        out[i] = (int16_t)sample;
    }
}

static void percussion_wave_read(void *ctx, samplebuffer_t *sbuf,
                                 int wpos, int wlen, bool seeking)
{
    int16_t *out;
    uint32_t x = 0x9E3779B9u ^ (uint32_t)wpos;
    (void)ctx;
    (void)seeking;
    if (wlen <= 0) return;

    out = (int16_t *)samplebuffer_append(sbuf, wlen);
    for (int i = 0; i < wlen; ++i) {
        int pos = wpos + i;
        int32_t env = ROTT64_MIDI_PERC_LEN - pos;
        if (env < 0) env = 0;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        out[i] = (int16_t)(((int32_t)(int16_t)(x >> 16) * env)
                         / ROTT64_MIDI_PERC_LEN);
    }
}
#endif

static float voice_gain(const midi_voice_t *v)
{
    uint8_t ch = v->channel & 15u;
    float gain = ((float)v->velocity / 127.0f)
               * ((float)seq_state.volume[ch] / 127.0f)
               * ((float)seq_state.expression[ch] / 127.0f)
               * ((float)current_volume / 255.0f);
    /* Leave headroom for multiple simultaneous MIDI voices and SFX. */
    gain *= 0.28f;
    if (gain < 0.0f) gain = 0.0f;
    if (gain > 1.0f) gain = 1.0f;
    return gain;
}

static void update_voice_volume(midi_voice_t *v)
{
#ifdef __N64__
    if (v->active) {
        float gain = voice_gain(v);
        mixer_ch_set_vol(v->mixer_channel, gain, gain);
    }
#else
    (void)v;
#endif
}

static void update_channel_volumes(uint8_t channel)
{
    for (int i = 0; i < ROTT64_MIDI_VOICES; ++i)
        if (seq_state.voices[i].active && seq_state.voices[i].channel == channel)
            update_voice_volume(&seq_state.voices[i]);
}

static void update_voice_pitch(midi_voice_t *v)
{
#ifdef __N64__
    if (v->active && v->channel != 9u) {
        float hz = note_hz(v->note, seq_state.pitch[v->channel & 15u]);
        float playback_rate = hz * (float)ROTT64_MIDI_CYCLE_SAMPLES;
        mixer_ch_set_freq(v->mixer_channel, playback_rate);
    }
#else
    (void)v;
#endif
}

static void update_channel_pitch(uint8_t channel)
{
    for (int i = 0; i < ROTT64_MIDI_VOICES; ++i)
        if (seq_state.voices[i].active && seq_state.voices[i].channel == channel)
            update_voice_pitch(&seq_state.voices[i]);
}

static midi_voice_t *alloc_voice(void)
{
    for (int i = 0; i < ROTT64_MIDI_VOICES; ++i) {
        if (!seq_state.voices[i].active)
            return &seq_state.voices[i];
    }

    /* Deterministic voice stealing: recycle voice 0 when polyphony exceeds
       the dedicated N64 music channel budget. */
#ifdef __N64__
    mixer_ch_stop(seq_state.voices[0].mixer_channel);
#endif
    seq_state.voices[0].active = 0;
    return &seq_state.voices[0];
}

static void stop_voice(midi_voice_t *v)
{
#ifdef __N64__
    if (v->active)
        mixer_ch_stop(v->mixer_channel);
#endif
    v->active = 0;
    v->sustained = 0;
}

static void stop_all_voices(void)
{
    for (int i = 0; i < ROTT64_MIDI_VOICES; ++i)
        stop_voice(&seq_state.voices[i]);
}

static void note_on(uint8_t ch, uint8_t note, uint8_t velocity)
{
    midi_voice_t *v = alloc_voice();
    memset(v, 0, sizeof(*v));
    v->active = 1;
    v->channel = ch;
    v->note = note;
    v->velocity = velocity;
    v->mixer_channel = ROTT64_MUSIC_CHANNEL_BASE
                     + (int)(v - seq_state.voices);

#ifdef __N64__
    if (ch == 9u) {
        mixer_ch_play(v->mixer_channel, &percussion_wave);
        mixer_ch_set_freq(v->mixer_channel, 11025.0f);
    } else {
        v->wave_index = program_waveform(seq_state.program[ch]);
        mixer_ch_play(v->mixer_channel, &tone_waves[v->wave_index]);
        update_voice_pitch(v);
    }
#endif
    update_voice_volume(v);
}

static void note_off(uint8_t ch, uint8_t note)
{
    for (int i = 0; i < ROTT64_MIDI_VOICES; ++i) {
        midi_voice_t *v = &seq_state.voices[i];
        if (!v->active || v->channel != ch || v->note != note)
            continue;
        if (seq_state.sustain[ch])
            v->sustained = 1;
        else
            stop_voice(v);
    }
}

static void release_sustained(uint8_t ch)
{
    for (int i = 0; i < ROTT64_MIDI_VOICES; ++i) {
        midi_voice_t *v = &seq_state.voices[i];
        if (v->active && v->channel == ch && v->sustained)
            stop_voice(v);
    }
}

static void apply_event(const seq_event_t *ev)
{
    uint8_t ch = ev->channel & 15u;

    switch (ev->type) {
    case EV_NOTE_ON:
        note_on(ch, ev->a, ev->b);
        break;
    case EV_NOTE_OFF:
        note_off(ch, ev->a);
        break;
    case EV_PROGRAM:
        seq_state.program[ch] = ev->a;
        break;
    case EV_CONTROL:
        if (ev->a == 7u) {
            seq_state.volume[ch] = ev->b;
            update_channel_volumes(ch);
        } else if (ev->a == 11u) {
            seq_state.expression[ch] = ev->b;
            update_channel_volumes(ch);
        } else if (ev->a == 64u) {
            uint8_t was = seq_state.sustain[ch];
            seq_state.sustain[ch] = ev->b >= 64u;
            if (was && !seq_state.sustain[ch])
                release_sustained(ch);
        } else if (ev->a == 120u || ev->a == 123u) {
            for (int i = 0; i < ROTT64_MIDI_VOICES; ++i)
                if (seq_state.voices[i].active &&
                    seq_state.voices[i].channel == ch)
                    stop_voice(&seq_state.voices[i]);
        }
        break;
    case EV_PITCH:
        seq_state.pitch[ch] = (int16_t)((int)ev->value - 8192);
        update_channel_pitch(ch);
        break;
    case EV_TEMPO:
    case EV_END:
        break;
    }
}

static void seek_sequence(uint32_t target_samples)
{
    stop_all_voices();
    sequencer_reset();

    /* Rebuild controller/program state and currently held notes by replaying
       events up to the requested point. This is only used for explicit seek
       or resume, not during the steady-state audio path. */
    while (seq_state.next_event < seq_event_count &&
           seq_events[seq_state.next_event].sample <= target_samples) {
        apply_event(&seq_events[seq_state.next_event]);
        ++seq_state.next_event;
    }

    song_position_samples = target_samples;
}

static void apply_music_volume(void)
{
    for (int i = 0; i < ROTT64_MIDI_VOICES; ++i)
        update_voice_volume(&seq_state.voices[i]);
    float_music_volume = (double)current_volume / 255.0;
}

int MUSIC_Init(int mode)
{
    int frequency = 0;
    (void)mode;

    if (Mix_QuerySpec(&frequency, NULL, NULL) == 0) {
        if (Mix_OpenAudio(MIX_DEFAULT_FREQUENCY, MIX_DEFAULT_FORMAT,
                          MIX_DEFAULT_CHANNELS, 512) != 0)
            return MUSIC_Error;
    }

#ifdef __N64__
    memset(tone_waves, 0, sizeof(tone_waves));
    for (int i = 0; i < 3; ++i) {
        tone_waves[i].name = "ROTT64 MIDI oscillator";
        tone_waves[i].bits = 16;
        tone_waves[i].channels = 1;
        tone_waves[i].frequency = 14080.0f; /* A4: 440Hz * 32 samples */
        tone_waves[i].len = ROTT64_MIDI_CYCLE_LEN;
        tone_waves[i].loop_len = ROTT64_MIDI_CYCLE_SAMPLES;
        tone_waves[i].read = tone_wave_read;
        tone_waves[i].ctx = (void *)(intptr_t)i;
    }

    memset(&percussion_wave, 0, sizeof(percussion_wave));
    percussion_wave.name = "ROTT64 MIDI percussion";
    percussion_wave.bits = 16;
    percussion_wave.channels = 1;
    percussion_wave.frequency = 11025.0f;
    percussion_wave.len = ROTT64_MIDI_PERC_LEN;
    percussion_wave.loop_len = 0;
    percussion_wave.read = percussion_wave_read;
#endif

    current_open = 0;
    current_paused = 0;
    song_position_samples = 0;
    paused_position_samples = 0;
    song_anchor_ms = 0;
    sequencer_reset();
    apply_music_volume();
    return MUSIC_Ok;
}

int MUSIC_Shutdown(void)
{
    return MUSIC_StopSong();
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
    return current_open ? __FX_TRUE : __FX_FALSE;
}

void MUSIC_Pause(void)
{
    if (!current_open || current_paused) return;
#ifdef __N64__
    uint64_t now = (uint64_t)get_ticks_ms();
    uint64_t elapsed = now >= song_anchor_ms ? now - song_anchor_ms : 0u;
    paused_position_samples = song_position_samples
        + (uint32_t)((elapsed * ROTT64_MIDI_RATE) / 1000u);
#endif
    stop_all_voices();
    current_paused = 1;
}

void MUSIC_Continue(void)
{
    if (!current_open || !current_paused) return;
    seek_sequence(paused_position_samples);
#ifdef __N64__
    song_anchor_ms = (uint64_t)get_ticks_ms();
#endif
    current_paused = 0;
}

int MUSIC_StopSong(void)
{
    stop_all_voices();
    current_open = 0;
    current_paused = 0;
    song_position_samples = 0;
    paused_position_samples = 0;
    song_anchor_ms = 0;
    music_songdata = NULL;
    music_songdatasize = 0u;
    music_loopflag = MUSIC_PlayOnce;
    free(seq_events);
    seq_events = NULL;
    seq_event_count = 0;
    seq_total_samples = 0;
    sequencer_reset();
    return MUSIC_Ok;
}

int MUSIC_PlaySong(unsigned char *song, int size, int loopflag)
{
    (void)MUSIC_StopSong();

    if (!load_sequence(song, size)) {
        SDL_SetError("ROTT64 MIDI sequencer could not parse song");
        return MUSIC_Error;
    }

    music_songdata = song;
    music_songdatasize = (size_t)size;
    music_loopflag = loopflag;
    sequencer_reset();
    song_position_samples = 0;
    paused_position_samples = 0;
#ifdef __N64__
    song_anchor_ms = (uint64_t)get_ticks_ms();
#endif
    current_open = 1;
    current_paused = 0;

    /* Do not synthesize or stream PCM here. The normal audio pump advances
       MIDI events incrementally after the game has returned to its main loop. */
    return MUSIC_Ok;
}

void MUSIC_SetSongTime(unsigned long milliseconds)
{
    uint32_t target;
    if (!current_open) return;

    target = (uint32_t)(((uint64_t)milliseconds * ROTT64_MIDI_RATE) / 1000u);
    if (target > seq_total_samples)
        target = seq_total_samples;

    seek_sequence(target);
    if (current_paused) {
        paused_position_samples = target;
    } else {
#ifdef __N64__
        song_anchor_ms = (uint64_t)get_ticks_ms();
#endif
    }
}

void MUSIC_GetSongPosition(songposition *position)
{
    uint32_t samples = song_position_samples;
    if (!position) return;

    memset(position, 0, sizeof(*position));
    if (!current_open) return;

#ifdef __N64__
    if (current_paused) {
        samples = paused_position_samples;
    } else {
        uint64_t now = (uint64_t)get_ticks_ms();
        uint64_t elapsed = now >= song_anchor_ms ? now - song_anchor_ms : 0u;
        samples += (uint32_t)((elapsed * ROTT64_MIDI_RATE) / 1000u);
    }
#endif

    position->milliseconds =
        (unsigned long)(((uint64_t)samples * 1000u) / ROTT64_MIDI_RATE);
}

void rott64_music_pump(void)
{
#ifdef __N64__
    uint64_t now;
    uint64_t elapsed;
    uint32_t target;

    if (!current_open || current_paused)
        return;

    now = (uint64_t)get_ticks_ms();
    elapsed = now >= song_anchor_ms ? now - song_anchor_ms : 0u;
    target = song_position_samples
           + (uint32_t)((elapsed * ROTT64_MIDI_RATE) / 1000u);

    if (target >= seq_total_samples) {
        if (music_loopflag == MUSIC_LoopSong) {
            stop_all_voices();
            sequencer_reset();
            song_position_samples = 0;
            song_anchor_ms = now;
            target = 0;
        } else {
            (void)MUSIC_StopSong();
            return;
        }
    }

    while (seq_state.next_event < seq_event_count &&
           seq_events[seq_state.next_event].sample <= target) {
        apply_event(&seq_events[seq_state.next_event]);
        ++seq_state.next_event;
    }
#endif
}

int MUSIC_FadeVolume(int tovolume, int milliseconds)
{
    (void)milliseconds;
    MUSIC_SetVolume(tovolume);
    return MUSIC_Ok;
}

int MUSIC_FadeActive(void)
{
    return __FX_FALSE;
}
