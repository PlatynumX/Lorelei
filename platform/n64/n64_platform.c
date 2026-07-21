#include "n64_platform.h"
#include <stdio.h>
#include <stdlib.h>
#ifdef __N64__
#include <libdragon.h>
#endif

static bool initialized;

#ifdef __N64__
static bool boot_display_ready;
static uint64_t rumble_until_ms;
static uint64_t rumble_started_ms;
static uint8_t rumble_strength;
static bool rumble_output_active;

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
    graphics_draw_text(surface, 16, 24, "ROTT64 DARK WAR");
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

    boot_display_show("Stage 1/6: entered N64 main()");
    for (volatile uint32_t i = 0; i < 20000000u; ++i) __asm__ volatile("nop");

    timer_init();
    boot_display_show("Stage 2/6: timer initialized");
    wait_ms(750);

    joypad_init();
    if (dfs_init(DFS_DEFAULT_LOCATION) != DFS_ESUCCESS)
        n64_platform_fatal("Stage 3 failed: DragonFS mount error");
    boot_display_show("Stage 3/6: DragonFS mounted");
    wait_ms(750);

    if (!is_memory_expanded()) {
        char message[128];
        snprintf(message, sizeof(message),
            "Expansion Pak required.\nDetected: %d MiB",
            get_memory_size() / (1024 * 1024));
        n64_platform_fatal(message);
    }

    wad = fopen("rom://rott/DARKWAR.WAD", "rb");
    if (wad == NULL)
        n64_platform_fatal("Stage 4 failed: DARKWAR.WAD not found\nExpected rom://rott/DARKWAR.WAD");
    fclose(wad);
    boot_display_show("Stage 4/6: DARKWAR.WAD found");
    wait_ms(500);

    wad = fopen("rom://rott/DARKWAR.RTL", "rb");
    if (wad == NULL)
        n64_platform_fatal("Stage 5 failed: DARKWAR.RTL not found\nExpected rom://rott/DARKWAR.RTL");
    fclose(wad);
    boot_display_show("Stage 5/6: DARKWAR.RTL found");
    wait_ms(500);

    wad = fopen("rom://rott/DARKWAR.RTC", "rb");
    if (wad == NULL)
        n64_platform_fatal("Stage 6 failed: DARKWAR.RTC not found\nExpected rom://rott/DARKWAR.RTC");
    fclose(wad);

    boot_display_show("Stage 6/6: Dark War data found\nStarting Taradino...");
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

void n64_platform_rumble_pulse(uint32_t duration_ms, uint8_t strength)
{
#ifdef __N64__
    uint64_t now;
    uint64_t requested_until;

    if (duration_ms == 0u || strength == 0u || !joypad_get_rumble_supported(JOYPAD_PORT_1)) {
        return;
    }

    now = (uint64_t)get_ticks_ms();
    requested_until = now + (uint64_t)duration_ms;
    if (requested_until > rumble_until_ms) {
        rumble_until_ms = requested_until;
    }
    if (rumble_until_ms <= now || rumble_started_ms == 0u) {
        rumble_started_ms = now;
    }
    if (strength > rumble_strength) {
        rumble_strength = strength;
    }
#else
    (void)duration_ms;
    (void)strength;
#endif
}

void n64_platform_rumble_stop(void)
{
#ifdef __N64__
    rumble_until_ms = 0u;
    rumble_started_ms = 0u;
    rumble_strength = 0u;
    if (rumble_output_active && joypad_get_rumble_supported(JOYPAD_PORT_1)) {
        joypad_set_rumble_active(JOYPAD_PORT_1, false);
    }
    rumble_output_active = false;
#endif
}

void n64_platform_poll(void)
{
#ifdef __N64__
    uint64_t now;
    bool desired = false;

    joypad_poll();
    now = (uint64_t)get_ticks_ms();

    if (rumble_until_ms > now && joypad_get_rumble_supported(JOYPAD_PORT_1)) {
        /* N64 Rumble Pak is binary, so approximate intensity with a short
           16 ms duty-cycle window. Strong pulses stay continuously on. */
        if (rumble_strength >= 240u) {
            desired = true;
        } else {
            uint64_t phase = (now - rumble_started_ms) & 15u;
            unsigned on_ms = ((unsigned)rumble_strength * 16u + 254u) / 255u;
            if (on_ms == 0u) on_ms = 1u;
            desired = phase < on_ms;
        }
    } else if (rumble_until_ms != 0u) {
        rumble_until_ms = 0u;
        rumble_started_ms = 0u;
        rumble_strength = 0u;
    }

    if (desired != rumble_output_active) {
        joypad_set_rumble_active(JOYPAD_PORT_1, desired);
        rumble_output_active = desired;
    }
#endif
}
