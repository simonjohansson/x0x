#ifndef X0Z_DIGITONE_ADAPTER_H
#define X0Z_DIGITONE_ADAPTER_H

#include "digitone-mk1/machines.h"
#include "x0z/controls.h"

#define X0Z_DN_CONTROLS 6
#define X0Z_DN_ASSIGNED 1u
#define X0Z_DN_NATIVE_START 2u

struct x0z_dn_mapping {
    enum x0z_control control;
    int32_t knob;
};

struct x0z_dn_value {
    enum x0z_control control;
    int32_t raw, minimum, maximum; /* Observed word and stock UI bounds; frame raw may exceed maximum. */
    struct x0z_position position;
};

struct x0z_dn_input {
    int32_t *output;
    uint32_t slot, track, generation, flags;
    int32_t pitch;
    uint32_t velocity, gate, count;
    struct x0z_dn_value value[X0Z_DN_CONTROLS];
};

struct x0z_dn_adapter {
    struct { uint32_t active, track, generation; } slot[8];
};

typedef void (*x0z_dn_receiver)(void *context, const struct x0z_dn_input *input);

/* The receiver is synchronous; this private input is not a firmware ABI. */
int x0z_dn_render(struct x0z_dn_adapter *adapter, int32_t slot, int32_t output[32],
                  const struct dnm_voice *voice, enum x0z_instrument instrument,
                  const struct x0z_dn_mapping *mapping, uint32_t count,
                  x0z_dn_receiver receiver, void *context);

/* Private, current-pin same-interrupt view; never a saved or public SDK format. */
struct x0z_dn_frame {
    const volatile int16_t *words;
    uint32_t phase; /* closed, entered, captured, late voices pass */
};
struct x0z_dn_frame_mapping {
    enum x0z_control control;
    uint32_t parameter;
};

void x0z_dn_frame_begin(struct x0z_dn_frame *frame);
void x0z_dn_frame_capture(struct x0z_dn_frame *frame, const volatile int16_t *words);
void x0z_dn_frame_ready(struct x0z_dn_frame *frame);
void x0z_dn_frame_end(struct x0z_dn_frame *frame);
/* Call only during the companion voices pass. MODEL can use this
 * raw reader without pretending to be a continuous semantic control. End the
 * view after the companion (voices order 60); render exit clears it again. */
int x0z_dn_frame_read(const struct x0z_dn_frame *frame, int32_t slot,
                      uint32_t parameter, int32_t *raw, int32_t *minimum, int32_t *maximum);
/* DN-only full-range SYN2 MODEL; observed raw and bounded existing-selector input.
 * Output words must be distinct; failed reads leave both unchanged. */
int x0z_dn_frame_model(const struct x0z_dn_frame *frame, int32_t slot,
                       uint32_t parameter, int32_t *raw, uint32_t *canonical);
int x0z_dn_render_frame(struct x0z_dn_adapter *adapter, int32_t slot, int32_t output[32],
                       const struct dnm_voice *voice, enum x0z_instrument instrument,
                       const struct x0z_dn_frame *frame,
                       const struct x0z_dn_frame_mapping *mapping, uint32_t count,
                       x0z_dn_receiver receiver, void *context);

/* Inactive slots must be invalidated when the caller observes their release/reuse. */
int x0z_dn_forget(struct x0z_dn_adapter *adapter, int32_t slot);

#endif
