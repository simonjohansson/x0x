/* Control/ownership dispatch only. Both audio sample loops are assembly. */
#include "engine.h"
extern void x0x_field808(int32_t *, int32_t *, uint32_t, uint32_t, uint32_t, uint32_t);
extern void x0x_909_body(int32_t *, int32_t *, uint32_t, uint32_t, uint32_t);

void x0x_render(struct x0x_voice *voice, int32_t output[32], uint32_t start,
                uint32_t tone_tune, uint32_t decay, uint32_t model)
{
    if (!output)
        return;
    if (!voice || start > 1 || tone_tune > 32512 || decay > 32512 || model > 32512) {
        x0x_silence(output);
        return;
    }
    if (start)
        voice->selected = model < 16384 ? 1 : 2;
    if (voice->selected == 1)
        x0x_field808(voice->payload, output, start, tone_tune, decay, 0);
    else if (voice->selected == 2)
        x0x_909_body(voice->payload, output, start, decay, tone_tune);
    else
        x0x_silence(output);
}
