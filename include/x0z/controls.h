#ifndef X0Z_CONTROLS_H
#define X0Z_CONTROLS_H

#include <stdint.h>

/* Private semantic identifiers, never firmware machine IDs or saved slots. */
enum x0z_instrument { X0Z_808, X0Z_909 };
enum x0z_control { X0Z_TONE, X0Z_DECAY, X0Z_LEVEL, X0Z_TUNE, X0Z_ATTACK, X0Z_STRENGTH };

typedef void (*x0z_control_receiver)(void *context, uint32_t voice,
                                   enum x0z_control control, double position);

int x0z_send_control(enum x0z_instrument instrument, uint32_t voice,
                     enum x0z_control control, uint32_t raw, uint32_t maximum,
                     x0z_control_receiver receiver, void *context);

#endif
