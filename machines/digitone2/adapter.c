#include "adapter.h"

static void ignore(void *context, uint32_t voice, enum x0z_control control,
                   struct x0z_position position)
{
    (void)context;
    (void)voice;
    (void)control;
    (void)position;
}

static int valid_knob(const struct mk2_param *knob)
{
    unsigned length = 0;
    if (!knob || !knob->label || knob->def > 127)
        return 0;
    while (length < 6 && knob->label[length] >= ' ' && knob->label[length] <= '~')
        ++length;
    return length > 0 && length <= 5 && !knob->label[length];
}

static int valid_bindings(enum x0z_instrument instrument,
                           const struct x0z_dn2_binding *bindings, uint32_t count)
{
    if (!bindings || !count || count > DN2_VOICE_PARAMS)
        return 0;
    for (uint32_t index = 0; index < count; ++index) {
        const struct x0z_dn2_binding *binding = &bindings[index];
        if (binding->parameter >= DN2_VOICE_PARAMS || !valid_knob(binding->knob) ||
                !x0z_send_control(instrument, 0, binding->control, 0, 32512, ignore, 0))
            return 0;
        for (uint32_t earlier = 0; earlier < index; ++earlier)
            if (bindings[earlier].parameter == binding->parameter ||
                    bindings[earlier].control == binding->control)
                return 0;
    }
    return 1;
}

int x0z_dn2_pages(enum x0z_instrument instrument,
                  const struct x0z_dn2_binding *bindings, uint32_t count,
                  struct mk2_page *pages, uint32_t page_count)
{
    if (!pages || !page_count || page_count > 5 || !valid_bindings(instrument, bindings, count))
        return 0;
    for (uint32_t index = 0; index < count; ++index)
        if (bindings[index].parameter >= 8 * page_count)
            return 0;
    for (uint32_t page = 0; page < page_count; ++page)
        for (unsigned knob = 0; knob < 8; ++knob)
            pages[page].knob[knob] = 0;
    for (uint32_t index = 0; index < count; ++index) {
        uint32_t parameter = bindings[index].parameter;
        pages[parameter / 8].knob[parameter % 8] = bindings[index].knob;
    }
    return 1;
}

int x0z_dn2_deliver(enum x0z_instrument instrument, const struct dn2_voice_input *input,
                    const struct x0z_dn2_binding *bindings, uint32_t count,
                    x0z_control_receiver controls, x0z_dn2_notice_receiver notice,
                    void *context)
{
    if (!input || !input->param || input->slot >= 16 || input->pitch > 0xffff ||
            (input->flags & ~DN2_VOICE_START) || !controls || !notice ||
            !valid_bindings(instrument, bindings, count))
        return 0;
    for (uint32_t index = 0; index < count; ++index)
        if (input->param[bindings[index].parameter] > 32512)
            return 0;
    /* Apply settled parameter values before a same-boundary START notification. */
    for (uint32_t index = 0; index < count; ++index) {
        const struct x0z_dn2_binding *binding = &bindings[index];
        x0z_send_control(instrument, input->slot, binding->control,
                         input->param[binding->parameter], 32512, controls, context);
    }
    struct x0z_dn2_notice delivered = {input->slot, input->pitch,
        input->flags & DN2_VOICE_START ? X0Z_DN2_START_UNCLASSIFIED : X0Z_DN2_CONTINUE};
    notice(context, &delivered);
    return 1;
}
