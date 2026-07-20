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
static rott64_filter_mode_t selected_filter_mode = ROTT64_FILTER_ENHANCED;
static rott64_aspect_mode_t selected_aspect_mode = ROTT64_ASPECT_ORIGINAL;
static int selected_brightness = 0;
typedef struct {
    uint8_t control_mode;
    uint8_t look_sensitivity;
    uint8_t look_deadzone;
    uint8_t invert_y;
    uint8_t binding[ROTT64_ACTION_COUNT];
} rott64_control_profile_t;

static rott64_control_profile_t control_profiles[2];
static bool selected_split_commbat = false;
static unsigned selected_local_input_player = 0u;

typedef struct {
    uint32_t magic;
    uint8_t version;
    uint8_t filter_mode;
    uint8_t aspect_mode;
    int8_t brightness;
    rott64_control_profile_t player[2];
} rott64_video_settings_t;

typedef struct {
    uint32_t magic;
    uint8_t version;
    uint8_t filter_mode;
    uint8_t aspect_mode;
    int8_t brightness;
    uint8_t control_mode;
    uint8_t look_sensitivity;
    uint8_t look_deadzone;
    uint8_t invert_y;
} rott64_video_settings_v2_t;

#define ROTT64_VIDEO_SETTINGS_MAGIC 0x56363452u /* V64R */
#define ROTT64_VIDEO_SETTINGS_VERSION 3u

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




static const uint8_t default_bindings[ROTT64_ACTION_COUNT] = {
    ROTT64_PAD_C_UP,    /* forward */
    ROTT64_PAD_C_DOWN,  /* backward */
    ROTT64_PAD_C_LEFT,  /* turn left */
    ROTT64_PAD_C_RIGHT, /* turn right */
    ROTT64_PAD_Z,       /* fire */
    ROTT64_PAD_D_UP,    /* confirm / swap */
    ROTT64_PAD_B,       /* run */
    ROTT64_PAD_START,   /* menu */
    ROTT64_PAD_D_LEFT,  /* weapon 1 */
    ROTT64_PAD_D_RIGHT, /* weapon 2 */
    ROTT64_PAD_L,       /* strafe left */
    ROTT64_PAD_R,       /* strafe right */
    ROTT64_PAD_A,       /* use */
    ROTT64_PAD_D_DOWN   /* turn 180 */
};

static void reset_control_profile(unsigned player_index)
{
    rott64_control_profile_t *profile;
    if (player_index >= 2u) return;
    profile = &control_profiles[player_index];
    profile->control_mode = ROTT64_CONTROL_MOUSELOOK;
    profile->look_sensitivity = 5u;
    profile->look_deadzone = 18u;
    profile->invert_y = 0u;
    memcpy(profile->binding, default_bindings, sizeof(profile->binding));
}

static const char *pad_button_name(rott64_pad_button_t button)
{
    static const char *const names[ROTT64_PAD_BUTTON_COUNT] = {
        "A", "B", "Z", "START", "L", "R",
        "C-UP", "C-DOWN", "C-LEFT", "C-RIGHT",
        "D-UP", "D-DOWN", "D-LEFT", "D-RIGHT"
    };
    return button < ROTT64_PAD_BUTTON_COUNT ? names[button] : "?";
}

static const char *control_action_name(rott64_control_action_t action)
{
    static const char *const names[ROTT64_ACTION_COUNT] = {
        "Forward", "Backward", "Turn Left", "Turn Right",
        "Fire", "Confirm/Swap", "Run", "Menu/Pause",
        "Weapon 1", "Weapon 2", "Strafe Left", "Strafe Right",
        "Use/Open", "Turn 180"
    };
    return action < ROTT64_ACTION_COUNT ? names[action] : "?";
}

