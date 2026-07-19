#ifndef ROTT64_N64_PLATFORM_H
#define ROTT64_N64_PLATFORM_H

#include <stdbool.h>
#include <stdint.h>

typedef enum {
    ROTT64_DATA_SHAREWARE = 0,
    ROTT64_DATA_FULL = 1,
    ROTT64_DATA_CUSTOM = 2
} rott64_data_mode_t;

void n64_platform_init(void);
void n64_platform_fatal(const char *message);
uint64_t n64_platform_ticks_ms(void);
void n64_platform_wait_ms(uint32_t milliseconds);
void n64_platform_poll(void);
void n64_platform_rumble_pulse(uint32_t duration_ms, uint8_t strength);
void n64_platform_rumble_stop(void);
void n64_platform_rumble_note_fire(void);
void n64_platform_rumble_nearby_audio(unsigned total, unsigned spread);
rott64_data_mode_t n64_platform_data_mode(void);
const char *n64_platform_custom_content(void);

typedef enum {
    ROTT64_FILTER_STANDARD = 0,
    ROTT64_FILTER_ENHANCED = 1
} rott64_filter_mode_t;

typedef enum {
    ROTT64_ASPECT_ORIGINAL = 0,
    ROTT64_ASPECT_4_3 = 1
} rott64_aspect_mode_t;

rott64_filter_mode_t n64_platform_filter_mode(void);
rott64_aspect_mode_t n64_platform_aspect_mode(void);
int n64_platform_brightness(void);

typedef enum {
    ROTT64_CONTROL_CLASSIC = 0,
    ROTT64_CONTROL_MOUSELOOK = 1
} rott64_control_mode_t;

rott64_control_mode_t n64_platform_control_mode(void);
int n64_platform_look_sensitivity(void);
int n64_platform_look_deadzone(void);
bool n64_platform_invert_y(void);

#endif
