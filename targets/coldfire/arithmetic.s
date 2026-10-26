/* Private test probe: Q1.31 state = sat(input + coefficient * state),
 * out = sat(level * state). MACSR selects truncation or nearest-even rounding.
 * The wrapper seeds and snapshots EMAC because Unicorn exposes no EMAC API.
 */
    .text
    .globl x0z_diagnostic
    .type x0z_diagnostic, @function
x0z_diagnostic:
    moveq #0, %d0
    move.l %d0, %macsr
    move.l #0x12345678, %d0
    move.l %d0, %acc0
    move.l #0x89abcdef, %d0
    move.l %d0, %acc1
    move.l #0x13579bdf, %d0
    move.l %d0, %acc2
    move.l #0x2468ace0, %d0
    move.l %d0, %acc3
    move.l #0x11223344, %d0
    move.l %d0, %accext01
    move.l #0x55667788, %d0
    move.l %d0, %accext23
    move.l #0xabce, %d0
    move.l %d0, %mask
    move.l #0x0cb1, %d0
    move.l %d0, %macsr
    lea -28(%sp), %sp
    move.l 32(%sp), %d0
    move.l %d0, 0(%sp)
    move.l 36(%sp), %d0
    move.l %d0, 4(%sp)
    move.l 40(%sp), %d0
    move.l %d0, 8(%sp)
    move.l 44(%sp), %d0
    move.l %d0, 12(%sp)
    move.l 48(%sp), %d0
    move.l %d0, 16(%sp)
    move.l 52(%sp), %d0
    move.l %d0, 20(%sp)
    move.l 56(%sp), %d0
    move.l %d0, 24(%sp)
    bsr x0z_arithmetic
    lea 28(%sp), %sp
    movea.l 32(%sp), %a0
    move.l %macsr, %d0
    move.l %d0, 28(%a0)
    moveq #0, %d0
    move.l %d0, %macsr
    move.l %acc0, %d0
    move.l %d0, 0(%a0)
    move.l %acc1, %d0
    move.l %d0, 4(%a0)
    move.l %acc2, %d0
    move.l %d0, 8(%a0)
    move.l %acc3, %d0
    move.l %d0, 12(%a0)
    move.l %accext01, %d0
    move.l %d0, 16(%a0)
    move.l %accext23, %d0
    move.l %d0, 20(%a0)
    move.l %mask, %d0
    move.l %d0, 24(%a0)
    move.l 28(%a0), %d0
    move.l %d0, %macsr
    rts
    .size x0z_diagnostic, .-x0z_diagnostic

/* void probe(state*, out*, input*, coefficient, level, frames, macsr).
 * Save with rounding disabled, as MCF54418RM section 5.3.1.2 requires.
 */
    .globl x0z_arithmetic
    .type x0z_arithmetic, @function
x0z_arithmetic:
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
    movea.l 88(%sp), %a2
    move.l 92(%sp), %d3
    move.l 96(%sp), %d4
    move.l 100(%sp), %d2
    move.l 104(%sp), %d6
    move.l %d6, %macsr
    move.l (%a0), %d5
    tst.l %d2
    beq.s .Lrestore
.Lsample:
    move.l (%a2)+, %d0
    move.l %d0, %acc0
    mac.l %d5, %d3, %acc0
    movclr.l %acc0, %d5
    moveq #0, %d0
    move.l %d0, %acc0
    mac.l %d5, %d4, %acc0
    movclr.l %acc0, %d0
    move.l %d0, (%a1)+
    subq.l #1, %d2
    bne.s .Lsample
    move.l %d5, (%a0)
.Lrestore:
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
    move.l %d0, %macsr /* restore MACSR */
    movem.l (%sp), %d2-%d7/%a2-%a6
    lea 76(%sp), %sp
    rts
    .size x0z_arithmetic, .-x0z_arithmetic
