/* ROTT64 replacement for Taradino's SDL-backed modexlib.c. */
#include "modexlib.h"
#include "SDL.h"
#include "n64_platform.h"

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#ifdef __N64__
#include <libdragon.h>
#endif

#define ROTT_WIDTH 320
#define ROTT_HEIGHT 200
#define N64_HEIGHT 240
#define BORDER_Y 20

boolean StretchScreen = 0;
byte *iG_buf_center;
int linewidth;
int ylookup[600];
byte *SCREEN_BUFFER;
int screensize;
byte *bufferofs;
byte *displayofs;
boolean graphicsmode = false;
byte *bufofsTopLimit;
byte *bufofsBottomLimit;

SDL_Surface *sdl_surface = NULL;
SDL_Surface *unstretch_sdl_surface = NULL;

static byte indexed_framebuffer[ROTT_WIDTH * ROTT_HEIGHT] __attribute__((aligned(16)));
static byte split_view_framebuffer[2][ROTT_WIDTH * ROTT_HEIGHT] __attribute__((aligned(16)));
static bool split_view_valid[2];
static SDL_Color palette_colors[256];
static SDL_Palette framebuffer_palette = {256, palette_colors, 0, 1};
static SDL_PixelFormat framebuffer_format = {0, &framebuffer_palette, 8, 1};
static SDL_Surface framebuffer_surface = {0, &framebuffer_format, ROTT_WIDTH, ROTT_HEIGHT, ROTT_WIDTH, indexed_framebuffer};
static bool display_ready;

extern int iG_X_center;
extern int iG_Y_center;


void n64_platform_capture_split_view(unsigned player_index, const uint8_t *pixels, size_t size)
{
    if (player_index >= 2u || pixels == NULL || size < (size_t)(ROTT_WIDTH * ROTT_HEIGHT))
        return;
    memcpy(split_view_framebuffer[player_index], pixels,
           (size_t)(ROTT_WIDTH * ROTT_HEIGHT));
    split_view_valid[player_index] = true;
}

static uint8_t apply_brightness(uint8_t value)
{
    int level = n64_platform_brightness();
    int adjusted = (int)value + level * 24;
    if (adjusted < 0) adjusted = 0;
    if (adjusted > 255) adjusted = 255;
    return (uint8_t)adjusted;
}

static uint16_t rgba5551(SDL_Color color)
{
    const uint16_t r = (uint16_t)(apply_brightness(color.r) >> 3);
    const uint16_t g = (uint16_t)(apply_brightness(color.g) >> 3);
    const uint16_t b = (uint16_t)(apply_brightness(color.b) >> 3);
    return (uint16_t)((r << 11) | (g << 6) | (b << 1) | 1u);
}

static void present_frame(void)
{
#ifdef __N64__
    surface_t *surface;
    uint16_t converted[256];
    int y;

    if (!display_ready) {
        return;
    }
    for (int i = 0; i < 256; ++i) {
        converted[i] = rgba5551(palette_colors[i]);
    }

    surface = display_get();
    if (surface == NULL) {
        return;
    }

    {
        uint16_t *destination = (uint16_t *)surface->buffer;
        const int destination_stride = surface->stride / (int)sizeof(uint16_t);
        for (y = 0; y < N64_HEIGHT; ++y) {
            uint16_t *row = destination + y * destination_stride;
            int source_y;
            if (n64_platform_aspect_mode() == ROTT64_ASPECT_4_3) {
                /* Expand the DOS 320x200 picture to 320x240, restoring the
                   intended 4:3 display aspect on N64 output. */
                source_y = (y * ROTT_HEIGHT) / N64_HEIGHT;
            } else {
                if (y < BORDER_Y || y >= BORDER_Y + ROTT_HEIGHT) {
                    memset(row, 0, ROTT_WIDTH * sizeof(*row));
                    continue;
                }
                source_y = y - BORDER_Y;
            }
            {
                const byte *source;
                if (n64_platform_split_commbat_requested() &&
                    split_view_valid[0] && split_view_valid[1]) {
                    unsigned view = y < (N64_HEIGHT / 2) ? 0u : 1u;
                    int local_y = y < (N64_HEIGHT / 2) ? y : y - (N64_HEIGHT / 2);
                    int split_source_y = (local_y * ROTT_HEIGHT) / (N64_HEIGHT / 2);
                    source = split_view_framebuffer[view] + split_source_y * ROTT_WIDTH;
                } else {
                    source = indexed_framebuffer + source_y * ROTT_WIDTH;
                }
                for (int x = 0; x < ROTT_WIDTH; ++x) {
                    row[x] = converted[source[x]];
                }
            }
        }
    }
    display_show(surface);
#else
    (void)rgba5551;
#endif
}

SDL_Window *VL_GetVideoWindow(void) { return NULL; }
SDL_Surface *VL_GetVideoSurface(void) { return sdl_surface; }
int VL_SaveBMP(const char *file) { (void)file; return -1; }
void SetShowCursor(int show) { (void)show; }

void GraphicsMode(void)
{
    n64_platform_init();
#ifdef __N64__
    if (!display_ready) {
        display_init(RESOLUTION_320x240, DEPTH_16_BPP, 2, GAMMA_NONE,
            n64_platform_filter_mode() == ROTT64_FILTER_ENHANCED ?
                FILTERS_RESAMPLE_ANTIALIAS_DEDITHER : FILTERS_RESAMPLE);
        display_ready = true;
    }
#else
    display_ready = true;
#endif
    sdl_surface = &framebuffer_surface;
    graphicsmode = true;
}

void ToggleFullScreen(void) { }
void SetTextMode(void) { }
void TurnOffTextCursor(void) { }
void WaitVBL(void) { n64_platform_wait_ms(14); }

void VL_SetVGAPlaneMode(void)
{
    int offset = 0;
    GraphicsMode();
    linewidth = ROTT_WIDTH;
    for (int i = 0; i < 600; ++i) {
        ylookup[i] = offset;
        if (i < ROTT_HEIGHT) {
            offset += linewidth;
        }
    }
    screensize = ROTT_WIDTH * ROTT_HEIGHT;
    SCREEN_BUFFER = displayofs = bufferofs = indexed_framebuffer;
    iG_X_center = ROTT_WIDTH / 2;
    iG_Y_center = ROTT_HEIGHT / 2 + 10;
    iG_buf_center = bufferofs + screensize / 2;
    bufofsTopLimit = bufferofs + screensize - ROTT_WIDTH;
    bufofsBottomLimit = bufferofs + ROTT_WIDTH;
    StretchScreen = 0;
    memset(indexed_framebuffer, 0, sizeof(indexed_framebuffer));
    XFlipPage();
}

void VL_CopyPlanarPage(byte *src, byte *dest) { memcpy(dest, src, (size_t)screensize); }
void VL_CopyPlanarPageToMemory(byte *src, byte *dest) { memcpy(dest, src, (size_t)screensize); }
void VL_ClearBuffer(byte *buf, byte color) { memset(buf, color, (size_t)screensize); }
void VL_ClearVideo(byte color) { memset(indexed_framebuffer, color, sizeof(indexed_framebuffer)); }
void VH_UpdateScreen(void) { present_frame(); }
void XFlipPage(void) { present_frame(); }
void EnableScreenStretch(void) { StretchScreen = 0; }
void DisableScreenStretch(void) { StretchScreen = 0; }
void DrawCenterAim(void) { }
