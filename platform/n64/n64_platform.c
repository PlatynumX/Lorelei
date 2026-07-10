#include "n64_platform.h"

#include <stdio.h>
#include <stdlib.h>

#ifdef __N64__
#include <libdragon.h>
#endif

static bool initialized;

void n64_platform_init(void)
{
    if (initialized) {
        return;
    }
#ifdef __N64__
    timer_init();
    debug_init_isviewer();
    joypad_init();
    if (dfs_init(DFS_DEFAULT_LOCATION) != DFS_ESUCCESS) {
        n64_platform_fatal("ROTT64: DragonFS mount failed");
    }
    if (!is_memory_expanded()) {
        console_init();
        console_set_render_mode(RENDER_MANUAL);
        console_clear();
        printf("ROTT64 FIRST-LEVEL CANDIDATE\n\n");
        printf("Expansion Pak required.\n");
        printf("Detected: %d MiB\n", get_memory_size() / (1024 * 1024));
        console_render();
        for (;;) {
            wait_ms(1000);
        }
    }
#endif
    initialized = true;
}

void n64_platform_fatal(const char *message)
{
#ifdef __N64__
    console_init();
    console_set_render_mode(RENDER_MANUAL);
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
