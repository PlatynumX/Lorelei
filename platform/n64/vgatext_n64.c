/*
 * ROTT64 replacement for Taradino's desktop VGA text renderer.
 *
 * Taradino's vgatext.c creates a separate SDL renderer, textures, and
 * 640x400 RGB surfaces for the DOS-style text screen shown during shutdown.
 * None of that is needed to reach gameplay on Nintendo 64, and keeping it
 * would require a second video backend beside the indexed game framebuffer.
 */
#include "SDL.h"

int vgatext_main(SDL_Window *window, Uint16 *screen)
{
    (void)window;
    (void)screen;
    return 0;
}
