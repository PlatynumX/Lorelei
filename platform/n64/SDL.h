#ifndef ROTT64_SDL_COMPAT_H
#define ROTT64_SDL_COMPAT_H

#include <stdarg.h>
#include <stddef.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef uint8_t Uint8;
typedef int8_t Sint8;
typedef uint16_t Uint16;
typedef int16_t Sint16;
typedef uint32_t Uint32;
typedef int32_t Sint32;
typedef uint64_t Uint64;
typedef int64_t Sint64;
typedef int SDL_bool;
typedef int SDL_Keycode;
typedef int SDL_Scancode;
typedef Uint16 SDL_Keymod;

#define SDL_FALSE 0

#define SDL_MAJOR_VERSION 2
#define SDL_MINOR_VERSION 30
#define SDL_PATCHLEVEL 0
#define SDL_VERSION_ATLEAST(X, Y, Z) 1

#define SDL_LIL_ENDIAN 1234
#define SDL_BIG_ENDIAN 4321
#ifdef __N64__
#define SDL_BYTEORDER SDL_BIG_ENDIAN
#else
#if defined(__BYTE_ORDER__) && __BYTE_ORDER__ == __ORDER_BIG_ENDIAN__
#define SDL_BYTEORDER SDL_BIG_ENDIAN
#else
#define SDL_BYTEORDER SDL_LIL_ENDIAN
#endif
#endif

#define AUDIO_U8 0x0008u
#define AUDIO_S8 0x8008u
#define AUDIO_U16LSB 0x0010u
#define AUDIO_S16LSB 0x8010u
#define AUDIO_U16MSB 0x1010u
#define AUDIO_S16MSB 0x9010u
#if SDL_BYTEORDER == SDL_BIG_ENDIAN
#define AUDIO_S16SYS AUDIO_S16MSB
#else
#define AUDIO_S16SYS AUDIO_S16LSB
#endif
#define SDL_AUDIO_MASK_BITSIZE 0x00FFu
#define SDL_AUDIO_MASK_DATATYPE 0x0100u
#define SDL_AUDIO_MASK_ENDIAN 0x1000u
#define SDL_AUDIO_MASK_SIGNED 0x8000u
#define SDL_AUDIO_BITSIZE(x) ((x) & SDL_AUDIO_MASK_BITSIZE)
#define SDL_AUDIO_ISFLOAT(x) ((x) & SDL_AUDIO_MASK_DATATYPE)
#define SDL_AUDIO_ISBIGENDIAN(x) ((x) & SDL_AUDIO_MASK_ENDIAN)
#define SDL_AUDIO_ISSIGNED(x) ((x) & SDL_AUDIO_MASK_SIGNED)
#define SDL_AUDIO_ALLOW_FREQUENCY_CHANGE 0x00000001u
#define SDL_TRUE 1
#define SDL_DISABLE 0
#define SDL_ENABLE 1
#define SDL_PRESSED 1
#define SDL_RELEASED 0

#define SDL_INIT_TIMER      0x00000001u
#define SDL_INIT_AUDIO      0x00000010u
#define SDL_INIT_VIDEO      0x00000020u
#define SDL_INIT_JOYSTICK   0x00000200u
#define SDL_INIT_EVENTS     0x00004000u
#define SDL_INIT_EVERYTHING 0x0000FFFFu

#define SDL_QUIT             0x100u
#define SDL_KEYDOWN          0x300u
#define SDL_KEYUP            0x301u
#define SDL_MOUSEMOTION      0x400u
#define SDL_MOUSEBUTTONDOWN  0x401u
#define SDL_MOUSEBUTTONUP    0x402u
#define SDL_MOUSEWHEEL       0x403u
#define SDL_JOYBALLMOTION    0x601u
#define SDL_JOYBUTTONDOWN    0x603u
#define SDL_JOYBUTTONUP      0x604u

