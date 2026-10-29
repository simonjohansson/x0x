/* Seed and snapshot the caller EMAC around the six-argument DSP entry. */
    .text
    .globl x0x_diagnostic
    .type x0x_diagnostic, @function
x0x_diagnostic:
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
    lea -24(%sp),%sp
    move.l 28(%sp),%d0
    move.l %d0,0(%sp)
    move.l 32(%sp),%d0
    move.l %d0,4(%sp)
    move.l 36(%sp),%d0
    move.l %d0,8(%sp)
    move.l 40(%sp),%d0
    move.l %d0,12(%sp)
    move.l 44(%sp),%d0
    move.l %d0,16(%sp)
    move.l 48(%sp),%d0
    move.l %d0,20(%sp)
    bsr x0x_field808
    lea 24(%sp),%sp
    movea.l 28(%sp),%a0
    move.l %d0, 32(%a0)
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
    .size x0x_diagnostic, .-x0x_diagnostic