static bool pressed_to_pad_button(joypad_buttons_t pressed, rott64_pad_button_t *out)
{
    if (pressed.a)       *out = ROTT64_PAD_A;
    else if (pressed.b)  *out = ROTT64_PAD_B;
    else if (pressed.z)  *out = ROTT64_PAD_Z;
    else if (pressed.start) *out = ROTT64_PAD_START;
    else if (pressed.l)  *out = ROTT64_PAD_L;
    else if (pressed.r)  *out = ROTT64_PAD_R;
    else if (pressed.c_up) *out = ROTT64_PAD_C_UP;
    else if (pressed.c_down) *out = ROTT64_PAD_C_DOWN;
    else if (pressed.c_left) *out = ROTT64_PAD_C_LEFT;
    else if (pressed.c_right) *out = ROTT64_PAD_C_RIGHT;
    else if (pressed.d_up) *out = ROTT64_PAD_D_UP;
    else if (pressed.d_down) *out = ROTT64_PAD_D_DOWN;
    else if (pressed.d_left) *out = ROTT64_PAD_D_LEFT;
    else if (pressed.d_right) *out = ROTT64_PAD_D_RIGHT;
    else return false;
    return true;
}

static void load_video_settings(void)
{
    rott64_video_settings_t settings;
    rott64_video_settings_v2_t legacy;
    unsigned player_index;
    unsigned action;

    reset_control_profile(0u);
    reset_control_profile(1u);

    memset(&settings, 0, sizeof(settings));
    if (n64_save_read_payload(&settings, sizeof(settings)) &&
        settings.magic == ROTT64_VIDEO_SETTINGS_MAGIC &&
        settings.version == ROTT64_VIDEO_SETTINGS_VERSION) {
        if (settings.filter_mode <= ROTT64_FILTER_ENHANCED)
            selected_filter_mode = (rott64_filter_mode_t)settings.filter_mode;
        if (settings.aspect_mode <= ROTT64_ASPECT_4_3)
            selected_aspect_mode = (rott64_aspect_mode_t)settings.aspect_mode;
        if (settings.brightness >= -2 && settings.brightness <= 2)
            selected_brightness = settings.brightness;

        for (player_index = 0u; player_index < 2u; ++player_index) {
            rott64_control_profile_t *dst = &control_profiles[player_index];
            const rott64_control_profile_t *src = &settings.player[player_index];
            if (src->control_mode <= ROTT64_CONTROL_MOUSELOOK)
                dst->control_mode = src->control_mode;
            if (src->look_sensitivity >= 1u && src->look_sensitivity <= 10u)
                dst->look_sensitivity = src->look_sensitivity;
            if (src->look_deadzone >= 4u && src->look_deadzone <= 40u)
                dst->look_deadzone = src->look_deadzone;
            dst->invert_y = src->invert_y ? 1u : 0u;
            for (action = 0u; action < ROTT64_ACTION_COUNT; ++action) {
                if (src->binding[action] < ROTT64_PAD_BUTTON_COUNT)
                    dst->binding[action] = src->binding[action];
            }
        }
        return;
    }

    /* Migrate R39/R43 V2 global controls into both independent player profiles. */
    memset(&legacy, 0, sizeof(legacy));
    if (n64_save_read_payload(&legacy, sizeof(legacy)) &&
        legacy.magic == ROTT64_VIDEO_SETTINGS_MAGIC &&
        legacy.version == 2u) {
        if (legacy.filter_mode <= ROTT64_FILTER_ENHANCED)
            selected_filter_mode = (rott64_filter_mode_t)legacy.filter_mode;
        if (legacy.aspect_mode <= ROTT64_ASPECT_4_3)
            selected_aspect_mode = (rott64_aspect_mode_t)legacy.aspect_mode;
        if (legacy.brightness >= -2 && legacy.brightness <= 2)
            selected_brightness = legacy.brightness;
        for (player_index = 0u; player_index < 2u; ++player_index) {
            if (legacy.control_mode <= ROTT64_CONTROL_MOUSELOOK)
                control_profiles[player_index].control_mode = legacy.control_mode;
            if (legacy.look_sensitivity >= 1u && legacy.look_sensitivity <= 10u)
                control_profiles[player_index].look_sensitivity = legacy.look_sensitivity;
            if (legacy.look_deadzone >= 4u && legacy.look_deadzone <= 40u)
                control_profiles[player_index].look_deadzone = legacy.look_deadzone;
            control_profiles[player_index].invert_y = legacy.invert_y ? 1u : 0u;
        }
    }
}

static void save_video_settings(void)
{
    rott64_video_settings_t settings;
    memset(&settings, 0, sizeof(settings));
    settings.magic = ROTT64_VIDEO_SETTINGS_MAGIC;
    settings.version = ROTT64_VIDEO_SETTINGS_VERSION;
    settings.filter_mode = (uint8_t)selected_filter_mode;
    settings.aspect_mode = (uint8_t)selected_aspect_mode;
    settings.brightness = (int8_t)selected_brightness;
    settings.player[0] = control_profiles[0];
    settings.player[1] = control_profiles[1];
    (void)n64_save_write_payload(&settings, sizeof(settings));
}

