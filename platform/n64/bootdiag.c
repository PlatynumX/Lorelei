/*
 * ROTT64 staged N64 boot diagnostic.
 * Does not link Taradino. Tests display, timer, memory, controller, DragonFS,
 * and opening the embedded shareware WAD.
 */
#include <libdragon.h>
#include <stdio.h>
#include <stdint.h>

static void spin_delay(void)
{
    for (volatile uint32_t i = 0; i < 35000000u; ++i) {
        __asm__ volatile("nop");
    }
}

static void show_stage(const char *title, const char *detail, uint32_t background)
{
    surface_t *surface = display_get();
    graphics_fill_screen(surface, background);
    graphics_set_default_font();
    graphics_set_color(
        graphics_make_color(255, 255, 255, 255),
        graphics_make_color(0, 0, 0, 0)
    );
    graphics_draw_text(surface, 16, 20, "ROTT64 N64 BOOT DIAGNOSTIC");
    graphics_draw_text(surface, 16, 56, title);
    if (detail != NULL) graphics_draw_text(surface, 16, 86, detail);
    display_show(surface);
}

int main(void)
{
    char detail[160];
    FILE *wad = NULL;
    int dfs_result;

    display_init(RESOLUTION_320x240, DEPTH_16_BPP, 2, GAMMA_NONE, FILTERS_DISABLED);
    show_stage(
        "STAGE 1 PASS: basic libdragon display",
        "If you can read this, the ROM booted and VI output works.",
        graphics_make_color(24, 24, 72, 255)
    );
    spin_delay();

    timer_init();
    show_stage(
        "STAGE 2 PASS: timer initialized",
        "Waiting two seconds before the next subsystem.",
        graphics_make_color(24, 72, 24, 255)
    );
    wait_ms(2000);

    snprintf(detail, sizeof(detail), "Detected RDRAM: %d MiB%s",
        get_memory_size() / (1024 * 1024),
        is_memory_expanded() ? " (Expansion Pak visible)" : " (NO Expansion Pak)");
    show_stage("STAGE 3: memory detection", detail,
        graphics_make_color(72, 48, 24, 255));
    wait_ms(2000);

    joypad_init();
    show_stage(
        "STAGE 4 PASS: controller subsystem initialized",
        "No controller input is required for this test.",
        graphics_make_color(56, 24, 72, 255)
    );
    wait_ms(2000);

    dfs_result = dfs_init(DFS_DEFAULT_LOCATION);
    if (dfs_result != DFS_ESUCCESS) {
        snprintf(detail, sizeof(detail), "dfs_init failed with code %d", dfs_result);
        show_stage("STAGE 5 FAIL: DragonFS did not mount", detail,
            graphics_make_color(96, 0, 0, 255));
        for (;;) wait_ms(1000);
    }
    show_stage(
        "STAGE 5 PASS: DragonFS mounted",
        "Next: opening rom://rott/HUNTBGIN.WAD",
        graphics_make_color(0, 64, 64, 255)
    );
    wait_ms(2000);

    wad = fopen("rom://rott/HUNTBGIN.WAD", "rb");
    if (wad == NULL) {
        show_stage(
            "STAGE 6 FAIL: HUNTBGIN.WAD not found",
            "Expected: rom://rott/HUNTBGIN.WAD",
            graphics_make_color(96, 0, 0, 255)
        );
        for (;;) wait_ms(1000);
    }
    fclose(wad);

    show_stage(
        "STAGE 6 PASS: WAD opened successfully",
        "BOOT DIAGNOSTIC COMPLETE.\nThis ROM will remain on this screen.",
        graphics_make_color(0, 80, 24, 255)
    );
    for (;;) wait_ms(1000);
}
