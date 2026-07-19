#ifndef ROTT64_SPLITSCREEN_COMMBAT_H
#define ROTT64_SPLITSCREEN_COMMBAT_H

#include <stdbool.h>
#include <stdint.h>

#define ROTT64_COMMBAT_LOCAL_PLAYERS 2U

typedef struct {
    uint16_t x;
    uint16_t y;
    uint16_t width;
    uint16_t height;
} rott64_viewport_t;

bool rott64_commbat_controller_port(unsigned local_player, unsigned *port_out);
bool rott64_commbat_horizontal_viewport(unsigned local_player, rott64_viewport_t *viewport_out);

#endif
