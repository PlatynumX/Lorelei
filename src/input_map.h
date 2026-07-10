#ifndef ROTT64_INPUT_MAP_H
#define ROTT64_INPUT_MAP_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    int8_t stick_x;
    int8_t stick_y;
    bool a;
    bool b;
    bool z;
    bool start;
    bool l;
    bool r;
    bool c_up;
    bool c_down;
    bool c_left;
    bool c_right;
    bool d_up;
    bool d_down;
    bool d_left;
    bool d_right;
} rott64_controller_state_t;

typedef enum {
    ROTT64_ACTION_FIRE = 1U << 0U,
    ROTT64_ACTION_USE = 1U << 1U,
    ROTT64_ACTION_RUN = 1U << 2U,
    ROTT64_ACTION_PAUSE = 1U << 3U,
    ROTT64_ACTION_NEXT_WEAPON = 1U << 4U,
    ROTT64_ACTION_PREVIOUS_WEAPON = 1U << 5U,
    ROTT64_ACTION_STRAFE_LEFT = 1U << 6U,
    ROTT64_ACTION_STRAFE_RIGHT = 1U << 7U,
    ROTT64_ACTION_LOOK_UP = 1U << 8U,
    ROTT64_ACTION_LOOK_DOWN = 1U << 9U
} rott64_action_t;

typedef struct {
    int16_t move;
    int16_t turn;
    uint32_t actions;
} rott64_input_frame_t;

void rott64_map_controller(
    const rott64_controller_state_t *controller,
    rott64_input_frame_t *frame
);

#endif
