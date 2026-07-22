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




static uint16_t rgba5551(SDL_Color color)
{
    const uint16_t r = (uint16_t)(color.r >> 3);
    const uint16_t g = (uint16_t)(color.g >> 3);
    const uint16_t b = (uint16_t)(color.b >> 3);
    return (uint16_t)((r << 11) | (g << 6) | (b << 1) | 1u);
}

/* ROTT64_HW2_PRESENT_FORWARD_DECL_FIX */
static int rott64_hw2_present(surface_t *fb);

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
    if (!rott64_hw2_present(surface))
        display_show(surface);
#else
    (void)rgba5551;
#endif
}

SDL_Window *VL_GetVideoWindow(void) { return NULL; }
SDL_Surface *VL_GetVideoSurface(void) { return sdl_surface; }


/* ROTT64_HW2B_EXACT_SPANS_PLATFORM_BEGIN
 *
 * R48 draws the exact dc_yl/dc_yh ranges used by every real wall-column draw.
 * A screen column can have two disjoint wall pieces; they stay disjoint here.
 *
 * CPU walls remain enabled for this diagnostic. The RDP overlay still occurs
 * during final presentation, so it can paint over software sprites/weapon.
 * That known compositing-order problem is separate from span geometry.
 */
#define ROTT64_HW2_MAX_WALLS 640

extern volatile unsigned int rott64_hw2_wall_seq;
extern volatile int rott64_hw2_wall_count;
extern volatile int rott64_hw2_viewwidth;
extern volatile int rott64_hw2_viewheight;
extern volatile int rott64_hw2_screenheight;
extern volatile unsigned char rott64_hw2_wall_segments[ROTT64_HW2_MAX_WALLS];
extern volatile short rott64_hw2_wall_top[ROTT64_HW2_MAX_WALLS];
extern volatile short rott64_hw2_wall_bottom[ROTT64_HW2_MAX_WALLS];
extern volatile short rott64_hw2_wall_top2[ROTT64_HW2_MAX_WALLS];
extern volatile short rott64_hw2_wall_bottom2[ROTT64_HW2_MAX_WALLS];
extern volatile unsigned char rott64_hw2_wall_color[ROTT64_HW2_MAX_WALLS];

static unsigned int rott64_hw2_seen_seq = 0;
static unsigned int rott64_hw2_frames = 0;
static int rott64_hw2_rdp_ready = 0;

static color_t rott64_hw2_color(unsigned int n)
{
    switch (n & 7u)
    {
        case 0: return RGBA32(214, 67, 59, 255);
        case 1: return RGBA32(54, 119, 191, 255);
        case 2: return RGBA32(205, 160, 50, 255);
        case 3: return RGBA32(66, 154, 91, 255);
        case 4: return RGBA32(145, 83, 173, 255);
        case 5: return RGBA32(203, 104, 46, 255);
        case 6: return RGBA32(61, 160, 164, 255);
        default: return RGBA32(170, 170, 170, 255);
    }
}

static void rott64_hw2_draw_span(
    surface_t *fb,
    int column,
    int viewwidth,
    int screenheight,
    int top,
    int bottom
)
{
    int x0, x1, y0, y1;

    if (top < 0) top = 0;
    if (bottom > screenheight) bottom = screenheight;
    if (bottom <= top) return;

    x0 = (column * (int)fb->width) / viewwidth;
    x1 = ((column + 1) * (int)fb->width) / viewwidth;
    if (x0 < 0) x0 = 0;
    if (x1 > (int)fb->width) x1 = (int)fb->width;
    if (x1 <= x0) return;

    y0 = (top * (int)fb->height) / screenheight;
    y1 = (bottom * (int)fb->height) / screenheight;
    if (y0 < 0) y0 = 0;
    if (y1 > (int)fb->height) y1 = (int)fb->height;
    if (y1 <= y0) return;

    rdpq_fill_rectangle(x0, y0, x1, y1);
}

static int rott64_hw2_present(surface_t *fb)
{
    unsigned int seq;
    int count, vw, vh, sh, i, last_color;

    if (fb == NULL)
        return 0;

    seq = rott64_hw2_wall_seq;
    if (seq == 0u || seq == rott64_hw2_seen_seq)
        return 0;

    if (rott64_hw2_frames >= 900u)
    {
        rott64_hw2_seen_seq = seq;
        return 0;
    }

    count = rott64_hw2_wall_count;
    vw = rott64_hw2_viewwidth;
    vh = rott64_hw2_viewheight;
    sh = rott64_hw2_screenheight;

    if (count <= 0 ||
        count > ROTT64_HW2_MAX_WALLS ||
        vw <= 0 ||
        vw > ROTT64_HW2_MAX_WALLS ||
        vh <= 0 ||
        sh <= 0 ||
        vh > sh)
    {
        rott64_hw2_seen_seq = seq;
        return 0;
    }

    if (count > vw)
        count = vw;

    if (!rott64_hw2_rdp_ready)
    {
        rdpq_init();
        rott64_hw2_rdp_ready = 1;
    }

    rdpq_attach(fb, NULL);
    last_color = -1;

    for (i = 0; i < count; ++i)
    {
        int segments = (int)rott64_hw2_wall_segments[i];
        int color_index;

        if (segments <= 0)
            continue;
        if (segments > 2)
            segments = 2;

        color_index = (int)(rott64_hw2_wall_color[i] & 7u);

        if (last_color < 0)
        {
            rdpq_set_mode_fill(
                rott64_hw2_color((unsigned int)color_index)
            );
            last_color = color_index;
        }
        else if (color_index != last_color)
        {
            rdpq_set_fill_color(
                rott64_hw2_color((unsigned int)color_index)
            );
            last_color = color_index;
        }

        rott64_hw2_draw_span(
            fb, i, vw, sh,
            (int)rott64_hw2_wall_top[i],
            (int)rott64_hw2_wall_bottom[i]
        );

        if (segments >= 2)
        {
            rott64_hw2_draw_span(
                fb, i, vw, sh,
                (int)rott64_hw2_wall_top2[i],
                (int)rott64_hw2_wall_bottom2[i]
            );
        }
    }

    rdpq_detach_show();
    rott64_hw2_seen_seq = seq;
    rott64_hw2_frames++;
    return 1;
}
/* ROTT64_HW2B_EXACT_SPANS_PLATFORM_END */


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
