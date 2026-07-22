#include "SDL.h"
#include "SDL_mixer.h"
#include "n64_platform.h"

#include <stdarg.h>
#include <stdbool.h>
#include <strings.h>

#ifdef __N64__
#include <libdragon.h>

/* Taradino menu state, defined in rt_menu.c. */
extern int inmenu;
extern int ingame;
#endif

#define EVENT_QUEUE_CAPACITY 64u
#define KEY_BINDING_COUNT 15u

struct SDL_Joystick { int unused; };

static Uint32 initialized_flags;
static char error_text[192];
static SDL_Event event_queue[EVENT_QUEUE_CAPACITY];
static unsigned queue_read;
static unsigned queue_write;
static int relative_x;
static int relative_y;
static Uint32 mouse_buttons;

static bool queue_empty(void)
{
    return queue_read == queue_write;
}

static bool queue_full(void)
{
    return ((queue_write + 1u) % EVENT_QUEUE_CAPACITY) == queue_read;
}

#ifdef __N64__
static SDL_Keycode keycode_for_scancode(SDL_Scancode code)
{
    if (code >= SDL_SCANCODE_A && code <= SDL_SCANCODE_Z) {
        return 'a' + (code - SDL_SCANCODE_A);
    }
    switch (code) {
        case SDL_SCANCODE_RETURN: return SDLK_RETURN;
        case SDL_SCANCODE_ESCAPE: return SDLK_ESCAPE;
        case SDL_SCANCODE_BACKSPACE: return SDLK_BACKSPACE;
        case SDL_SCANCODE_TAB: return SDLK_TAB;
        case SDL_SCANCODE_SPACE: return SDLK_SPACE;
        case SDL_SCANCODE_CAPSLOCK: return SDLK_CAPSLOCK;
        case SDL_SCANCODE_NUMLOCKCLEAR: return SDLK_NUMLOCKCLEAR;
        case SDL_SCANCODE_SCROLLLOCK: return SDLK_SCROLLLOCK;
        case SDL_SCANCODE_PAUSE: return SDLK_PAUSE;
        case SDL_SCANCODE_KP_ENTER: return SDLK_KP_ENTER;
        default: return 0x40000000 | code;
    }
}

static void emit_key(SDL_Scancode scancode, bool pressed)
{
    SDL_Event event;
    if (queue_full()) {
        return;
    }
    SDL_zero(event);
    event.type = pressed ? SDL_KEYDOWN : SDL_KEYUP;
    event.key.type = event.type;
    event.key.state = pressed ? SDL_PRESSED : SDL_RELEASED;
    event.key.keysym.scancode = scancode;
    event.key.keysym.sym = keycode_for_scancode(scancode);
    event_queue[queue_write] = event;
    queue_write = (queue_write + 1u) % EVENT_QUEUE_CAPACITY;
}

typedef struct {
    SDL_Scancode key;
    bool held;
} key_binding_t;

static key_binding_t bindings[KEY_BINDING_COUNT] = {
    {SDL_SCANCODE_UP, false},          /* menu up */
    {SDL_SCANCODE_DOWN, false},        /* menu down */
    {SDL_SCANCODE_LEFT, false},        /* menu left */
    {SDL_SCANCODE_RIGHT, false},       /* menu right */
    {SDL_SCANCODE_LCTRL, false},       /* fire */
    {SDL_SCANCODE_RETURN, false},      /* confirm / swap */
    {SDL_SCANCODE_LSHIFT, false},      /* run */
    {SDL_SCANCODE_ESCAPE, false},      /* back / pause */
    {SDL_SCANCODE_TAB, false},         /* drop */
    {SDL_SCANCODE_COMMA, false},       /* strafe left */
    {SDL_SCANCODE_PERIOD, false},      /* strafe right */
    {SDL_SCANCODE_SPACE, false},       /* use */
    {SDL_SCANCODE_BACKSPACE, false},   /* volte-face */
    {SDL_SCANCODE_M, false},           /* map */
    {SDL_SCANCODE_CAPSLOCK, false},    /* autorun */
};

