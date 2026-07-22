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
static SDL_Color palette_colors[256];
static SDL_Palette framebuffer_palette = {256, palette_colors, 0, 1};
static SDL_PixelFormat framebuffer_format = {0, &framebuffer_palette, 8, 1};
static SDL_Surface framebuffer_surface = {0, &framebuffer_format, ROTT_WIDTH, ROTT_HEIGHT, ROTT_WIDTH, indexed_framebuffer};
static bool display_ready;

extern int iG_X_center;
extern int iG_Y_center;

/* ROTT64_HW1_V4_CLEAN_R45D_BEGIN
 * R46 HW1 v4: direct N64 RDP framebuffer proof.
 *
 * Built fresh from the exact preserved R45d baseline.
 * For the first 180 presented frames, RDPQ draws a live flat-shaded room
 * directly into the framebuffer already acquired by the existing N64
 * display backend. After frame 180, the normal R45d software presentation
 * path resumes automatically.
 */
static unsigned int rott64_hw1_v4_frame = 0;
static int rott64_hw1_v4_rdp_initialized = 0;

static void rott64_hw1_v4_quad(float x0, float y0,
                               float x1, float y1,
                               float x2, float y2,
                               float x3, float y3)
{
    float a[2] = { x0, y0 };
    float b[2] = { x1, y1 };
    float c[2] = { x2, y2 };
    float d[2] = { x3, y3 };

    rdpq_triangle(&TRIFMT_FILL, a, b, c);
    rdpq_triangle(&TRIFMT_FILL, a, c, d);
}

static void rott64_hw1_v4_color(int r, int g, int b)
{
    rdpq_set_prim_color(RGBA32(r, g, b, 255));
}

static int rott64_hw1_v4_present(surface_t *fb)
{
    float w;
    float h;
    float shift;
    float bx0;
    float bx1;
    float by0;
    float by1;
    unsigned int phase;

    if (fb == NULL || rott64_hw1_v4_frame >= 180u)
        return 0;

    if (!rott64_hw1_v4_rdp_initialized)
    {
        rdpq_init();
        rott64_hw1_v4_rdp_initialized = 1;
    }

    w = (float)fb->width;
    h = (float)fb->height;

    phase = rott64_hw1_v4_frame % 120u;
    shift = (float)(
        (phase < 60u)
            ? ((int)phase - 30)
            : (90 - (int)phase)
    ) * (w / 320.0f);

    bx0 = w * 0.29f + shift;
    bx1 = w * 0.71f + shift;
    by0 = h * 0.23f;
    by1 = h * 0.76f;

    rdpq_attach(fb, NULL);
    rdpq_clear(RGBA32(8, 10, 18, 255));
    rdpq_set_mode_standard();
    rdpq_mode_combiner(RDPQ_COMBINER_FLAT);

    rott64_hw1_v4_color(38, 43, 58);
    rott64_hw1_v4_quad(
        0.0f, 0.0f,
        w, 0.0f,
        bx1, by0,
        bx0, by0
    );

    rott64_hw1_v4_color(55, 48, 39);
    rott64_hw1_v4_quad(
        bx0, by1,
        bx1, by1,
        w, h,
        0.0f, h
    );

    rott64_hw1_v4_color(115, 47, 43);
    rott64_hw1_v4_quad(
        0.0f, 0.0f,
        bx0, by0,
        bx0, by1,
        0.0f, h
    );

    rott64_hw1_v4_color(45, 70, 105);
    rott64_hw1_v4_quad(
        bx1, by0,
        w, 0.0f,
        w, h,
        bx1, by1
    );

    rott64_hw1_v4_color(82, 83, 79);
    rott64_hw1_v4_quad(
        bx0, by0,
        bx1, by0,
        bx1, by1,
        bx0, by1
    );

    rott64_hw1_v4_color(101, 67, 41);
    rott64_hw1_v4_quad(
        w * 0.455f + shift, h * 0.43f,
        w * 0.565f + shift, h * 0.43f,
        w * 0.565f + shift, by1,
        w * 0.455f + shift, by1
    );

    rott64_hw1_v4_color(220, 193, 68);
    rott64_hw1_v4_quad(
        w * 0.08f + (float)phase * (w / 180.0f), h * 0.88f,
        w * 0.13f + (float)phase * (w / 180.0f), h * 0.88f,
        w * 0.13f + (float)phase * (w / 180.0f), h * 0.92f,
        w * 0.08f + (float)phase * (w / 180.0f), h * 0.92f
    );

    rdpq_detach_show();
    rott64_hw1_v4_frame++;
    return 1;
}
/* ROTT64_HW1_V4_CLEAN_R45D_END */


static uint16_t rgba5551(SDL_Color color)
{
    const uint16_t r = (uint16_t)(color.r >> 3);
    const uint16_t g = (uint16_t)(color.g >> 3);
    const uint16_t b = (uint16_t)(color.b >> 3);
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
            if (y < BORDER_Y || y >= BORDER_Y + ROTT_HEIGHT) {
                memset(row, 0, ROTT_WIDTH * sizeof(*row));
            } else {
                const byte *source = indexed_framebuffer + (y - BORDER_Y) * ROTT_WIDTH;
                for (int x = 0; x < ROTT_WIDTH; ++x) {
                    row[x] = converted[source[x]];
                }
            }
        }
    }
    if (!rott64_hw1_v4_present(surface))
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
        display_init(RESOLUTION_320x240, DEPTH_16_BPP, 2, GAMMA_NONE, FILTERS_RESAMPLE);
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
