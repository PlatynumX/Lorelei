#include "SDL.h"
#include "SDL_mixer.h"
#include <assert.h>
#include <string.h>

int main(void)
{
    SDL_Color backing[4] = {{0}};
    SDL_Palette palette = {4, backing, 0, 1};
    SDL_Color incoming[2] = {{1,2,3,255},{4,5,6,255}};
    SDL_Event in = {0}, out = {0};
    const char bytes[] = "ROTT64";
    char readback[7] = {0};
    SDL_RWops *rw;

    assert(SDL_Init(SDL_INIT_TIMER | SDL_INIT_EVENTS) == 0);
    assert(SDL_SetPaletteColors(&palette, incoming, 1, 2) == 0);
    assert(backing[1].g == 2 && backing[2].b == 6);
    in.type = SDL_KEYDOWN;
    in.key.keysym.scancode = SDL_SCANCODE_RETURN;
    in.key.state = SDL_PRESSED;
    assert(SDL_PushEvent(&in) == 1);
    assert(SDL_PollEvent(&out) == 1);
    assert(out.type == SDL_KEYDOWN && out.key.keysym.scancode == SDL_SCANCODE_RETURN);
    rw = SDL_RWFromConstMem(bytes, 6);
    assert(rw != NULL && SDL_RWsize(rw) == 6);
    assert(SDL_RWread(rw, readback, 1, 6) == 6);
    assert(strcmp(readback, "ROTT64") == 0);
    assert(SDL_RWclose(rw) == 0);
    assert(Mix_OpenAudio(22050, MIX_DEFAULT_FORMAT, 2, 512) == 0);
    assert(Mix_QuerySpec(NULL, NULL, NULL) == 1);
    Mix_CloseAudio();
    return 0;
}
