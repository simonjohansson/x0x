#ifndef X0X_CONTROLS_H
#define X0X_CONTROLS_H

#include <stdint.h>

/* Private semantic identifiers, never firmware machine IDs or saved slots. */
enum x0x_instrument { X0X_808, X0X_909 };
enum x0x_control { X0X_TONE, X0X_DECAY, X0X_LEVEL, X0X_TUNE, X0X_ATTACK, X0X_STRENGTH };

/* Exact unitless position; the DSP backend chooses its numeric representation. */
struct x0x_position { uint32_t numerator, denominator; };

typedef void (*x0x_control_receiver)(void *context, uint32_t voice,
                                   enum x0x_control control, struct x0x_position position);

int x0x_send_control(enum x0x_instrument instrument, uint32_t voice,
                     enum x0x_control control, uint32_t raw, uint32_t maximum,
                     x0x_control_receiver receiver, void *context);

#endif
