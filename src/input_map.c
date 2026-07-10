#include "input_map.h"

#include <stddef.h>

#define ROTT64_STICK_DEADZONE 8

static int16_t apply_deadzone(int8_t value)
{
    const int16_t widened = value;
    if (widened > -ROTT64_STICK_DEADZONE && widened < ROTT64_STICK_DEADZONE) {
        return 0;
    }
    return widened;
}

void rott64_map_controller(
    const rott64_controller_state_t *controller,
    rott64_input_frame_t *frame
)
{
    uint32_t actions = 0U;

    if (controller == NULL || frame == NULL) {
        return;
    }

    frame->move = apply_deadzone(controller->stick_y);
    frame->turn = apply_deadzone(controller->stick_x);

    /* N64 FPS-style digital movement: C-buttons mirror the analog stick. */
    if (controller->c_up) {
        frame->move = 80;
    } else if (controller->c_down) {
        frame->move = -80;
    }

    if (controller->c_left) {
        frame->turn = -80;
    } else if (controller->c_right) {
        frame->turn = 80;
    }

    if (controller->z) {
        actions |= ROTT64_ACTION_FIRE;
    }
    if (controller->a) {
        actions |= ROTT64_ACTION_USE;
    }
    if (controller->b) {
        actions |= ROTT64_ACTION_RUN;
    }
    if (controller->start) {
        actions |= ROTT64_ACTION_PAUSE;
    }
    if (controller->r) {
        actions |= ROTT64_ACTION_NEXT_WEAPON;
    }
    if (controller->l) {
        actions |= ROTT64_ACTION_PREVIOUS_WEAPON;
    }
    /* The D-pad now carries the former C-button action group. */
    if (controller->d_left) {
        actions |= ROTT64_ACTION_STRAFE_LEFT;
    }
    if (controller->d_right) {
        actions |= ROTT64_ACTION_STRAFE_RIGHT;
    }
    if (controller->d_up) {
        actions |= ROTT64_ACTION_LOOK_UP;
    }
    if (controller->d_down) {
        actions |= ROTT64_ACTION_LOOK_DOWN;
    }

    frame->actions = actions;
}
