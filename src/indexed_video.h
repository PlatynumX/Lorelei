#ifndef ROTT64_INDEXED_VIDEO_H
#define ROTT64_INDEXED_VIDEO_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define ROTT_VIDEO_WIDTH 320U
#define ROTT_VIDEO_HEIGHT 200U
#define ROTT_VIDEO_OUTPUT_HEIGHT 240U
#define ROTT_VIDEO_BORDER_ROWS 20U
#define ROTT_VIDEO_PALETTE_ENTRIES 256U
#define ROTT_VIDEO_PALETTE_BYTES (ROTT_VIDEO_PALETTE_ENTRIES * 3U)

uint16_t rott_video_vga6_to_rgba5551(uint8_t red, uint8_t green, uint8_t blue);

bool rott_video_build_palette(
    const uint8_t *vga_palette,
    size_t palette_size,
    uint16_t *rgba5551,
    size_t color_capacity
);

bool rott_video_expand_320x200(
    const uint8_t *indexed_pixels,
    size_t indexed_stride,
    const uint16_t *rgba5551,
    uint16_t border_color,
    uint16_t *output_pixels,
    size_t output_stride,
    size_t output_height
);

#endif
