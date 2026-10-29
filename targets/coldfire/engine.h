#ifndef X0X_COLDFIRE_ENGINE_H
#define X0X_COLDFIRE_ENGINE_H
#include <stdint.h>
#define X0X_FIELD_WORDS 352
/* Private tagged union: 808 uses the payload; provisional 909 uses 4 words. */
struct x0x_voice {
    uint32_t selected;
    int32_t payload[X0X_FIELD_WORDS];
};
void x0x_render(struct x0x_voice *, int32_t output[32], uint32_t start,
                uint32_t tone_tune, uint32_t decay, uint32_t model);
void x0x_silence(int32_t output[32]);
#endif
