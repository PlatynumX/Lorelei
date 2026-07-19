#include "n64_platform.h"
#include "n64_save.h"
#include "n64_custom_content.h"
#include <stdio.h>
#include <stdlib.h>
#ifdef __N64__
#include <libdragon.h>
#endif

static bool initialized;
static rott64_data_mode_t selected_data_mode = ROTT64_DATA_SHAREWARE;

#ifdef __N64__
static unsigned selected_custom_index;
static bool boot_display_ready;
static uint64_t rumble_until_ms;
static uint64_t rumble_started_ms;
static uint8_t rumble_strength;
static bool rumble_output_active;
static uint64_t rumble_last_fire_ms;

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


static void boot_data_selector(void)
{
    unsigned choice = 0u;
    for (;;) {
        char message[192];
        joypad_buttons_t pressed;
        const char *label = choice == 0u ? "SHAREWARE" : choice == 1u ? "FULL DARK WAR" : "CUSTOM LEVELS";
        snprintf(message, sizeof(message),
            "Choose game data: %s\nD-Pad Up/Down: change   A/Start: select", label);
        boot_display_show(message);
        wait_ms(90);
        joypad_poll();
        pressed = joypad_get_buttons_pressed(JOYPAD_PORT_1);
        if (pressed.d_up) choice = (choice + 2u) % 3u;
        if (pressed.d_down) choice = (choice + 1u) % 3u;
        if (pressed.a || pressed.start) break;
    }
    selected_data_mode = (rott64_data_mode_t)choice;

    if (selected_data_mode == ROTT64_DATA_CUSTOM && ROTT64_CUSTOM_CONTENT_COUNT != 0u) {
        for (;;) {
            char message[224];
            joypad_buttons_t pressed;
            snprintf(message, sizeof(message),
                "Custom %u/%u: %s\nLeft/Right: change   A/Start: select   B: back",
                selected_custom_index + 1u, ROTT64_CUSTOM_CONTENT_COUNT,
                rott64_custom_content[selected_custom_index]);
            boot_display_show(message);
            wait_ms(90);
            joypad_poll();
            pressed = joypad_get_buttons_pressed(JOYPAD_PORT_1);
            if (pressed.d_left) selected_custom_index = selected_custom_index == 0u ? ROTT64_CUSTOM_CONTENT_COUNT - 1u : selected_custom_index - 1u;
            if (pressed.d_right) selected_custom_index = (selected_custom_index + 1u) % ROTT64_CUSTOM_CONTENT_COUNT;
            if (pressed.b) { selected_data_mode = ROTT64_DATA_SHAREWARE; break; }
            if (pressed.a || pressed.start) break;
        }
    }
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
    (void)n64_save_init();
    if (dfs_init(DFS_DEFAULT_LOCATION) != DFS_ESUCCESS)
        n64_platform_fatal("Stage 3 failed: DragonFS mount error");
    {
        char save_message[128];
        if (n64_save_available())
            snprintf(save_message, sizeof(save_message), "Stage 3/4: DragonFS mounted\nEEPROM save storage OK - boot %lu", (unsigned long)n64_save_boot_count());
        else
            snprintf(save_message, sizeof(save_message), "Stage 3/4: DragonFS mounted\nEEPROM save storage unavailable");
        boot_display_show(save_message);
    }
    wait_ms(750);

    if (!is_memory_expanded()) {
        char message[128];
        snprintf(message, sizeof(message),
            "Expansion Pak required.\nDetected: %d MiB",
            get_memory_size() / (1024 * 1024));
        n64_platform_fatal(message);
    }

    boot_data_selector();
    if (selected_data_mode == ROTT64_DATA_FULL || selected_data_mode == ROTT64_DATA_CUSTOM)
        wad = fopen("rom://rott/full/DARKWAR.WAD", "rb");
    else
        wad = fopen("rom://rott/HUNTBGIN.WAD", "rb");
    if (wad == NULL)
        n64_platform_fatal("Stage 4 failed: selected game WAD not found");
    fclose(wad);

    boot_display_show(selected_data_mode == ROTT64_DATA_SHAREWARE ?
        "Stage 4/4: Shareware selected\nStarting Taradino..." :
        selected_data_mode == ROTT64_DATA_FULL ?
        "Stage 4/4: Full Dark War selected\nStarting Taradino..." :
        "Stage 4/4: Custom content selected\nStarting Taradino...");
    wait_ms(900);
    boot_display_close();
#endif
    initialized = true;
}

rott64_data_mode_t n64_platform_data_mode(void)
{
    return selected_data_mode;
}

const char *n64_platform_custom_content(void)
{
#ifdef __N64__
    if (ROTT64_CUSTOM_CONTENT_COUNT == 0u) return NULL;
    if (selected_custom_index >= ROTT64_CUSTOM_CONTENT_COUNT) return NULL;
    return rott64_custom_content[selected_custom_index];
#else
    return NULL;
#endif
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


void n64_platform_rumble_note_fire(void)
{
#ifdef __N64__
    rumble_last_fire_ms = (uint64_t)get_ticks_ms();
#endif
}

void n64_platform_rumble_nearby_audio(unsigned total, unsigned spread)
{
#ifdef __N64__
    uint64_t now = (uint64_t)get_ticks_ms();
    bool recent_fire = rumble_last_fire_ms != 0u && (now - rumble_last_fire_ms) <= 110u;

    /* Taradino's stereo panning encodes proximity in the combined left/right
       energy. Use it as a low-intrusion event classifier until direct engine
       hooks are added: very loud centered sounds are close explosions/damage;
       the same signature immediately after Z fire upgrades recoil for heavy
       weapons. More distant centered events receive progressively lighter
       pulses. */
    if (spread > 72u || total < 320u) {
        return;
    }

    if (recent_fire && total >= 455u && spread <= 44u) {
        n64_platform_rumble_pulse(92u, 250u); /* heavy-weapon recoil */
        return;
    }
    if (total >= 470u && spread <= 36u) {
        n64_platform_rumble_pulse(86u, 225u); /* point-blank blast / hard damage */
        return;
    }
    if (total >= 420u && spread <= 52u) {
        n64_platform_rumble_pulse(64u, 185u); /* nearby explosion / damage */
        return;
    }

    /* Distance-scaled fallback: 320..419 combined energy -> 105..174 duty. */
    {
        unsigned strength = 105u + ((total - 320u) * 69u) / 99u;
        unsigned duration = 34u + ((total - 320u) * 20u) / 99u;
        if (strength > 174u) strength = 174u;
        if (duration > 54u) duration = 54u;
        n64_platform_rumble_pulse((uint32_t)duration, (uint8_t)strength);
    }
#else
    (void)total;
    (void)spread;
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
