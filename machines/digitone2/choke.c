#include <stdint.h>

/* Tag only x0x's outgoing, undeclared knob word; never modify a saved sound. */
/* shortcut: word 39 carries ownership until the SDK exposes track identity (#95). */
void x0x_tag_frame(volatile uint16_t *frame, const volatile uint8_t *owner)
{
    for (unsigned slot = 0; slot < 16; ++slot) {
        if (frame[74 + slot] == 20) {
            unsigned track = owner[20 * slot];
            frame[109 + 73 * slot + 39] = track < 16 ? 0xa500 | track : 0;
        }
    }
}