static void boot_video_options(void)
{
    unsigned row = 0u;
    for (;;) {
        char message[320];
        joypad_buttons_t pressed;
        const char *filter = selected_filter_mode == ROTT64_FILTER_ENHANCED ? "ENHANCED" : "STANDARD";
        const char *aspect = selected_aspect_mode == ROTT64_ASPECT_4_3 ? "4:3 CORRECTED" : "ORIGINAL";
        const char *cursor0 = row == 0u ? ">" : " ";
        const char *cursor1 = row == 1u ? ">" : " ";
        const char *cursor2 = row == 2u ? ">" : " ";
        const char *cursor3 = row == 3u ? ">" : " ";
        snprintf(message, sizeof(message),
            "N64 VIDEO OPTIONS\n"
            "%s Filtering: %s\n"
            "%s Aspect: %s\n"
            "%s Brightness: %+d\n"
            "%s Save & Back\n"
            "Up/Down: select  Left/Right: change  A: choose  B: back",
            cursor0, filter, cursor1, aspect, cursor2, selected_brightness, cursor3);
        boot_display_show(message);
        wait_ms(90);
        joypad_poll();
        pressed = joypad_get_buttons_pressed(JOYPAD_PORT_1);

        if (pressed.d_up) row = (row + 3u) % 4u;
        if (pressed.d_down) row = (row + 1u) % 4u;

        if (row == 0u && (pressed.d_left || pressed.d_right || pressed.a))
            selected_filter_mode = selected_filter_mode == ROTT64_FILTER_ENHANCED ?
                ROTT64_FILTER_STANDARD : ROTT64_FILTER_ENHANCED;
        else if (row == 1u && (pressed.d_left || pressed.d_right || pressed.a))
            selected_aspect_mode = selected_aspect_mode == ROTT64_ASPECT_4_3 ?
                ROTT64_ASPECT_ORIGINAL : ROTT64_ASPECT_4_3;
        else if (row == 2u && (pressed.d_left || pressed.d_right)) {
            int delta = pressed.d_right ? 1 : -1;
            selected_brightness += delta;
            if (selected_brightness > 2) selected_brightness = -2;
            if (selected_brightness < -2) selected_brightness = 2;
        } else if (row == 3u && pressed.a) {
            save_video_settings();
            return;
        }
        if (pressed.b) {
            save_video_settings();
            return;
        }
    }
}


static void boot_remap_actions(unsigned player_index)
{
    unsigned action = 0u;
    joypad_port_t port = player_index == 1u ? JOYPAD_PORT_2 : JOYPAD_PORT_1;

    for (;;) {
        char message[384];
        joypad_buttons_t pressed;
        rott64_pad_button_t mapped =
            (rott64_pad_button_t)control_profiles[player_index].binding[action];

        snprintf(message, sizeof(message),
            "PLAYER %u BUTTON REMAP\n"
            "%s: %s\n"
            "Up/Down: choose action\n"
            "A: bind this action\n"
            "Z: reset Player %u defaults\n"
            "B: back",
            player_index + 1u,
            control_action_name((rott64_control_action_t)action),
            pad_button_name(mapped),
            player_index + 1u);
        boot_display_show(message);
        wait_ms(90);
        joypad_poll();
        pressed = joypad_get_buttons_pressed(port);

        if (pressed.d_up)
            action = (action + ROTT64_ACTION_COUNT - 1u) % ROTT64_ACTION_COUNT;
        if (pressed.d_down)
            action = (action + 1u) % ROTT64_ACTION_COUNT;

        if (pressed.z) {
            reset_control_profile(player_index);
            continue;
        }

        if (pressed.a) {
            /* Wait for A release first so the menu-confirm press itself is not
               immediately captured as the new binding. */
            do {
                wait_ms(20);
                joypad_poll();
            } while (joypad_get_buttons_held(port).a);

            for (;;) {
                char capture_message[320];
                rott64_pad_button_t button;
                snprintf(capture_message, sizeof(capture_message),
                    "PLAYER %u BUTTON REMAP\n"
                    "%s\n"
                    "Press the N64 button to bind.\n"
                    "Press START to cancel.",
                    player_index + 1u,
                    control_action_name((rott64_control_action_t)action));
                boot_display_show(capture_message);
                wait_ms(30);
                joypad_poll();
                pressed = joypad_get_buttons_pressed(port);

                if (pressed.start)
                    break;
                if (pressed_to_pad_button(pressed, &button)) {
                    control_profiles[player_index].binding[action] = (uint8_t)button;
                    break;
                }
            }
        }

        if (pressed.b) {
            save_video_settings();
            return;
        }
    }
}

