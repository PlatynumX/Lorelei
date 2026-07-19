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

static uint32_t note_phase_inc(uint8_t note, int16_t pitch)
{
    float semitone = (float)((int)note - 69) + ((float)pitch / 8192.0f) * 2.0f;
    float hz = 440.0f * powf(2.0f, semitone / 12.0f);
    double inc = ((double)hz * 4294967296.0) / (double)ROTT64_MIDI_RATE;
    if (inc < 1.0) inc = 1.0;
    if (inc > 4294967295.0) inc = 4294967295.0;
    return (uint32_t)inc;
}

static uint8_t program_waveform(uint8_t program)
{
    if (program < 8) return 2;       /* pianos: triangle */
    if (program < 24) return 1;      /* chromatic/organ: square */
    if (program < 40) return 2;      /* guitars/bass: triangle */
    if (program < 56) return 0;      /* strings: saw */
    if (program < 80) return 1;      /* brass/reed: square */
    if (program < 96) return 2;      /* leads/pads: triangle */
    return 0;
}

static void synth_reset(void)
{
    memset(&synth, 0, sizeof(synth));
    for (int i = 0; i < 16; ++i) {
        synth.volume[i] = 100;
        synth.expression[i] = 127;
    }
    synth.noise = 0x13579BDFu;
}

static synth_voice_t *alloc_voice(void)
{
    synth_voice_t *quietest = &synth.voices[0];
    for (int i = 0; i < ROTT64_MIDI_MAX_VOICES; ++i) {
        if (!synth.voices[i].active) return &synth.voices[i];
        if (synth.voices[i].env < quietest->env) quietest = &synth.voices[i];
    }
    return quietest;
}

static void update_channel_pitch(uint8_t channel)
{
    for (int i = 0; i < ROTT64_MIDI_MAX_VOICES; ++i) {
        synth_voice_t *v = &synth.voices[i];
        if (v->active && v->channel == channel && channel != 9)
            v->phase_inc = note_phase_inc(v->note, synth.pitch[channel]);
    }
}

static void apply_event(const seq_event_t *ev)
{
    uint8_t ch = ev->channel & 15;
    switch (ev->type) {
    case EV_NOTE_ON: {
        synth_voice_t *v = alloc_voice();
        memset(v, 0, sizeof(*v));
        v->active = 1;
        v->channel = ch;
        v->note = ev->a;
        v->velocity = ev->b;
        v->waveform = (ch == 9) ? 3 : program_waveform(synth.program[ch]);
        v->phase_inc = note_phase_inc(ev->a, synth.pitch[ch]);
        v->env = (ch == 9) ? 32767 : 0;
        break;
    }
    case EV_NOTE_OFF:
        for (int i = 0; i < ROTT64_MIDI_MAX_VOICES; ++i) {
            synth_voice_t *v = &synth.voices[i];
            if (v->active && v->channel == ch && v->note == ev->a) {
                if (synth.sustain[ch]) v->releasing = 2;
                else v->releasing = 1;
            }
        }
        break;
    case EV_PROGRAM:
        synth.program[ch] = ev->a;
        break;
    case EV_CONTROL:
        if (ev->a == 7) synth.volume[ch] = ev->b;
        else if (ev->a == 11) synth.expression[ch] = ev->b;
        else if (ev->a == 64) {
            uint8_t was = synth.sustain[ch];
            synth.sustain[ch] = ev->b >= 64;
            if (was && !synth.sustain[ch]) {
                for (int i = 0; i < ROTT64_MIDI_MAX_VOICES; ++i)
                    if (synth.voices[i].active && synth.voices[i].channel == ch
                        && synth.voices[i].releasing == 2)
                        synth.voices[i].releasing = 1;
            }
        } else if (ev->a == 120 || ev->a == 123) {
            for (int i = 0; i < ROTT64_MIDI_MAX_VOICES; ++i)
                if (synth.voices[i].active && synth.voices[i].channel == ch)
                    synth.voices[i].releasing = 1;
        }
        break;
    case EV_PITCH:
        synth.pitch[ch] = (int16_t)((int)ev->value - 8192);
        update_channel_pitch(ch);
        break;
    case EV_TEMPO:
    case EV_END:
        break;
    }
}

