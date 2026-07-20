#ifndef ROTT64_N64_PLATFORM_H
#define ROTT64_N64_PLATFORM_H

#include <stdbool.h>
#include <stdint.h>
#include <stddef.h>

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

typedef enum {
    ROTT64_PAD_A = 0,
    ROTT64_PAD_B,
    ROTT64_PAD_Z,
    ROTT64_PAD_START,
    ROTT64_PAD_L,
    ROTT64_PAD_R,
    ROTT64_PAD_C_UP,
    ROTT64_PAD_C_DOWN,
    ROTT64_PAD_C_LEFT,
    ROTT64_PAD_C_RIGHT,
    ROTT64_PAD_D_UP,
    ROTT64_PAD_D_DOWN,
    ROTT64_PAD_D_LEFT,
    ROTT64_PAD_D_RIGHT,
    ROTT64_PAD_BUTTON_COUNT
} rott64_pad_button_t;

typedef enum {
    ROTT64_ACTION_FORWARD = 0,
    ROTT64_ACTION_BACKWARD,
    ROTT64_ACTION_TURN_LEFT,
    ROTT64_ACTION_TURN_RIGHT,
    ROTT64_ACTION_FIRE,
    ROTT64_ACTION_CONFIRM,
    ROTT64_ACTION_RUN,
    ROTT64_ACTION_MENU,
    ROTT64_ACTION_WEAPON_1,
    ROTT64_ACTION_WEAPON_2,
    ROTT64_ACTION_STRAFE_LEFT,
    ROTT64_ACTION_STRAFE_RIGHT,
    ROTT64_ACTION_USE,
    ROTT64_ACTION_TURN_180,
    ROTT64_ACTION_COUNT
} rott64_control_action_t;

rott64_control_mode_t n64_platform_control_mode_for_player(unsigned player_index);
int n64_platform_look_sensitivity_for_player(unsigned player_index);
int n64_platform_look_deadzone_for_player(unsigned player_index);
bool n64_platform_invert_y_for_player(unsigned player_index);
rott64_pad_button_t n64_platform_binding_for_action(unsigned player_index, rott64_control_action_t action);

bool n64_platform_second_controller_connected(void);
bool n64_platform_split_commbat_requested(void);

void n64_platform_set_local_input_player(unsigned player_index);
unsigned n64_platform_local_input_player(void);
void n64_platform_capture_split_view(unsigned player_index, const uint8_t *pixels, size_t size);

#endif