#define SDL_BUTTON_LEFT 1u
#define SDL_BUTTON_MIDDLE 2u
#define SDL_BUTTON_RIGHT 3u
#define SDL_BUTTON(X) (1u << ((X)-1u))
#define SDL_BUTTON_LMASK SDL_BUTTON(SDL_BUTTON_LEFT)
#define SDL_BUTTON_MMASK SDL_BUTTON(SDL_BUTTON_MIDDLE)
#define SDL_BUTTON_RMASK SDL_BUTTON(SDL_BUTTON_RIGHT)

#define KMOD_NONE 0x0000u
#define KMOD_LSHIFT 0x0001u
#define KMOD_RSHIFT 0x0002u
#define KMOD_SHIFT (KMOD_LSHIFT | KMOD_RSHIFT)
#define KMOD_LCTRL 0x0040u
#define KMOD_RCTRL 0x0080u
#define KMOD_CTRL (KMOD_LCTRL | KMOD_RCTRL)
#define KMOD_LALT 0x0100u
#define KMOD_RALT 0x0200u
#define KMOD_ALT (KMOD_LALT | KMOD_RALT)

/* SDL2 USB/HID scancode values. Taradino indexes a table with these values. */
enum {
    SDL_SCANCODE_UNKNOWN = 0,
    SDL_SCANCODE_A = 4, SDL_SCANCODE_B, SDL_SCANCODE_C, SDL_SCANCODE_D,
    SDL_SCANCODE_E, SDL_SCANCODE_F, SDL_SCANCODE_G, SDL_SCANCODE_H,
    SDL_SCANCODE_I, SDL_SCANCODE_J, SDL_SCANCODE_K, SDL_SCANCODE_L,
    SDL_SCANCODE_M, SDL_SCANCODE_N, SDL_SCANCODE_O, SDL_SCANCODE_P,
    SDL_SCANCODE_Q, SDL_SCANCODE_R, SDL_SCANCODE_S, SDL_SCANCODE_T,
    SDL_SCANCODE_U, SDL_SCANCODE_V, SDL_SCANCODE_W, SDL_SCANCODE_X,
    SDL_SCANCODE_Y, SDL_SCANCODE_Z,
    SDL_SCANCODE_1 = 30, SDL_SCANCODE_2, SDL_SCANCODE_3, SDL_SCANCODE_4,
    SDL_SCANCODE_5, SDL_SCANCODE_6, SDL_SCANCODE_7, SDL_SCANCODE_8,
    SDL_SCANCODE_9, SDL_SCANCODE_0,
    SDL_SCANCODE_RETURN = 40, SDL_SCANCODE_ESCAPE, SDL_SCANCODE_BACKSPACE,
    SDL_SCANCODE_TAB, SDL_SCANCODE_SPACE, SDL_SCANCODE_MINUS,
    SDL_SCANCODE_EQUALS, SDL_SCANCODE_LEFTBRACKET, SDL_SCANCODE_RIGHTBRACKET,
    SDL_SCANCODE_BACKSLASH, SDL_SCANCODE_NONUSHASH, SDL_SCANCODE_SEMICOLON,
    SDL_SCANCODE_APOSTROPHE, SDL_SCANCODE_GRAVE, SDL_SCANCODE_COMMA,
    SDL_SCANCODE_PERIOD, SDL_SCANCODE_SLASH, SDL_SCANCODE_CAPSLOCK,
    SDL_SCANCODE_F1, SDL_SCANCODE_F2, SDL_SCANCODE_F3, SDL_SCANCODE_F4,
    SDL_SCANCODE_F5, SDL_SCANCODE_F6, SDL_SCANCODE_F7, SDL_SCANCODE_F8,
    SDL_SCANCODE_F9, SDL_SCANCODE_F10, SDL_SCANCODE_F11, SDL_SCANCODE_F12,
    SDL_SCANCODE_PRINTSCREEN, SDL_SCANCODE_SCROLLLOCK, SDL_SCANCODE_PAUSE,
    SDL_SCANCODE_INSERT, SDL_SCANCODE_HOME, SDL_SCANCODE_PAGEUP,
    SDL_SCANCODE_DELETE, SDL_SCANCODE_END, SDL_SCANCODE_PAGEDOWN,
    SDL_SCANCODE_RIGHT, SDL_SCANCODE_LEFT, SDL_SCANCODE_DOWN, SDL_SCANCODE_UP,
    SDL_SCANCODE_NUMLOCKCLEAR, SDL_SCANCODE_KP_DIVIDE, SDL_SCANCODE_KP_MULTIPLY,
    SDL_SCANCODE_KP_MINUS, SDL_SCANCODE_KP_PLUS, SDL_SCANCODE_KP_ENTER,
    SDL_SCANCODE_KP_1, SDL_SCANCODE_KP_2, SDL_SCANCODE_KP_3,
    SDL_SCANCODE_KP_4, SDL_SCANCODE_KP_5, SDL_SCANCODE_KP_6,
    SDL_SCANCODE_KP_7, SDL_SCANCODE_KP_8, SDL_SCANCODE_KP_9,
    SDL_SCANCODE_KP_0, SDL_SCANCODE_KP_PERIOD,
    SDL_SCANCODE_LCTRL = 224, SDL_SCANCODE_LSHIFT, SDL_SCANCODE_LALT,
    SDL_SCANCODE_LGUI, SDL_SCANCODE_RCTRL, SDL_SCANCODE_RSHIFT,
    SDL_SCANCODE_RALT, SDL_SCANCODE_RGUI,
    SDL_SCANCODE_F13 = 104, SDL_SCANCODE_F14 = 105
};

