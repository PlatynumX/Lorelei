#include "SDL.h"
#include "SDL_mixer.h"
#include <assert.h>
#include <string.h>


static void test_voc_decode(void)
{
    static const Uint8 voc_type1[] = {
        'C','r','e','a','t','i','v','e',' ','V','o','i','c','e',' ','F','i','l','e',0x1a,
        0x1a,0x00, 0x0a,0x01, 0x29,0x11,
        0x01, 0x06,0x00,0x00, 0xa4,0x00, 0x80,0x81,0x7f,0x00,
        0x00
    };
    static const Uint8 voc_type9[] = {
        'C','r','e','a','t','i','v','e',' ','V','o','i','c','e',' ','F','i','l','e',0x1a,
        0x1a,0x00, 0x0a,0x01, 0x29,0x11,
        0x09, 0x10,0x00,0x00,
        0x11,0x2b,0x00,0x00, 0x08,0x01, 0x00,0x00, 0x00,0x00,0x00,0x00,
        0x80,0xff,0x00,0x40,
        0x00
    };
    Mix_Chunk *chunk;

    chunk = Mix_LoadWAV_RW(SDL_RWFromConstMem(voc_type1, sizeof(voc_type1)), 1);
    assert(chunk != NULL);
    assert(chunk->frequency == 10869u);
    assert(chunk->alen == 4u);
    assert(chunk->bits == 8u && chunk->channels == 1u);
    assert(chunk->abuf[0] == 0x00u);
    assert(chunk->abuf[1] == 0x01u);
    assert(chunk->abuf[2] == 0xffu);
    assert(chunk->abuf[3] == 0x80u);
    Mix_FreeChunk(chunk);

    chunk = Mix_LoadWAV_RW(SDL_RWFromConstMem(voc_type9, sizeof(voc_type9)), 1);
    assert(chunk != NULL);
    assert(chunk->frequency == 11025u);
    assert(chunk->alen == 4u);
    assert(chunk->abuf[0] == 0x00u);
    assert(chunk->abuf[1] == 0x7fu);
    assert(chunk->abuf[2] == 0x80u);
    assert(chunk->abuf[3] == 0xc0u);
    Mix_FreeChunk(chunk);
}

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
    test_voc_decode();
    assert(Mix_OpenAudio(22050, MIX_DEFAULT_FORMAT, 2, 512) == 0);
    assert(Mix_QuerySpec(NULL, NULL, NULL) == 1);
    Mix_CloseAudio();
    return 0;
}
