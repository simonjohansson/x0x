#include "controls.h"

extern const struct mk2_param x0x_dn2_tone_tune, x0x_dn2_decay, x0x_dn2_attack;

static const struct x0x_dn2_binding controls_808[] = {
    {0, X0X_TONE, &x0x_dn2_tone_tune}, {1, X0X_DECAY, &x0x_dn2_decay}
};
static const struct x0x_dn2_binding controls_909[] = {
    {0, X0X_TUNE, &x0x_dn2_tone_tune}, {1, X0X_DECAY, &x0x_dn2_decay}, {2, X0X_ATTACK, &x0x_dn2_attack}
};

void x0x_dn2_controls_init(struct x0x_dn2_controls *state)
{
    if (!state)
        return;
    for (unsigned slot = 0; slot < 16; ++slot) {
        state->voice[slot].initialized = 0;
        state->voice[slot].instrument = X0X_808;
    }
}

struct delivery {
    x0x_control_receiver controls;
    x0x_dn2_control_notice_receiver notice;
    void *context;
    struct x0x_dn2_control_notice event;
};

static void deliver_control(void *context, uint32_t slot, enum x0x_control control,
                            struct x0x_position position)
{
    struct delivery *delivery = context;
    delivery->controls(delivery->context, slot, control, position);
}

static void deliver_notice(void *context, const struct x0x_dn2_notice *event)
{
    struct delivery *delivery = context;
    delivery->event.delivered = *event;
    delivery->notice(delivery->context, &delivery->event);
}

int x0x_dn2_controls_deliver(struct x0x_dn2_controls *state,
                            const struct dn2_voice_input *input,
                            x0x_control_receiver controls,
                            x0x_dn2_control_notice_receiver notice, void *context)
{
    if (!state || !input || !input->param || input->slot >= 16 ||
            input->pitch > 0xffff || (input->flags & ~DN2_VOICE_START) || !controls || !notice)
        return 0;
    /* Validate declared native destinations, including ATTK when semantically
     * ignored in 808. Undeclared D/E/G/H and later pages are never consumed. */
    for (unsigned parameter = 0; parameter < 6; ++parameter)
        if ((parameter < 3 || parameter == 5) && input->param[parameter] > 32512)
            return 0;
    struct x0x_dn2_selection *selection = &state->voice[input->slot];
    if (selection->initialized > 1 || (selection->initialized &&
            selection->instrument != X0X_808 && selection->instrument != X0X_909))
        return 0;
    if (!selection->initialized && !(input->flags & DN2_VOICE_START))
        return 1;

    enum x0x_instrument instrument = selection->instrument;
    if (input->flags & DN2_VOICE_START)
        instrument = input->param[5] < 16384 ? X0X_808 : X0X_909;
    uint32_t initialize = !selection->initialized;
    uint32_t changed = selection->initialized && selection->instrument != instrument;
    struct delivery delivery = {controls, notice, context,
        {{0, 0, X0X_DN2_CONTINUE}, instrument, initialize, changed, initialize || changed}};
    const struct x0x_dn2_binding *bindings = instrument == X0X_808 ? controls_808 : controls_909;
    uint32_t count = instrument == X0X_808 ? 2 : 3;
    if (!x0x_dn2_deliver(instrument, input, bindings, count,
                         deliver_control, deliver_notice, &delivery))
        return 0;
    selection->initialized = 1;
    selection->instrument = instrument;
    return 1;
}
