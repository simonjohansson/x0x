/* First unshaped 909 triangle at 48 kHz: provisional 50 Hz, tau 250 ms, gain .25.
 * void x0x_909_body(int32_t state[2], int32_t output[32], uint32_t start).
 * State is {unsigned phase, Q1.31 amplitude}; caller owns aligned disjoint extents.
 * shortcut: START resets to a rising zero crossing; replace the fixed pitch,
 * exponential envelope and restart when the circuit model is implemented.
 * Nearest-even envelope multiplication has a small nonzero Q31 tail floor.
 */
    .text
    .globl x0x_909_body
    .type x0x_909_body, @function
x0x_909_body:
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
    tst.l 88(%sp)
    beq.s .L909continue
    move.l #0x40000000, %d4
    move.l #0x20000000, %d5
.L909continue:
    move.l #0xb0, %d0 /* fractional, saturated, nearest-even */
    move.l %d0, %macsr
    move.l #2147304698, %d2 /* round(exp(-1/12000) * 2^31) */
    moveq #32, %d6
.L909sample:
    addi.l #4473924, %d4 /* round(50/48000 * 2^32), natural phase wrap */
    move.l %d4, %d3
    cmpi.l #0x80000000, %d3
    beq.s .L909peak
    tst.l %d3
    bpl.s .L909fold
    neg.l %d3
.L909fold:
    add.l %d3, %d3
    subi.l #0x80000000, %d3
    bra.s .L909multiply
.L909peak:
    move.l #0x7fffffff, %d3 /* positive unity is outside Q1.31 */
.L909multiply:
    moveq #0, %d0
    move.l %d0, %acc0
    mac.l %d5, %d2, %acc0
    movclr.l %acc0, %d5
    mac.l %d5, %d3, %acc0
    movclr.l %acc0, %d0
    move.l %d0, (%a1)+
    subq.l #1, %d6
    bne.s .L909sample
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
    .size x0x_909_body, .-x0x_909_body
