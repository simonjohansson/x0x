/* 808 passive Tone low-pass: R171=220, R172=VR5=10k, C45=100 nF.
 * void x0x_808_tone(int32_t *state, int32_t output[32], uint32_t tone_raw).
 * Q1.31 in-place TPT one-pole; state and output are aligned, disjoint extents.
 * tone_raw is caller-bounded to 0..32512. The caller owns lifecycle resets.
 * shortcut: fixed nominal rational C15 approximation; exact vintage curve is unproven.
 */
    .text
    .globl x0x_808_tone
    .type x0x_808_tone, @function
x0x_808_tone:
    lea -76(%sp), %sp
    movem.l %d2-%d7/%a2-%a6, (%sp)
    move.l %macsr, %d0
    move.l %d0, 72(%sp)
    moveq #0, %d0
    move.l %d0, %macsr
    move.l %acc0, %d0
    move.l %d0, 44(%sp)
    move.l %acc1, %d0
    move.l %d0, 48(%sp)
    move.l %acc2, %d0
    move.l %d0, 52(%sp)
    move.l %acc3, %d0
    move.l %d0, 56(%sp)
    move.l %accext01, %d0
    move.l %d0, 60(%sp)
    move.l %accext23, %d0
    move.l %d0, 64(%sp)
    move.l %mask, %d0
    move.l %d0, 68(%sp)
    movea.l 80(%sp), %a0
    movea.l 84(%sp), %a1
    move.l 88(%sp), %d3
    /* Nominal rational C15 rheostat: G=(750*32512+1375*raw)/(38334*32512-31721*raw). */
    move.l %d3, %d2
    move.l #1375, %d0
    mulu.l %d0, %d2
    addi.l #24384000, %d2
    move.l #31721, %d0
    mulu.l %d0, %d3
    move.l #1246315008, %d5
    sub.l %d3, %d5
    moveq #0, %d6
    moveq #31, %d7
.Ldivide:
    add.l %d6, %d6
    add.l %d2, %d2
    bcs.s .Lsubtract
    cmp.l %d5, %d2
    bcs.s .Lnext
.Lsubtract:
    sub.l %d5, %d2
    addq.l #1, %d6
.Lnext:
    subq.l #1, %d7
    bne.s .Ldivide
    move.l #0xb0, %d0
    move.l %d0, %macsr
    move.l (%a0), %d4
    moveq #32, %d7
.Lsample:
    moveq #0, %d0
    move.l %d0, %acc0
    move.l (%a1), %d2
    /* Form G*x-G*s in EMAC so opposite full-scale inputs cannot overflow x-s. */
    mac.l %d2, %d6, %acc0
    msac.l %d4, %d6, %acc0
    movclr.l %acc0, %d0
    add.l %d0, %d4
    move.l %d4, (%a1)+
    add.l %d0, %d4
    subq.l #1, %d7
    bne.s .Lsample
    move.l %d4, (%a0)
    moveq #0, %d0
    move.l %d0, %macsr
    move.l 44(%sp), %d0
    move.l %d0, %acc0
    move.l 48(%sp), %d0
    move.l %d0, %acc1
    move.l 52(%sp), %d0
    move.l %d0, %acc2
    move.l 56(%sp), %d0
    move.l %d0, %acc3
    move.l 60(%sp), %d0
    move.l %d0, %accext01
    move.l 64(%sp), %d0
    move.l %d0, %accext23
    move.l 68(%sp), %d0
    move.l %d0, %mask
    move.l 72(%sp), %d0
    move.l %d0, %macsr
    movem.l (%sp), %d2-%d7/%a2-%a6
    lea 76(%sp), %sp
    rts
    .size x0x_808_tone, .-x0x_808_tone
