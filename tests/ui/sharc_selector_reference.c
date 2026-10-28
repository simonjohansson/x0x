/* Host executable policy reference. No audio rendering or target transport. */
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "controls.h"

struct reference {
    uint32_t tail[16], controls, notices, sum, numerator;
    uint32_t initialize, changed, clear;
};

static void control(void *context, uint32_t slot, enum x0x_control kind,
                     struct x0x_position position)
{
    struct reference *reference = context;
    assert(slot < 16 && kind < X0X_STRENGTH && position.denominator == 32512);
    assert(kind != X0X_LEVEL);
    ++reference->controls;
    reference->sum += position.numerator;
}

static void notice(void *context, const struct x0x_dn2_control_notice *event)
{
    struct reference *reference = context;
    uint32_t slot = event->delivered.slot;
    ++reference->notices;
    reference->initialize = event->initialize;
    reference->changed = event->model_changed;
    reference->clear = event->clear_tail;
    if (event->clear_tail)
        reference->tail[slot] = 0;
    reference->numerator = reference->sum + reference->tail[slot];
    ++reference->tail[slot];
}

int main(void)
{
    struct x0x_dn2_controls state;
    struct reference reference = {0};
    x0x_dn2_controls_init(&state);
    uint32_t slot, pitch, flags, params_present, input_present;
    while (scanf("%u %u %u %u %u", &slot, &pitch, &flags,
                  &params_present, &input_present) == 5) {
        uint32_t params[DN2_VOICE_PARAMS];
        for (unsigned parameter = 0; parameter < DN2_VOICE_PARAMS; ++parameter)
            assert(scanf("%u", &params[parameter]) == 1);
        reference.controls = reference.notices = reference.sum = reference.numerator = 0;
        reference.initialize = reference.changed = reference.clear = 0;
        struct dn2_voice_input input = {0, slot, pitch, flags, params_present ? params : 0, 0};
        int valid = x0x_dn2_controls_deliver(&state, input_present ? &input : 0,
                                             control, notice, &reference);
        printf("%u %u %u %u %u %u %u", valid, reference.notices, reference.controls,
               reference.initialize, reference.changed, reference.clear, reference.numerator);
        for (unsigned voice = 0; voice < 16; ++voice)
            printf(" %u %u", reference.tail[voice], state.voice[voice].initialized
                   ? (uint32_t)state.voice[voice].instrument + 1 : 0);
        putchar('\n');
    }
    return ferror(stdin) ? 1 : 0;
}
