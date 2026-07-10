#include "indexed_video.h"
#include "input_map.h"

#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

static void test_palette_and_framebuffer(void)
{
    uint8_t palette[ROTT_VIDEO_PALETTE_BYTES] = {0};
    uint16_t converted[ROTT_VIDEO_PALETTE_ENTRIES] = {0};
    uint8_t *indexed = calloc(ROTT_VIDEO_WIDTH * ROTT_VIDEO_HEIGHT, 1U);
    uint16_t *output = calloc(ROTT_VIDEO_WIDTH * ROTT_VIDEO_OUTPUT_HEIGHT, sizeof(uint16_t));

    assert(indexed != NULL && output != NULL);
    palette[3U] = 63U;
    palette[4U] = 0U;
    palette[5U] = 0U;
    indexed[0] = 1U;

    assert(rott_video_build_palette(palette, sizeof(palette), converted, ROTT_VIDEO_PALETTE_ENTRIES));
    assert(converted[0] == 1U);
    assert(converted[1] == 0xF801U);
    assert(rott_video_expand_320x200(
        indexed,
        ROTT_VIDEO_WIDTH,
        converted,
        0x1235U,
        output,
        ROTT_VIDEO_WIDTH,
        ROTT_VIDEO_OUTPUT_HEIGHT));
    assert(output[0] == 0x1235U);
    assert(output[(ROTT_VIDEO_BORDER_ROWS * ROTT_VIDEO_WIDTH)] == 0xF801U);
    assert(output[((ROTT_VIDEO_OUTPUT_HEIGHT - 1U) * ROTT_VIDEO_WIDTH)] == 0x1235U);

    free(output);
    free(indexed);
}

static void test_input_mapping(void)
{
    rott64_controller_state_t controller;
    rott64_input_frame_t frame;

    memset(&controller, 0, sizeof(controller));
    memset(&frame, 0, sizeof(frame));
    controller.stick_x = 4;
    controller.stick_y = 50;
    controller.z = true;
    controller.a = true;
    controller.r = true;
    controller.d_left = true;

    rott64_map_controller(&controller, &frame);
    assert(frame.turn == 0);
    assert(frame.move == 50);
    assert((frame.actions & ROTT64_ACTION_FIRE) != 0U);
    assert((frame.actions & ROTT64_ACTION_USE) != 0U);
    assert((frame.actions & ROTT64_ACTION_NEXT_WEAPON) != 0U);
    assert((frame.actions & ROTT64_ACTION_STRAFE_LEFT) != 0U);

    controller.d_left = false;
    controller.c_down = true;
    controller.c_right = true;
    rott64_map_controller(&controller, &frame);
    assert(frame.move == -80);
    assert(frame.turn == 80);

    memset(&controller, 0, sizeof(controller));
    memset(&frame, 0, sizeof(frame));
    controller.d_up = true;
    controller.d_right = true;
    rott64_map_controller(&controller, &frame);
    assert((frame.actions & ROTT64_ACTION_LOOK_UP) != 0U);
    assert((frame.actions & ROTT64_ACTION_STRAFE_RIGHT) != 0U);
}

int main(void)
{
    test_palette_and_framebuffer();
    test_input_mapping();
    puts("Indexed video and controller mapping host tests passed");
    return 0;
}