static void update_binding(unsigned index, bool held)
{
    if (index >= KEY_BINDING_COUNT || bindings[index].held == held) {
        return;
    }
    bindings[index].held = held;
    emit_key(bindings[index].key, held);
}
#endif

#ifdef __N64__
static int n64_mouse_axis(int value)
{
    const int deadzone = 8;
    const int max_axis = 85;
    const int max_delta = 9;
    int magnitude = value < 0 ? -value : value;
    int scaled;
    int delta;

    if (magnitude <= deadzone) return 0;
    if (magnitude > max_axis) magnitude = max_axis;

    scaled = magnitude - deadzone;
    delta = (scaled * scaled * max_delta) /
            ((max_axis - deadzone) * (max_axis - deadzone));
    if (delta < 1) delta = 1;
    return value < 0 ? -delta : delta;
}
#endif

static void poll_n64_controller(void)
{
    rott64_mixer_pump();
#ifdef __N64__
    joypad_inputs_t input;
    joypad_buttons_t buttons;
    joypad_buttons_t pressed;
    static uint64_t next_auto_fire_rumble_ms;
    static uint64_t next_mouse_sample_ms;
    static bool look_up_held;
    static bool look_down_held;
    const uint64_t now = n64_platform_ticks_ms();
    const bool menu_mode = (inmenu != 0) || (ingame == 0);

    n64_platform_poll();
    input = joypad_get_inputs(JOYPAD_PORT_1);
    buttons = joypad_get_buttons_held(JOYPAD_PORT_1);
    pressed = joypad_get_buttons_pressed(JOYPAD_PORT_1);

    if (!menu_mode) {
        if (pressed.z) {
            n64_platform_rumble_pulse(55u, 210u);
            next_auto_fire_rumble_ms = now + 85u;
        } else if (buttons.z && now >= next_auto_fire_rumble_ms) {
            n64_platform_rumble_pulse(38u, 165u);
            next_auto_fire_rumble_ms = now + 85u;
        }
    }

    /* Menus: D-pad navigation, A/Z confirm, B/Start back. */
    update_binding(0, menu_mode && buttons.d_up);
    update_binding(1, menu_mode && buttons.d_down);
    update_binding(2, menu_mode && buttons.d_left);
    update_binding(3, menu_mode && buttons.d_right);
    update_binding(5, (menu_mode && (buttons.a || buttons.z)) ||
                       (!menu_mode && buttons.c_up));
    update_binding(7, (menu_mode && (buttons.b || buttons.start)) ||
                       (!menu_mode && buttons.start));

    /* Gameplay:
       analog mouse, Z fire, A use, B run,
       C-left/right strafe, C-up swap, C-down drop,
       D-up/down look, D-left intentionally unassigned, D-right autorun,
       L map, R volte-face. */
    update_binding(4, !menu_mode && buttons.z);
    update_binding(6, !menu_mode && buttons.b);
    update_binding(8, !menu_mode && buttons.c_down);
    update_binding(9, !menu_mode && buttons.c_left);
    update_binding(10, !menu_mode && buttons.c_right);
    update_binding(11, !menu_mode && buttons.a);
    update_binding(12, !menu_mode && buttons.r);
    update_binding(13, !menu_mode && buttons.l);
    update_binding(14, !menu_mode && buttons.d_right);

    if (!menu_mode) {
        if (look_up_held != buttons.d_up) {
            look_up_held = buttons.d_up;
            emit_key(SDL_SCANCODE_I, look_up_held);
        }
        if (look_down_held != buttons.d_down) {
            look_down_held = buttons.d_down;
            emit_key(SDL_SCANCODE_K, look_down_held);
        }

        if (now >= next_mouse_sample_ms) {
            relative_x += n64_mouse_axis(input.stick_x);
            relative_y -= n64_mouse_axis(input.stick_y);
            next_mouse_sample_ms = now + 8u;
        }
    } else {
        if (look_up_held) {
            look_up_held = false;
            emit_key(SDL_SCANCODE_I, false);
        }
        if (look_down_held) {
            look_down_held = false;
            emit_key(SDL_SCANCODE_K, false);
        }
        relative_x = 0;
        relative_y = 0;
    }
#else
    /* Host tests push events explicitly. */
#endif
}

