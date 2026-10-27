#include "x0x/controls.h"

int x0x_send_control(enum x0x_instrument instrument, uint32_t voice,
                     enum x0x_control control, uint32_t raw, uint32_t maximum,
                     x0x_control_receiver receiver, void *context)
{
    int common = control == X0X_DECAY || control == X0X_LEVEL || control == X0X_STRENGTH;
    int supported = (instrument == X0X_808 && (common || control == X0X_TONE)) ||
                    (instrument == X0X_909 && (common || control == X0X_TUNE || control == X0X_ATTACK));
    if (!supported || !receiver || !maximum || raw > maximum)
        return 0;
    /* Position is unitless; the shared model supplies the pot/circuit mapping. */
    struct x0x_position position = {raw, maximum};
    receiver(context, voice, control, position);
    return 1;
}
