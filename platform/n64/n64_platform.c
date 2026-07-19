#include "n64_platform.h"
#include <stdio.h>
#include <stdlib.h>
#ifdef __N64__
#include <libdragon.h>
#endif

static bool initialized;

#ifdef __N64__
static bool boot_display_ready;

static void boot_display_open(void)
{
    if (boot_display_ready) return;
    display_init(RESOLUTION_320x240, DEPTH_16_BPP, 2, GAMMA_NONE, FILTERS_RESAMPLE);
    graphics_set_default_font();
    boot_display_ready = true;
}

static void boot_display_show(const char *stage)
{
    surface_t *surface;
    boot_display_open();
    surface = display_get();
    graphics_fill_screen(surface, graphics_make_color(0, 0, 32, 255));
    graphics_set_color(
        graphics_make_color(255, 255, 255, 255),
        graphics_make_color(0, 0, 0, 0)
    );
    graphics_draw_text(surface, 16, 24, "ROTT64 SHAREWARE");
    graphics_draw_text(surface, 16, 64, stage ? stage : "Starting...");
    display_show(surface);
}

static void boot_display_close(void)
{
    if (!boot_display_ready) return;
    display_close();
    boot_display_ready = false;
}
#endif

void n64_platform_init(void)
{
    if (initialized) return;
#ifdef __N64__
    FILE *wad;

    boot_display_show("Stage 1/4: entered N64 main()");
    for (volatile uint32_t i = 0; i < 20000000u; ++i) __asm__ volatile("nop");

    timer_init();
    boot_display_show("Stage 2/4: timer initialized");
    wait_ms(750);

    joypad_init();
    if (dfs_init(DFS_DEFAULT_LOCATION) != DFS_ESUCCESS)
        n64_platform_fatal("Stage 3 failed: DragonFS mount error");
    boot_display_show("Stage 3/4: DragonFS mounted");
    wait_ms(750);

    if (!is_memory_expanded()) {
        char message[128];
        snprintf(message, sizeof(message),
            "Expansion Pak required.\nDetected: %d MiB",
            get_memory_size() / (1024 * 1024));
        n64_platform_fatal(message);
    }

    wad = fopen("rom://rott/HUNTBGIN.WAD", "rb");
    if (wad == NULL)
        n64_platform_fatal("Stage 4 failed: HUNTBGIN.WAD not found\nExpected rom://rott/HUNTBGIN.WAD");
    fclose(wad);

    boot_display_show("Stage 4/4: shareware WAD found\nStarting Taradino...");
    wait_ms(1500);
    boot_display_close();
#endif
    initialized = true;
}

void n64_platform_fatal(const char *message)
{
#ifdef __N64__
    boot_display_show(message ? message : "ROTT64 fatal error");
    for (;;) wait_ms(1000);
#else
    fprintf(stderr, "%s\n", message ? message : "ROTT64 fatal error");
    abort();
#endif
}

uint64_t n64_platform_ticks_ms(void)
{
#ifdef __N64__
    return (uint64_t)get_ticks_ms();
#else
    static uint64_t mock_ticks;
    return mock_ticks++;
#endif
}

void n64_platform_wait_ms(uint32_t milliseconds)
{
#ifdef __N64__
    wait_ms(milliseconds);
#else
    (void)milliseconds;
#endif
}

void n64_platform_poll(void)
{
#ifdef __N64__
    joypad_poll();
#endif
}
