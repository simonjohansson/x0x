/* Control/ownership dispatch only. Both audio sample loops are assembly. */
#include "engine.h"
extern void x0x_field808(int32_t *, int32_t *, uint32_t, uint32_t, uint32_t, uint32_t);
extern void x0x_field909(int32_t *, int32_t *, uint32_t, uint32_t, uint32_t, uint32_t);

void x0x_render(struct x0x_voice *voice, int32_t output[32], uint32_t start,
                uint32_t tone_tune, uint32_t decay, uint32_t model, uint32_t attack)
{
    if (!output)
        return;
    if (!voice || start > 1 || tone_tune > 32512 || decay > 32512 || model > 32512) {
        x0x_silence(output);
        return;
    }
    uint32_t selected = start ? (model < 16384 ? 1 : 2) : voice->selected;
    if (selected == 2 && attack > 32512) {
        x0x_silence(output);
        return;
    }
    if (start)
        voice->selected = selected;
    if (voice->selected == 1)
        x0x_field808(voice->payload, output, start, tone_tune, decay, 0);
    else if (voice->selected == 2)
        x0x_field909(voice->payload, output, start, tone_tune, decay, attack);
    else
        x0x_silence(output);
}