static void advance_events_to(uint32_t sample)
{
    while (synth.next_event < seq_event_count && seq_events[synth.next_event].sample <= sample) {
        apply_event(&seq_events[synth.next_event]);
        ++synth.next_event;
    }
}

static int32_t voice_sample(synth_voice_t *v)
{
    int32_t raw;
    uint16_t p;
    uint8_t ch;
    int32_t gain;
    if (!v->active) return 0;
    ch = v->channel;
    if (v->waveform == 3) {
        synth.noise ^= synth.noise << 13;
        synth.noise ^= synth.noise >> 17;
        synth.noise ^= synth.noise << 5;
        raw = (int16_t)(synth.noise >> 16);
        v->env -= 700;
    } else {
        p = (uint16_t)(v->phase >> 16);
        if (v->waveform == 0) raw = (int16_t)p;
        else if (v->waveform == 1) raw = (p & 0x8000) ? 24000 : -24000;
        else {
            uint16_t q = p & 0x7FFF;
            raw = (p & 0x8000) ? (32767 - ((int32_t)q << 1))
                               : (-32767 + ((int32_t)q << 1));
        }
        v->phase += v->phase_inc;
        if (!v->releasing && v->env < 32767) {
            v->env += 700;
            if (v->env > 32767) v->env = 32767;
        } else if (v->releasing == 1) {
            v->env -= 350;
        }
    }
    if (v->env <= 0) {
        v->active = 0;
        return 0;
    }
    gain = (int32_t)v->velocity * synth.volume[ch] * synth.expression[ch];
    raw = (raw * (v->env >> 7)) >> 8;
    raw = (raw * gain) / (127 * 127 * 127);
    return raw;
}

static int16_t render_one_sample(void)
{
    int32_t mixed = 0;
    for (int i = 0; i < ROTT64_MIDI_MAX_VOICES; ++i)
        mixed += voice_sample(&synth.voices[i]);
    if (mixed > 32767) mixed = 32767;
    if (mixed < -32768) mixed = -32768;
    return (int16_t)mixed;
}

static void synth_seek(uint32_t target)
{
    synth_reset();
    /* Reconstruct note/channel state at the requested point. Phase continuity
     * is approximated by advancing active oscillator phases between events. */
    uint32_t cursor = 0;
    while (synth.next_event < seq_event_count && seq_events[synth.next_event].sample <= target) {
        uint32_t next = seq_events[synth.next_event].sample;
        uint32_t delta = next - cursor;
        for (int i = 0; i < ROTT64_MIDI_MAX_VOICES; ++i)
            if (synth.voices[i].active)
                synth.voices[i].phase += synth.voices[i].phase_inc * delta;
        cursor = next;
        advance_events_to(next);
    }
    if (target > cursor) {
        uint32_t delta = target - cursor;
        for (int i = 0; i < ROTT64_MIDI_MAX_VOICES; ++i)
            if (synth.voices[i].active)
                synth.voices[i].phase += synth.voices[i].phase_inc * delta;
    }
    synth.rendered_pos = target;
}

#ifdef __N64__
static void midi_wave_read(void *ctx, samplebuffer_t *sbuf, int wpos, int wlen, bool seeking)
{
    int16_t *out;
    (void)ctx;
    if (wlen <= 0) return;
    if (seeking || (uint32_t)wpos != synth.rendered_pos)
        synth_seek((uint32_t)wpos);
    out = (int16_t *)samplebuffer_append(sbuf, wlen);
    for (int i = 0; i < wlen; ++i) {
        advance_events_to(synth.rendered_pos);
        out[i] = render_one_sample();
        ++synth.rendered_pos;
    }
}
#endif

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
        if (Mix_OpenAudio(MIX_DEFAULT_FREQUENCY, MIX_DEFAULT_FORMAT, MIX_DEFAULT_CHANNELS, 512) != 0)
            return MUSIC_Error;
    }
    current_open = 0;
    current_paused = 0;
    paused_sample_position = 0.0f;
#ifdef __N64__
    memset(midi_waves, 0, sizeof(midi_waves));
    for (int i = 0; i < 2; ++i) {
        midi_waves[i].name = "ROTT64 MIDI synth";
        midi_waves[i].bits = 16;
        midi_waves[i].channels = 1;
        midi_waves[i].frequency = ROTT64_MIDI_RATE;
        midi_waves[i].loop_len = 0;
        midi_waves[i].read = midi_wave_read;
        midi_waves[i].ctx = NULL;
    }
    midi_wave_index = 0;
