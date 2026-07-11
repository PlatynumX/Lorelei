#include "n64_platform.h"

#include <stdio.h>
#include <stdlib.h>

#ifdef __N64__
#include <libdragon.h>
#endif

static bool initialized;

#ifdef __N64__
static bool console_ready;

static void boot_console_open(void)
{
    if (console_ready) {
        return;
    }
    console_init();
    console_set_render_mode(RENDER_MANUAL);
    console_set_debug(true);
    console_ready = true;
}

static void boot_console_show(const char *stage)
{
    boot_console_open();
    console_clear();
    printf("ROTT64 SHAREWARE\n\n");
    printf("%s\n", stage ? stage : "Starting...");
    console_render();
}

static void boot_console_close(void)
{
    if (!console_ready) {
        return;
    }
    console_close();
    console_ready = false;
}
#endif

void n64_platform_init(void)
{
    if (initialized) {
        return;
    }
#ifdef __N64__
    FILE *wad;

    timer_init();
    debug_init_isviewer();

    /* These visible checkpoints distinguish an emulator/bootloader failure
       from a later Taradino startup failure. console_close() releases the
       temporary display before the game initializes its 320x240 framebuffer. */
    boot_console_show("Stage 1/4: entered N64 main()");
    wait_ms(250);

    joypad_init();
    if (dfs_init(DFS_DEFAULT_LOCATION) != DFS_ESUCCESS) {
        n64_platform_fatal("Stage 2 failed: DragonFS mount error");
    }
    boot_console_show("Stage 2/4: DragonFS mounted");
    wait_ms(250);

    if (!is_memory_expanded()) {
        char message[128];
        snprintf(message, sizeof(message),
                 "Expansion Pak required.\nDetected: %d MiB",
                 get_memory_size() / (1024 * 1024));
        n64_platform_fatal(message);
    }
    boot_console_show("Stage 3/4: Expansion Pak detected");
    wait_ms(250);

    wad = fopen("rom://rott/HUNTBGIN.WAD", "rb");
    if (wad == NULL) {
        n64_platform_fatal(
            "Stage 4 failed: HUNTBGIN.WAD not found\n"
            "Expected rom://rott/HUNTBGIN.WAD");
    }
    fclose(wad);
    boot_console_show("Stage 4/4: shareware WAD found\nStarting Taradino...");
    wait_ms(500);
    boot_console_close();
#endif
    initialized = true;
}

void n64_platform_fatal(const char *message)
{
#ifdef __N64__
    boot_console_open();
    console_clear();
    printf("ROTT64 FATAL ERROR\n\n%s\n", message ? message : "unknown error");
    console_render();
    for (;;) {
        wait_ms(1000);
    }
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
