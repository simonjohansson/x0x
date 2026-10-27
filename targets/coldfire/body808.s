/* Provisional 808 body: damped 55 Hz sine at 48 kHz with live decay.
 * void x0x_808_body(int32_t state[2], int32_t output[32], uint32_t start, uint32_t decay_raw).
 * decay_raw is caller-bounded to 0..32512; default 16384 gives tau = 250 ms.
 * State is {x,y} in Q1.31; caller owns disjoint aligned state/output extents.
 * shortcut: START restarts phase/amplitude; replace with measured retrigger
 * excitation when the circuit model is implemented.
 */
    .text
    .globl x0x_808_body
    .type x0x_808_body, @function
x0x_808_body:
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
    beq.s .Lcontinue
    moveq #0, %d4
    move.l #0x20000000, %d5
.Lcontinue:
    move.l #0xb0, %d0 /* fractional, saturated, nearest-even */
    move.l %d0, %macsr
    /* Linear provisional feedback retention, interpolated once per block. */
    move.l 92(%sp), %d6
    move.l #66052, %d0 /* floor(2^31 / 32512); product stays signed-positive */
    mulu.l %d0, %d6
    move.l #2147112711, %d2
    move.l %d2, %acc0
    move.l #270545, %d2
    mac.l %d6, %d2, %acc0
    movclr.l %acc0, %d2
    move.l #15458369, %d3
    move.l %d3, %acc0
    move.l #1948, %d3
    mac.l %d6, %d3, %acc0
    movclr.l %acc0, %d3
    moveq #32, %d6
.Lsample:
    moveq #0, %d0
    move.l %d0, %acc0
    move.l %d0, %acc1
    mac.l %d4, %d2, %acc0
    mac.l %d5, %d3, %acc0
    mac.l %d5, %d2, %acc1
    msac.l %d4, %d3, %acc1
    movclr.l %acc0, %d4
    movclr.l %acc1, %d5
    move.l %d4, (%a1)+
    subq.l #1, %d6
    bne.s .Lsample
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
    .size x0x_808_body, .-x0x_808_body