static void boot_control_options(void)
{
    unsigned row = 0u;
    unsigned player_index = 0u;

    for (;;) {
        char message[448];
        joypad_buttons_t pressed;
        rott64_control_profile_t *profile = &control_profiles[player_index];

        snprintf(message, sizeof(message),
            "N64 CONTROL OPTIONS\n"
            "%s Player: %u\n"
            "%s Mode: %s\n"
            "%s Look sensitivity: %u\n"
            "%s Stick deadzone: %u\n"
            "%s Invert Y: %s\n"
            "%s Remap buttons...\n"
            "%s Save & Back\n"
            "P1 and P2 profiles save independently.",
            row==0?">":" ", player_index + 1u,
            row==1?">":" ", profile->control_mode==ROTT64_CONTROL_MOUSELOOK?"ANALOG MOUSELOOK":"CLASSIC DIGITAL",
            row==2?">":" ", profile->look_sensitivity,
            row==3?">":" ", profile->look_deadzone,
            row==4?">":" ", profile->invert_y?"ON":"OFF",
            row==5?">":" ",
            row==6?">":" ");

        boot_display_show(message);
        wait_ms(90);
        joypad_poll();
        pressed = joypad_get_buttons_pressed(JOYPAD_PORT_1);

        if (pressed.d_up) row = (row + 6u) % 7u;
        if (pressed.d_down) row = (row + 1u) % 7u;

        if (row == 0u && (pressed.d_left || pressed.d_right || pressed.a)) {
            player_index ^= 1u;
        } else if (row == 1u && (pressed.d_left || pressed.d_right || pressed.a)) {
            profile->control_mode =
                profile->control_mode == ROTT64_CONTROL_MOUSELOOK ?
                ROTT64_CONTROL_CLASSIC : ROTT64_CONTROL_MOUSELOOK;
        } else if (row == 2u && (pressed.d_left || pressed.d_right)) {
            int value = (int)profile->look_sensitivity + (pressed.d_right ? 1 : -1);
            if (value > 10) value = 1;
            if (value < 1) value = 10;
            profile->look_sensitivity = (uint8_t)value;
        } else if (row == 3u && (pressed.d_left || pressed.d_right)) {
            int value = (int)profile->look_deadzone + (pressed.d_right ? 2 : -2);
            if (value > 40) value = 4;
            if (value < 4) value = 40;
            profile->look_deadzone = (uint8_t)value;
        } else if (row == 4u && (pressed.d_left || pressed.d_right || pressed.a)) {
            profile->invert_y = profile->invert_y ? 0u : 1u;
        } else if (row == 5u && pressed.a) {
            boot_remap_actions(player_index);
        } else if (row == 6u && pressed.a) {
            save_video_settings();
            return;
        }

        if (pressed.b) {
            save_video_settings();
            return;
        }
    }
}

