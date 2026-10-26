#ifndef X0Z_DIGITONE2_ADAPTER_H
#define X0Z_DIGITONE2_ADAPTER_H

#include <stdint.h>
#include "x0z/controls.h"
#include "digitone-mk2/voice.h"
#include "mk2/machines.h"

/* Callers supply reviewed native positions; this adapter reserves no sound slots. */
struct x0z_dn2_binding {
    uint32_t parameter;
    enum x0z_control control;
    const struct mk2_param *knob;
};

enum x0z_dn2_boundary { X0Z_DN2_CONTINUE, X0Z_DN2_START_UNCLASSIFIED };
struct x0z_dn2_notice {
    uint32_t slot, pitch;
    enum x0z_dn2_boundary boundary;
};
typedef void (*x0z_dn2_notice_receiver)(void *context, const struct x0z_dn2_notice *notice);

int x0z_dn2_pages(enum x0z_instrument instrument,
                  const struct x0z_dn2_binding *bindings, uint32_t count,
                  struct mk2_page *pages, uint32_t page_count);
int x0z_dn2_deliver(enum x0z_instrument instrument, const struct dn2_voice_input *input,
                    const struct x0z_dn2_binding *bindings, uint32_t count,
                    x0z_control_receiver controls, x0z_dn2_notice_receiver notice,
                    void *context);

#endif
