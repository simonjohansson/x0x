#ifndef X0X_DIGITONE2_ADAPTER_H
#define X0X_DIGITONE2_ADAPTER_H

#include <stdint.h>
#include "x0x/controls.h"
#include "digitone-mk2/voice.h"
#include "mk2/machines.h"

/* Callers supply reviewed native positions; this adapter reserves no sound slots. */
struct x0x_dn2_binding {
    uint32_t parameter;
    enum x0x_control control;
    const struct mk2_param *knob;
};

enum x0x_dn2_boundary { X0X_DN2_CONTINUE, X0X_DN2_START_UNCLASSIFIED };
struct x0x_dn2_notice {
    uint32_t slot, pitch;
    enum x0x_dn2_boundary boundary;
};
typedef void (*x0x_dn2_notice_receiver)(void *context, const struct x0x_dn2_notice *notice);

int x0x_dn2_pages(enum x0x_instrument instrument,
                  const struct x0x_dn2_binding *bindings, uint32_t count,
                  struct mk2_page *pages, uint32_t page_count);
int x0x_dn2_deliver(enum x0x_instrument instrument, const struct dn2_voice_input *input,
                    const struct x0x_dn2_binding *bindings, uint32_t count,
                    x0x_control_receiver controls, x0x_dn2_notice_receiver notice,
                    void *context);

#endif