static void boot_data_selector(void)
{
    unsigned choice = 0u;

    for (;;) {
        for (;;) {
            char message[320];
            joypad_buttons_t pressed;
            bool pad2;

            joypad_poll();
            pad2 = joypad_is_connected(JOYPAD_PORT_2);

            const char *label =
                choice == 0u ? "SHAREWARE" :
                choice == 1u ? "FULL DARK WAR" :
                choice == 2u ? "CUSTOM LEVELS" :
                choice == 3u ? (pad2 ? "2P SPLIT-SCREEN COMM-BAT" : "2P SPLIT-SCREEN COMM-BAT [CONTROLLER 2 REQUIRED]") :
                choice == 4u ? "VIDEO OPTIONS" : "CONTROLS";

            snprintf(message, sizeof(message),
                "ROTT64 MAIN MENU\n"
                "Choose: %s\n"
                "Controller 2: %s\n"
                "D-Pad Up/Down: change   A/Start: select",
                label, pad2 ? "CONNECTED" : "NOT CONNECTED");
            boot_display_show(message);
            wait_ms(90);
            joypad_poll();
            pressed = joypad_get_buttons_pressed(JOYPAD_PORT_1);

            if (pressed.d_up) {
                do {
                    choice = (choice + 5u) % 6u;
                } while (choice == 3u && !joypad_is_connected(JOYPAD_PORT_2));
            }
            if (pressed.d_down) {
                do {
                    choice = (choice + 1u) % 6u;
                } while (choice == 3u && !joypad_is_connected(JOYPAD_PORT_2));
            }

            if ((pressed.a || pressed.start) &&
                !(choice == 3u && !joypad_is_connected(JOYPAD_PORT_2))) {
                break;
            }
        }

        if (choice == 4u) {
            boot_video_options();
            continue;
        }
        if (choice == 5u) {
            boot_control_options();
            continue;
        }

        if (choice == 3u) {
            /* Controller 2 is guaranteed to be present here because the menu
               skips and rejects this item otherwise. This flag is consumed by
               the local Comm-Bat integration path. */
            selected_split_commbat = true;
            selected_data_mode = ROTT64_DATA_FULL;
            break;
        }

        selected_split_commbat = false;
        selected_data_mode = (rott64_data_mode_t)choice;
        break;
    }

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
            if (pressed.d_left)
                selected_custom_index = selected_custom_index == 0u ?
                    ROTT64_CUSTOM_CONTENT_COUNT - 1u : selected_custom_index - 1u;
            if (pressed.d_right)
                selected_custom_index = (selected_custom_index + 1u) % ROTT64_CUSTOM_CONTENT_COUNT;
            if (pressed.b) {
                selected_data_mode = ROTT64_DATA_SHAREWARE;
                break;
            }
            if (pressed.a || pressed.start)
                break;
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
    load_video_settings();
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

rott64_filter_mode_t n64_platform_filter_mode(void) { return selected_filter_mode; }
rott64_aspect_mode_t n64_platform_aspect_mode(void) { return selected_aspect_mode; }
int n64_platform_brightness(void) { return selected_brightness; }
rott64_control_mode_t n64_platform_control_mode_for_player(unsigned player_index)
{
    if (player_index >= 2u) player_index = 0u;
    return (rott64_control_mode_t)control_profiles[player_index].control_mode;
}

int n64_platform_look_sensitivity_for_player(unsigned player_index)
{
    if (player_index >= 2u) player_index = 0u;
    return control_profiles[player_index].look_sensitivity;
}

int n64_platform_look_deadzone_for_player(unsigned player_index)
{
    if (player_index >= 2u) player_index = 0u;
    return control_profiles[player_index].look_deadzone;
}

bool n64_platform_invert_y_for_player(unsigned player_index)
{
    if (player_index >= 2u) player_index = 0u;
    return control_profiles[player_index].invert_y != 0u;
}

rott64_pad_button_t n64_platform_binding_for_action(
    unsigned player_index, rott64_control_action_t action)
{
    if (player_index >= 2u) player_index = 0u;
    if (action >= ROTT64_ACTION_COUNT) return ROTT64_PAD_A;
    return (rott64_pad_button_t)control_profiles[player_index].binding[action];
}

rott64_control_mode_t n64_platform_control_mode(void)
{
    return n64_platform_control_mode_for_player(selected_local_input_player);
}

int n64_platform_look_sensitivity(void)
{
    return n64_platform_look_sensitivity_for_player(selected_local_input_player);
}

int n64_platform_look_deadzone(void)
{
    return n64_platform_look_deadzone_for_player(selected_local_input_player);
}

bool n64_platform_invert_y(void)
{
    return n64_platform_invert_y_for_player(selected_local_input_player);
}

bool n64_platform_second_controller_connected(void)
{
#ifdef __N64__
    joypad_poll();
    return joypad_is_connected(JOYPAD_PORT_2);
#else
    return false;
#endif
}

bool n64_platform_split_commbat_requested(void)
{
    return selected_split_commbat;
}

void n64_platform_set_local_input_player(unsigned player_index)
{
    selected_local_input_player = player_index < 2u ? player_index : 0u;
}

unsigned n64_platform_local_input_player(void)
{
    return selected_local_input_player;
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