size_t rott64_sdl_strlcpy(char *dst, const char *src, size_t size)
{
    const size_t length = src ? strlen(src) : 0u;
    if (size != 0u) {
        const size_t copy = length < size - 1u ? length : size - 1u;
        if (copy != 0u && src != NULL) memcpy(dst, src, copy);
        dst[copy] = '\0';
    }
    return length;
}

void SDL_GetVersion(SDL_version *version)
{
    if (version != NULL) {
        version->major = SDL_MAJOR_VERSION;
        version->minor = SDL_MINOR_VERSION;
        version->patch = SDL_PATCHLEVEL;
    }
}

int SDL_Init(Uint32 flags)
{
    n64_platform_init();
    initialized_flags |= flags;
    return 0;
}

int SDL_InitSubSystem(Uint32 flags) { return SDL_Init(flags); }
void SDL_QuitSubSystem(Uint32 flags) { initialized_flags &= ~flags; }
void SDL_Quit(void) { initialized_flags = 0; }
Uint32 SDL_WasInit(Uint32 flags) { return flags ? initialized_flags & flags : initialized_flags; }
Uint32 SDL_GetTicks(void) { return (Uint32)n64_platform_ticks_ms(); }
Uint64 SDL_GetTicks64(void) { return n64_platform_ticks_ms(); }
void SDL_Delay(Uint32 milliseconds) { rott64_mixer_pump(); n64_platform_wait_ms(milliseconds); rott64_mixer_pump(); }
const char *SDL_GetError(void) { return error_text; }

int SDL_SetError(const char *fmt, ...)
{
    va_list args;
    va_start(args, fmt);
    (void)vsnprintf(error_text, sizeof(error_text), fmt, args);
    va_end(args);
    return -1;
}

void SDL_ClearError(void) { error_text[0] = '\0'; }

static char *copy_path(const char *path)
{
    const size_t length = strlen(path) + 1u;
    char *result = malloc(length);
    if (result != NULL) {
        memcpy(result, path, length);
    }
    return result;
}

char *SDL_GetBasePath(void) { return copy_path("rom://rott/"); }
char *SDL_GetPrefPath(const char *org, const char *app)
{
    (void)org;
    (void)app;
    /* Read-only target. No CONFIG.ROT is embedded, so Taradino uses defaults. */
    return copy_path("rom://rott/");
}

int SDL_ShowSimpleMessageBox(Uint32 flags, const char *title, const char *message, SDL_Window *window)
{
    (void)flags; (void)title; (void)window;
    n64_platform_fatal(message);
    return 0;
}

int SDL_PollEvent(SDL_Event *event)
{
    poll_n64_controller();
    if (event == NULL || queue_empty()) {
        return 0;
    }
    *event = event_queue[queue_read];
    queue_read = (queue_read + 1u) % EVENT_QUEUE_CAPACITY;
    return 1;
}

int SDL_PushEvent(SDL_Event *event)
{
    if (event == NULL || queue_full()) {
        return -1;
    }
    event_queue[queue_write] = *event;
    queue_write = (queue_write + 1u) % EVENT_QUEUE_CAPACITY;
    return 1;
}