#endif
    synth_reset();
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
    if (!current_open) return __FX_FALSE;
#ifdef __N64__
    return (current_paused || mixer_ch_playing(ROTT64_MUSIC_CHANNEL)) ? __FX_TRUE : __FX_FALSE;
#else
    return current_paused ? __FX_TRUE : __FX_FALSE;
#endif
}

void MUSIC_Continue(void)
{
    if (!current_open || !current_paused) return;
#ifdef __N64__
    synth_seek((uint32_t)paused_sample_position);
    mixer_ch_play(ROTT64_MUSIC_CHANNEL, &midi_waves[midi_wave_index]);
    mixer_ch_set_pos(ROTT64_MUSIC_CHANNEL, paused_sample_position);
#endif
    current_paused = 0;
    apply_music_volume();
}

void MUSIC_Pause(void)
{
    if (!current_open || current_paused) return;
#ifdef __N64__
    paused_sample_position = mixer_ch_get_pos(ROTT64_MUSIC_CHANNEL);
    mixer_ch_stop(ROTT64_MUSIC_CHANNEL);
#endif
    current_paused = 1;
}

int MUSIC_StopSong(void)
{
#ifdef __N64__
    if (current_open) mixer_ch_stop(ROTT64_MUSIC_CHANNEL);
#endif
    current_open = 0;
    current_paused = 0;
    paused_sample_position = 0.0f;
    music_songdata = NULL;
    music_songdatasize = 0u;
    music_loopflag = MUSIC_PlayOnce;
    free(seq_events);
    seq_events = NULL;
    seq_event_count = 0;
    seq_total_samples = 0;
    synth_reset();
    return MUSIC_Ok;
}

int MUSIC_PlaySong(unsigned char *song, int size, int loopflag)
{
    (void)MUSIC_StopSong();
    if (!load_sequence(song, size)) {
        SDL_SetError("ROTT64 MIDI synth could not parse song");
        return MUSIC_Error;
    }
    music_songdata = song;
    music_songdatasize = (size_t)size;
    music_loopflag = loopflag;
    synth_reset();
#ifdef __N64__
    /* Alternate waveform identities between songs. Libdragon intentionally
     * retains a channel's sample cache when the same waveform pointer is
     * replayed; using two descriptors prevents cached samples from the prior
     * MIDI song leaking into the beginning of a newly selected song. */
    midi_wave_index ^= 1;
    midi_waves[midi_wave_index].len = (int)seq_total_samples;
    mixer_ch_play(ROTT64_MUSIC_CHANNEL, &midi_waves[midi_wave_index]);
#endif
    current_open = 1;
    current_paused = 0;
    paused_sample_position = 0.0f;
    apply_music_volume();
    return MUSIC_Ok;
}

void MUSIC_SetSongTime(unsigned long milliseconds)
{
    uint32_t position;
    if (!current_open) return;
    position = (uint32_t)(((uint64_t)milliseconds * ROTT64_MIDI_RATE) / 1000u);
    if (position > seq_total_samples) position = seq_total_samples;
#ifdef __N64__
    if (current_paused) paused_sample_position = (float)position;
    else mixer_ch_set_pos(ROTT64_MUSIC_CHANNEL, (float)position);
#endif
}

void MUSIC_GetSongPosition(songposition *position)
{
    float samples = 0.0f;
    if (!position) return;
    memset(position, 0, sizeof(*position));
    if (!current_open) return;
#ifdef __N64__
    samples = current_paused ? paused_sample_position : mixer_ch_get_pos(ROTT64_MUSIC_CHANNEL);
#endif
    if (samples > 0.0f)
        position->milliseconds = (unsigned long)((samples * 1000.0f) / ROTT64_MIDI_RATE);
}

void rott64_music_pump(void)
{
#ifdef __N64__
    if (!current_open || current_paused || music_loopflag != MUSIC_LoopSong) return;
    if (!mixer_ch_playing(ROTT64_MUSIC_CHANNEL)) {
        synth_reset();
        mixer_ch_play(ROTT64_MUSIC_CHANNEL, &midi_waves[midi_wave_index]);
        mixer_ch_set_pos(ROTT64_MUSIC_CHANNEL, 0.0f);
        apply_music_volume();
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
