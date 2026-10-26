#include "x0z/controls.h"

int x0z_send_control(enum x0z_instrument instrument, uint32_t voice,
                     enum x0z_control control, uint32_t raw, uint32_t maximum,
                     x0z_control_receiver receiver, void *context)
{
    int common = control == X0Z_DECAY || control == X0Z_LEVEL || control == X0Z_STRENGTH;
    int supported = (instrument == X0Z_808 && (common || control == X0Z_TONE)) ||
                    (instrument == X0Z_909 && (common || control == X0Z_TUNE || control == X0Z_ATTACK));
    if (!supported || !receiver || !maximum || raw > maximum)
        return 0;
    /* Position is unitless; the shared model supplies the pot/circuit mapping. */
    receiver(context, voice, control, (double)raw / maximum);
    return 1;
}