#define SDLK_UNKNOWN 0
#define SDLK_RETURN '\r'
#define SDLK_ESCAPE 27
#define SDLK_BACKSPACE '\b'
#define SDLK_TAB '\t'
#define SDLK_SPACE ' '
#define SDLK_g 'g'
#define SDLK_PAUSE 0x40000048
#define SDLK_CAPSLOCK 0x40000039
#define SDLK_NUMLOCKCLEAR 0x40000053
#define SDLK_SCROLLLOCK 0x40000047
#define SDLK_KP_ENTER 0x40000058

#define SDL_JOYSTICK_AXIS_MAX 32767
#define SDL_MESSAGEBOX_ERROR 0x10u

#define SDL_zero(x) memset(&(x), 0, sizeof(x))
#define SDL_arraysize(array) (sizeof(array) / sizeof((array)[0]))
#define SDL_snprintf snprintf
#define SDL_vsnprintf vsnprintf
#define SDL_malloc malloc
#define SDL_calloc calloc
#define SDL_realloc realloc
#define SDL_free free
#define SDL_memset memset
#define SDL_memcpy memcpy
#define SDL_strlen strlen
#define SDL_strcmp strcmp
#define SDL_strncmp strncmp
#define SDL_strcasecmp strcasecmp
#define SDL_strncasecmp strncasecmp
#define SDL_strlcpy(dst, src, size) rott64_sdl_strlcpy((dst), (src), (size))

#define SDL_MUSTLOCK(surface) 0
#define SDL_LockSurface(surface) 0
#define SDL_UnlockSurface(surface) ((void)0)

struct SDL_Window;
struct SDL_Renderer;
struct SDL_Texture;
struct SDL_Joystick;
typedef struct SDL_Window SDL_Window;
typedef struct SDL_Renderer SDL_Renderer;
typedef struct SDL_Texture SDL_Texture;
typedef struct SDL_Joystick SDL_Joystick;

typedef struct SDL_Color { Uint8 r, g, b, a; } SDL_Color;
typedef struct SDL_Palette { int ncolors; SDL_Color *colors; Uint32 version; int refcount; } SDL_Palette;
typedef struct SDL_PixelFormat { Uint32 format; SDL_Palette *palette; Uint8 BitsPerPixel; Uint8 BytesPerPixel; } SDL_PixelFormat;
typedef struct SDL_Surface { Uint32 flags; SDL_PixelFormat *format; int w, h; int pitch; void *pixels; } SDL_Surface;
typedef struct SDL_Rect { int x, y, w, h; } SDL_Rect;
typedef struct SDL_RWops { FILE *file; const Uint8 *mem; size_t size; size_t pos; int owned; } SDL_RWops;
typedef struct SDL_version { Uint8 major, minor, patch; } SDL_version;

