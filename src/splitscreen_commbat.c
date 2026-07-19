#include "splitscreen_commbat.h"

bool rott64_commbat_controller_port(unsigned local_player, unsigned *port_out)
{
    if (port_out == 0 || local_player >= ROTT64_COMMBAT_LOCAL_PLAYERS) {
        return false;
    }

    *port_out = local_player;
    return true;
}

bool rott64_commbat_horizontal_viewport(unsigned local_player, rott64_viewport_t *viewport_out)
{
    if (viewport_out == 0 || local_player >= ROTT64_COMMBAT_LOCAL_PLAYERS) {
        return false;
    }

    viewport_out->x = 0U;
    viewport_out->y = (uint16_t)(local_player * 120U);
    viewport_out->width = 320U;
    viewport_out->height = 120U;
    return true;
}
