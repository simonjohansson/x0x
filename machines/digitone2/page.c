#include "mk2/machines.h"

const struct mk2_param x0x_dn2_tone_tune = {"TNTUN", 64},
    x0x_dn2_decay = {"DECAY", 64}, x0x_dn2_attack = {"ATTK", 64};
static const struct mk2_param model = {"MODEL", 0};
static const struct mk2_page pages[] = {{{&x0x_dn2_tone_tune, &x0x_dn2_decay,
    &x0x_dn2_attack, 0, 0, &model, 0, 0}}};
const struct mk2_synth x0x_dn2_synth = {20, "X0X KICKS", "KICKS"};
const struct mk2_voice_pages x0x_dn2_voice_pages = {20, 1, pages};