typedef struct SDL_Keysym { SDL_Scancode scancode; SDL_Keycode sym; SDL_Keymod mod; Uint32 unused; } SDL_Keysym;
typedef struct SDL_KeyboardEvent { Uint32 type, timestamp, windowID; Uint8 state, repeat, padding2, padding3; SDL_Keysym keysym; } SDL_KeyboardEvent;
typedef struct SDL_MouseMotionEvent { Uint32 type, timestamp, windowID, which, state; int x, y, xrel, yrel; } SDL_MouseMotionEvent;
typedef struct SDL_MouseButtonEvent { Uint32 type, timestamp, windowID, which; Uint8 button, state, clicks, padding1; int x, y; } SDL_MouseButtonEvent;
typedef struct SDL_MouseWheelEvent { Uint32 type, timestamp, windowID, which; int x, y; Uint32 direction; } SDL_MouseWheelEvent;
typedef struct SDL_JoyBallEvent { Uint32 type, timestamp; Sint32 which; Uint8 ball, padding1, padding2, padding3; Sint16 xrel, yrel; } SDL_JoyBallEvent;
typedef struct SDL_JoyButtonEvent { Uint32 type, timestamp; Sint32 which; Uint8 button, state, padding1, padding2; } SDL_JoyButtonEvent;
typedef union SDL_Event {
    Uint32 type;
    SDL_KeyboardEvent key;
    SDL_MouseMotionEvent motion;
    SDL_MouseButtonEvent button;
    SDL_MouseWheelEvent wheel;
    SDL_JoyBallEvent jball;
    SDL_JoyButtonEvent jbutton;
    Uint8 padding[64];
} SDL_Event;

size_t rott64_sdl_strlcpy(char *dst, const char *src, size_t size);
void SDL_GetVersion(SDL_version *version);
int SDL_Init(Uint32 flags);
int SDL_InitSubSystem(Uint32 flags);
void SDL_QuitSubSystem(Uint32 flags);
void SDL_Quit(void);
Uint32 SDL_WasInit(Uint32 flags);
Uint32 SDL_GetTicks(void);
Uint64 SDL_GetTicks64(void);
void SDL_Delay(Uint32 milliseconds);
const char *SDL_GetError(void);
int SDL_SetError(const char *fmt, ...);
void SDL_ClearError(void);
char *SDL_GetBasePath(void);
char *SDL_GetPrefPath(const char *org, const char *app);
int SDL_ShowSimpleMessageBox(Uint32 flags, const char *title, const char *message, SDL_Window *window);
int SDL_PollEvent(SDL_Event *event);
int SDL_PushEvent(SDL_Event *event);
void SDL_PumpEvents(void);
Uint32 SDL_GetMouseState(int *x, int *y);
Uint32 SDL_GetRelativeMouseState(int *x, int *y);
int SDL_SetRelativeMouseMode(SDL_bool enabled);
int SDL_ShowCursor(int toggle);
int SDL_NumJoysticks(void);
SDL_Joystick *SDL_JoystickOpen(int device_index);
void SDL_JoystickClose(SDL_Joystick *joystick);
Sint16 SDL_JoystickGetAxis(SDL_Joystick *joystick, int axis);
Uint8 SDL_JoystickGetButton(SDL_Joystick *joystick, int button);
int SDL_JoystickEventState(int state);
int SDL_SetPaletteColors(SDL_Palette *palette, const SDL_Color *colors, int firstcolor, int ncolors);
SDL_RWops *SDL_RWFromFile(const char *file, const char *mode);
SDL_RWops *SDL_RWFromConstMem(const void *mem, int size);
SDL_RWops *SDL_RWFromMem(void *mem, int size);
Sint64 SDL_RWsize(SDL_RWops *context);
Sint64 SDL_RWseek(SDL_RWops *context, Sint64 offset, int whence);
size_t SDL_RWread(SDL_RWops *context, void *ptr, size_t size, size_t maxnum);
size_t SDL_RWwrite(SDL_RWops *context, const void *ptr, size_t size, size_t num);
int SDL_RWclose(SDL_RWops *context);

#ifdef __cplusplus
}
#endif
#endif
