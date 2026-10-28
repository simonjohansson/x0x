/* Isolated unloaded C47/VR4 output coupling: 470 nF and fixed 100 kohm.
 * void x0x_808_coupling(int32_t state[2], int32_t output[32]).
 * Q1.31 state {previous input,previous output}; caller owns lifecycle resets.
 * Input |x| <= .25; unscaled RC L1 bound is .5; output has fixed calibration.
 * C47 history stays unscaled. The complete synth chain retains its .5 FS bound.
 * shortcut: fixed full VR4 and unloaded RC; C49/buffer/loading remain unmodeled.
 */
    .text
    .globl x0x_808_coupling
    .type x0x_808_coupling, @function
x0x_808_coupling:
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
    move.l (%a0), %d4
    move.l 4(%a0), %d5
    move.l #0xb0, %d0
    move.l %d0, %macsr
    move.l #2146531960, %d6 /* A = 4511/4513 */
    move.l #2147007804, %d3 /* B = 4512/4513 */
    moveq #32, %d7
.Lcoupling_sample:
    move.l (%a1), %d2
    move.l %d5, %d1
    moveq #0, %d0
    move.l %d0, %acc0
    mac.l %d5, %d6, %acc0
    mac.l %d2, %d3, %acc0
    msac.l %d4, %d3, %acc0
    movclr.l %acc0, %d5
    /* Constant input has zero DC gain; discard a fixed point caused by rounding. */
    cmp.l %d4, %d2
    bne.s .Lcoupling_store
    cmp.l %d1, %d5
    bne.s .Lcoupling_store
    moveq #0, %d5
.Lcoupling_store:
    move.l %d2, %d4
    moveq #0, %d0
    move.l %d0, %acc0
    move.l #1719774208, %d0 /* Fixed output factor / 2 in Q31 (1.601664543...). */
    mac.l %d5, %d0, %acc0
    movclr.l %acc0, %d0
    add.l %d0, %d0
    move.l %d0, (%a1)+
    subq.l #1, %d7
    bne.s .Lcoupling_sample
    move.l %d4, (%a0)
    move.l %d5, 4(%a0)
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
    .size x0x_808_coupling, .-x0x_808_coupling