void SDL_PumpEvents(void) { poll_n64_controller(); }
Uint32 SDL_GetMouseState(int *x, int *y) { if (x) *x = 0; if (y) *y = 0; return mouse_buttons; }
Uint32 SDL_GetRelativeMouseState(int *x, int *y)
{
    if (x) *x = relative_x;
    if (y) *y = relative_y;
    relative_x = relative_y = 0;
    return mouse_buttons;
}
int SDL_SetRelativeMouseMode(SDL_bool enabled) { (void)enabled; return 0; }
int SDL_ShowCursor(int toggle) { (void)toggle; return 0; }
int SDL_NumJoysticks(void) { return 0; }
SDL_Joystick *SDL_JoystickOpen(int device_index) { (void)device_index; return NULL; }
void SDL_JoystickClose(SDL_Joystick *joystick) { (void)joystick; }
Sint16 SDL_JoystickGetAxis(SDL_Joystick *joystick, int axis) { (void)joystick; (void)axis; return 0; }
Uint8 SDL_JoystickGetButton(SDL_Joystick *joystick, int button) { (void)joystick; (void)button; return 0; }
int SDL_JoystickEventState(int state) { return state; }

int SDL_SetPaletteColors(SDL_Palette *palette, const SDL_Color *colors, int firstcolor, int ncolors)
{
    if (palette == NULL || colors == NULL || firstcolor < 0 || ncolors < 0
        || firstcolor + ncolors > palette->ncolors) {
        return SDL_SetError("invalid palette range");
    }
    memcpy(&palette->colors[firstcolor], colors, (size_t)ncolors * sizeof(*colors));
    palette->version++;
    return 0;
}

SDL_RWops *SDL_RWFromFile(const char *file, const char *mode)
{
    SDL_RWops *rw = calloc(1, sizeof(*rw));
    if (rw == NULL) return NULL;
    rw->file = fopen(file, mode);
    if (rw->file == NULL) { free(rw); return NULL; }
    rw->owned = 1;
    return rw;
}

SDL_RWops *SDL_RWFromConstMem(const void *mem, int size)
{
    SDL_RWops *rw;
    if (mem == NULL || size < 0) return NULL;
    rw = calloc(1, sizeof(*rw));
    if (rw != NULL) { rw->mem = mem; rw->size = (size_t)size; }
    return rw;
}
SDL_RWops *SDL_RWFromMem(void *mem, int size) { return SDL_RWFromConstMem(mem, size); }

Sint64 SDL_RWsize(SDL_RWops *context)
{
    long oldpos, end;
    if (context == NULL) return -1;
    if (context->file == NULL) return (Sint64)context->size;
    oldpos = ftell(context->file);
    if (oldpos < 0 || fseek(context->file, 0, SEEK_END) != 0) return -1;
    end = ftell(context->file);
    (void)fseek(context->file, oldpos, SEEK_SET);
    return (Sint64)end;
}

Sint64 SDL_RWseek(SDL_RWops *context, Sint64 offset, int whence)
{
    if (context == NULL) return -1;
    if (context->file != NULL) {
        if (fseek(context->file, (long)offset, whence) != 0) return -1;
        return (Sint64)ftell(context->file);
    }
    {
        Sint64 base = whence == SEEK_SET ? 0 : whence == SEEK_CUR ? (Sint64)context->pos : (Sint64)context->size;
        Sint64 next = base + offset;
        if (next < 0 || (uint64_t)next > context->size) return -1;
        context->pos = (size_t)next;
        return next;
    }
}

size_t SDL_RWread(SDL_RWops *context, void *ptr, size_t size, size_t maxnum)
{
    size_t bytes, available;
    if (context == NULL || ptr == NULL) return 0;
    if (context->file != NULL) return fread(ptr, size, maxnum, context->file);
    if (size == 0) return 0;
    available = context->size - context->pos;
    bytes = size * maxnum;
    if (bytes > available) bytes = available - (available % size);
    memcpy(ptr, context->mem + context->pos, bytes);
    context->pos += bytes;
    return bytes / size;
}

size_t SDL_RWwrite(SDL_RWops *context, const void *ptr, size_t size, size_t num)
{
    if (context == NULL || context->file == NULL) return 0;
    return fwrite(ptr, size, num, context->file);
}

int SDL_RWclose(SDL_RWops *context)
{
    int result = 0;
    if (context == NULL) return -1;
    if (context->file != NULL && context->owned) result = fclose(context->file);
    free(context);
    return result;
}
