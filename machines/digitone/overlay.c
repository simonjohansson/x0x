/* SPDX-License-Identifier: GPL-2.0-or-later */
/* Screen gate and grid adapted from OB-1's Digitone overlay, GPL-2.0-or-later,
 * elektrob-1-dn contributors. Stock SYN2 envelope artwork is not per-machine. */
#include "digitone-mk1/machines.h"

#ifndef KEYVAR_AT
#error "KEYVAR_AT must match Digitone OS 1.44"
#endif

static void *x0z_dn_brain;
static uint32_t trigs;
/* shortcut: ordinary grid input is covered; qualify modifier flows in #20. */
static int32_t grid_record, func_down, rec_down;
static const int32_t slots[] = {27, 28, 29, 32};
static const int32_t places[] = {0, 1, 2, 5};
static const char *const labels[] = {"TNTUN", "DECAY", "ATTK", "MODEL"};

static int32_t shown(void)
{
    void *bottom, *top, *manager, *view;
    int32_t track = fw_active_track;
    if (!x0z_dn_brain || track < 0 || track >= 4 || !fw_kit ||
            (FW_SOUND_SLOT(fw_kit, track, 0) >> 8) != 80 ||
            *(volatile int32_t *)KEYVAR_AT != 2)
        return 0;
    bottom = *(void *volatile *)((uint8_t *)x0z_dn_brain + 0x54);
    top = *(void *volatile *)((uint8_t *)x0z_dn_brain + 0x5c);
    if (!bottom || bottom != top)
        return 0;
    manager = *(void *volatile *)((uint8_t *)bottom + 8);
    if (!manager)
        return 0;
    view = *(void *volatile *)((uint8_t *)manager + 0xc0);
    return view && *(volatile int32_t *)((uint8_t *)view + 144) == 0;
}

int x0z_dn_key(void *owner, void *event)
{
    if (owner)
        x0z_dn_brain = owner;
    if (event) {
        int32_t key = *(int32_t *)((uint8_t *)event + 12);
        int32_t flags = *(int32_t *)((uint8_t *)event + 16);
        if (key == 1)
            func_down = !(flags & 0x10);
        if (key == 10) {
            rec_down = !(flags & 0x10);
            if (flags == 1 && !func_down)
                grid_record ^= 1;
        }
        if (key == 11 && flags == 1 && rec_down)
            grid_record = 0;
        if (key == 12 && flags == 1 && rec_down)
            grid_record = 1;
        if (key >= 26 && key <= 41) {
            if (flags & 0x10) trigs &= ~(1u << (key - 26));
            else trigs |= 1u << (key - 26);
        } else if (flags & 1 && ((key >= 20 && key <= 25) || (key >= 42 && key <= 45)))
            trigs = 0;
    }
    return 0;
}

/* OB-1's slot-indexed native lock row; read only while editing a held step. */
static int32_t shown_value(int32_t slot)
{
    int32_t value = FW_SOUND_SLOT(fw_kit, fw_active_track, slot);
    if (grid_record && trigs && fw_pattern) {
        uint32_t step = 0;
        while (!(trigs & (1u << step))) ++step;
        uint8_t *row = fw_pattern + 0x1e80 + fw_active_track * 10319 + step * 160;
        int32_t locked = *(volatile int16_t *)(row + 2 * slot);
        if (locked != -1) value = locked;
    }
    return value;
}

static void number(int32_t raw, char text[4])
{
    uint32_t value = raw < 0 ? 0 : raw > 32512 ? 127 : (uint32_t)raw >> 8;
    uint32_t at = 0;
    if (value >= 100) text[at++] = '0' + value / 100;
    if (value >= 10) text[at++] = '0' + value / 10 % 10;
    text[at++] = '0' + value % 10;
    text[at] = 0;
}

void x0z_dn_draw(void *bitmap, void *control)
{
    (void)control;
    if (!shown())
        return;
    fw_fillrect(bitmap, 15, 0, 127, 52, 0);
    for (uint32_t knob = 0; knob < 4; ++knob) {
        int32_t x = 18 + 27 * (places[knob] % 4), y = 12 + 26 * (places[knob] / 4);
        int32_t raw = shown_value(slots[knob]);
        char text[4];
        number(raw, text);
        fw_framerect(bitmap, x + 4, 63 - y - 17, x + 21, 63 - y, 1);
        fw_textbox(bitmap, fw_font5, x + 13, 63 - y - 11, 1, 0, "XXX", "%s",
                   knob == 3 ? (raw < 16384 ? "808" : "909") : text);
        fw_textbox(bitmap, fw_font5, x + 13, 63 - y - 24, 1, 0, "XXXXX", "%s", labels[knob]);
    }
}

void x0z_dn_tick(void *control)
{
    static int32_t valid, track = -1, values[4];
    int32_t dirty;
    if (!control || !shown()) { valid = 0; return; }
    dirty = !valid || track != fw_active_track;
    for (uint32_t knob = 0; knob < 4; ++knob) {
        int32_t value = shown_value(slots[knob]);
        dirty |= values[knob] != value;
        values[knob] = value;
    }
    track = fw_active_track;
    valid = 1;
    if (dirty)
        *((volatile uint8_t *)control + 0x20) = 1;
}
