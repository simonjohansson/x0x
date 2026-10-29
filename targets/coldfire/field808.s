/* Frozen 808 field: Q26 envelopes/state, Q31 carrier/Tone, 64-bit phase.
 * Private C ABI: field(state[352], output[32], START, Tone, Decay, MODEL).
 * Controls latch on START; MODEL=909 is silent in this private 808 entry.
 * Frame: callee registers 0..43, EMAC 44..75, private scratch 76..127.
 */
.text
.globl x0x_field808
.type x0x_field808,@function
x0x_field808:
    lea -128(%sp),%sp
    movem.l %d2-%d7/%a2-%a6,(%sp)
    movea.l %sp,%a6
    move.l %macsr,%d0
    move.l %d0,72(%a6)
    moveq #0,%d0
    move.l %d0,%macsr
    move.l %acc0,%d0
    move.l %d0,44(%a6)
    move.l %acc1,%d0
    move.l %d0,48(%a6)
    move.l %acc2,%d0
    move.l %d0,52(%a6)
    move.l %acc3,%d0
    move.l %d0,56(%a6)
    move.l %accext01,%d0
    move.l %d0,60(%a6)
    move.l %accext23,%d0
    move.l %d0,64(%a6)
    move.l %mask,%d0
    move.l %d0,68(%a6)
    move.l #0xb0,%d0
    move.l %d0,%macsr
    movea.l 136(%a6),%a5
    move.l %a5,%d0
    beq .Lfinish
    movea.l 132(%a6),%a4
    move.l %a4,%d0
    beq .Lsilent
    move.l 140(%a6),%d0
    cmpi.l #1,%d0
    bhi .Lsilent
    move.l 144(%a6),%d0
    cmpi.l #32512,%d0
    bhi .Lsilent
    move.l 148(%a6),%d0
    cmpi.l #32512,%d0
    bhi .Lsilent
    move.l 152(%a6),%d0
    cmpi.l #32512,%d0
    bhi .Lsilent
    tst.l 140(%a6)
    beq .Lcontinued
    cmpi.l #16384,%d0
    blo .Lstart808
    moveq #2,%d0
    move.l %d0,24(%a4)
    bra .Lsilent
.Lstart808:
    bsr .Lprepare
.Lcontinued:
    moveq #1,%d0
    cmp.l 24(%a4),%d0
    bne .Lsilent
    moveq #32,%d0
    move.l %d0,76(%a6)
.Lsample:
    move.l (%a4),%d1
    cmpi.l #264000,%d1
    bge .Lexpired
    clr.l 80(%a6)
    clr.l 84(%a6)
    move.l (%a4),%d1
    cmpi.l #1440,%d1
    bge .Lbody
    moveq #0,%d0
    bsr .Lenvelope
    move.l %d0,80(%a6)
.Lbody:
    move.l (%a4),%d1
    cmpi.l #960,%d1
    blt .Lblend
    moveq #1,%d0
    move.l %d0,88(%a6)
.Lharmonic:
    move.l 88(%a6),%d0
    bsr .Lenvelope
    move.l %d0,92(%a6)
    move.l %d1,96(%a6)
    move.l 88(%a6),%d0
    move.l 4(%a4),%d1
    mulu.l %d1,%d0
    bsr .Lsine
    move.l %d0,%d1
    move.l 92(%a6),%d0
    bsr .Lmul
    move.l %d0,124(%a6)
    move.l 88(%a6),%d0
    move.l 4(%a4),%d1
    mulu.l %d1,%d0
    addi.l #0x40000000,%d0
    bsr .Lsine
    move.l %d0,%d1
    move.l 96(%a6),%d0
    bsr .Lmul
    add.l 124(%a6),%d0
    add.l %d0,84(%a6)
    addq.l #1,88(%a6)
    move.l 88(%a6),%d1
    cmpi.l #4,%d1
    blt .Lharmonic
    moveq #4,%d0
    bsr .Lenvelope
    add.l %d0,84(%a6)
.Lblend:
    move.l 80(%a6),%d0
    move.l (%a4),%d1
    cmpi.l #960,%d1
    blt .Ltone
    move.l 84(%a6),%d0
    move.l (%a4),%d1
    cmpi.l #1440,%d1
    bge .Ltone
    move.l (%a4),%d6
    subi.l #960,%d6
    move.l #4473924,%d0
    mulu.l %d0,%d6
    move.l %d6,%d0
    move.l %d6,%d1
    bsr .Lmul
    move.l %d0,92(%a6)
    move.l %d6,%d1
    bsr .Lmul
    move.l 92(%a6),%d1
    sub.l %d0,%d1
    add.l %d1,%d1
    add.l 92(%a6),%d1
    move.l 84(%a6),%d0
    sub.l 80(%a6),%d0
    bsr .Lmul
    add.l 80(%a6),%d0
.Ltone:
    move.l 20(%a4),%d1
    bsr .Lmul
    add.l %d0,%d0
    move.l %d0,92(%a6)
    add.l 12(%a4),%d0
    move.l %d0,96(%a6)
    move.l 16(%a4),%d1
    bsr .Lmul
    move.l %d0,120(%a6)
    move.l 92(%a6),%d0
    move.l cf_constants+8,%d1
    bsr .Lmul
    move.l 120(%a6),%d1
    sub.l %d0,%d1
    move.l %d1,12(%a4)
    move.l 96(%a6),%d0
    lsl.l #7,%d0
    move.l %d0,(%a5)+
    addq.l #1,(%a4)
    move.l 8(%a4),%d0
    move.l cf_constants+4,%d1
    add.l %d1,%d0
    move.l %d0,8(%a4)
    move.l 4(%a4),%d0
    move.l cf_constants,%d1
    addx.l %d1,%d0
    move.l %d0,4(%a4)
    bra .Lnext
.Lexpired:
    clr.l (%a5)+
.Lnext:
    subq.l #1,76(%a6)
    bne .Lsample
    bra .Lfinish
.Lsilent:
    moveq #32,%d0
.Lzero:
    clr.l (%a5)+
    subq.l #1,%d0
    bne .Lzero
.Lfinish:
    moveq #0,%d0
    move.l %d0,%macsr
    move.l 44(%a6),%d0
    move.l %d0,%acc0
    move.l 48(%a6),%d0
    move.l %d0,%acc1
    move.l 52(%a6),%d0
    move.l %d0,%acc2
    move.l 56(%a6),%d0
    move.l %d0,%acc3
    move.l 60(%a6),%d0
    move.l %d0,%accext01
    move.l 64(%a6),%d0
    move.l %d0,%accext23
    move.l 68(%a6),%d0
    move.l %d0,%mask
    move.l 72(%a6),%d0
    move.l %d0,%macsr
    movem.l (%sp),%d2-%d7/%a2-%a6
    lea 128(%sp),%sp
    rts

/* Fractional EMAC multiplication: two nearest-even narrowing steps. */
.globl x0x_cf_mul
x0x_cf_mul:
.Lmul:
    moveq #0,%d2
    move.l %d2,%acc0
    mac.l %d0,%d1,%acc0
    movclr.l %acc0,%d0
    rts
.globl x0x_cf_dot
x0x_cf_dot:
.Ldot:
    moveq #0,%d0
    move.l %d0,%acc0
.Ldot_loop:
    move.l (%a0)+,%d0
    move.l (%a1)+,%d1
    mac.l %d0,%d1,%acc0
    subq.l #1,%d3
    bne .Ldot_loop
    movclr.l %acc0,%d0
    rts
.globl x0x_cf_horner
x0x_cf_horner:
.Lhorner:
    move.l (%a0)+,%d0
    moveq #3,%d3
.Lhorner_loop:
    move.l %d6,%d1
    bsr .Lmul
    add.l (%a0)+,%d0
    subq.l #1,%d3
    bne .Lhorner_loop
    rts
/* Exact floor((numerator<<31)/denominator), without a 64-bit DIV opcode. */
.globl x0x_cf_fraction
x0x_cf_fraction:
.Lfraction:
    cmp.l %d1,%d0
    bhs .Lfraction_one
    lsl.l #8,%d0
    lsl.l #7,%d0
    move.l %d0,%d2
    divu.l %d1,%d0
    move.l %d0,%d3
    mulu.l %d1,%d3
    sub.l %d3,%d2
    lsl.l #8,%d2
    lsl.l #8,%d2
    divu.l %d1,%d2
    lsl.l #8,%d0
    lsl.l #8,%d0
    or.l %d2,%d0
    rts
.Lfraction_one:
    move.l #0x7fffffff,%d0
    rts
.globl x0x_cf_sine
x0x_cf_sine:
.Lsine:
    move.l %d0,%d2
    moveq #21,%d1
    lsr.l %d1,%d0
    lsl.l #2,%d0
    lea cf_sine,%a0
    adda.l %d0,%a0
    move.l (%a0),%d4
    move.l 4(%a0),%d0
    sub.l %d4,%d0
    andi.l #0x1fffff,%d2
    lsl.l #8,%d2
    lsl.l #2,%d2
    move.l %d2,%d1
    bsr .Lmul
    add.l %d4,%d0
    rts
.Lprepare:
    move.l 148(%a6),%d0
    move.l %d0,%d1
    andi.l #255,%d1
    lsr.l #8,%d0
    lsl.l #2,%d0
    lea cf_coordinate,%a0
    adda.l %d0,%a0
    move.l (%a0),%d2
    move.l %d2,%d3
    cmpi.l #508,%d0
    beq .Lcoordinate_end
    move.l 4(%a0),%d3
.Lcoordinate_end:
    sub.l %d2,%d3
    mulu.l %d1,%d3
    lsl.l #8,%d2
    add.l %d3,%d2
    lsl.l #4,%d2
    move.l %d2,%d0
    move.l #65280,%d1
    divu.l %d1,%d0
    cmpi.l #15,%d0
    bls .Lcontrol_segment
    moveq #15,%d0
.Lcontrol_segment:
    move.l %d0,%d3
    mulu.l %d1,%d3
    sub.l %d3,%d2
    lsl.l #7,%d0
    lea cf_control,%a2
    adda.l %d0,%a2
    move.l %d2,%d0
    bsr .Lfraction
    move.l %d0,%d6
    lea 28(%a4),%a3
    moveq #8,%d7
.Lweights:
    movea.l %a2,%a0
    bsr .Lhorner
    movea.l %a0,%a2
    move.l %d0,(%a3)+
    subq.l #1,%d7
    bne .Lweights
    lea cf_body,%a2
    lea 208(%a4),%a3
    move.l #300,%d7
.Lcombine:
    movea.l %a2,%a0
    lea 28(%a4),%a1
    moveq #8,%d3
    bsr .Ldot
    movea.l %a0,%a2
    move.l %d0,(%a3)+
    subq.l #1,%d7
    bne .Lcombine
    move.l 144(%a6),%d0
    cmpi.l #256,%d0
    blo .Llow_tone
    move.l %d0,%d6
    andi.l #255,%d6
    moveq #23,%d1
    lsl.l %d1,%d6
    lsr.l #8,%d0
    lsl.l #4,%d0
    lea cf_tone,%a0
    adda.l %d0,%a0
    bra .Lpole
.Llow_tone:
    lea cf_low_break,%a2
    moveq #0,%d7
.Lfind_low:
    cmp.l 4(%a2),%d0
    blo .Llow_found
    addq.l #4,%a2
    addq.l #1,%d7
    bra .Lfind_low
.Llow_found:
    sub.l (%a2),%d0
    move.l 4(%a2),%d1
    sub.l (%a2),%d1
    bsr .Lfraction
    move.l %d0,%d6
    lsl.l #4,%d7
    lea cf_low,%a0
    adda.l %d7,%a0
.Lpole:
    bsr .Lhorner
    move.l %d0,16(%a4)
    move.l #0x7fffffff,%d1
    sub.l %d0,%d1
    move.l %d1,%d0
    move.l cf_constants+12,%d1
    bsr .Lmul
    move.l %d0,20(%a4)
    clr.l (%a4)
    clr.l 4(%a4)
    clr.l 8(%a4)
    clr.l 12(%a4)
    moveq #1,%d0
    move.l %d0,24(%a4)
    moveq #-1,%d0
    lea 60(%a4),%a0
    moveq #5,%d1
.Linvalidate:
    move.l %d0,(%a0)+
    subq.l #1,%d1
    bne .Linvalidate
    rts

/* Cache convex Bezier values at a segment change, then exact integer power
 * coefficients. D0=group; returns one/two Q26 values in D0/D1. */
.Lenvelope:
    moveq #28,%d1
    mulu.l %d1,%d0
    lea cf_groups,%a2
    adda.l %d0,%a2
    move.l 20(%a2),%d4
    movea.l %a4,%a0
    adda.l %d4,%a0
    move.l (%a0),%d5
    bpl .Lindex_nonnegative
    moveq #0,%d5
.Lindex_nonnegative:
    moveq #76,%d1
    mulu.l %d5,%d1
    movea.l 4(%a2),%a3
    adda.l %d1,%a3
.Lfind_segment:
    move.l (%a4),%d0
    cmp.l 4(%a3),%d0
    blt .Lsegment_ready
    move.l (%a2),%d0
    subq.l #1,%d0
    cmp.l %d0,%d5
    bge .Lsegment_ready
    addq.l #1,%d5
    lea 76(%a3),%a3
    bra .Lfind_segment
.Lsegment_ready:
    cmp.l (%a0),%d5
    beq .Lcached
    move.l %d5,(%a0)
    lsl.l #2,%d5
    add.l 8(%a2),%d5
    move.l %a4,%d0
    add.l %d0,%d5
    move.l %d5,92(%a6)
    move.l 24(%a2),%d0
    add.l %a4,%d0
    move.l %d0,96(%a6)
    move.l 16(%a2),%d0
    move.l %d0,116(%a6)
.Lcache_channel:
    moveq #0,%d5
.Lbezier:
    move.l %d5,%d0
    lsl.l #2,%d0
    lea 12(%a3),%a0
    adda.l %d0,%a0
    movea.l 92(%a6),%a1
    moveq #4,%d3
    bsr .Ldot
    move.l %d0,100(%a6,%d5.l)
    addq.l #4,%d5
    cmpi.l #16,%d5
    blt .Lbezier
    move.l 100(%a6),%d0
    move.l 104(%a6),%d1
    move.l 108(%a6),%d2
    move.l 112(%a6),%d3
    movea.l 96(%a6),%a0
    move.l %d2,%d4
    add.l %d4,%d4
    add.l %d2,%d4
    sub.l %d4,%d3
    move.l %d1,%d4
    add.l %d4,%d4
    add.l %d1,%d4
    add.l %d4,%d3
    sub.l %d0,%d3
    move.l %d3,(%a0)+
    move.l %d1,%d4
    add.l %d4,%d4
    sub.l %d4,%d2
    add.l %d0,%d2
    move.l %d2,%d4
    add.l %d4,%d4
    add.l %d2,%d4
    move.l %d4,(%a0)+
    sub.l %d0,%d1
    move.l %d1,%d4
    add.l %d4,%d4
    add.l %d1,%d4
    move.l %d4,(%a0)+
    move.l %d0,(%a0)+
    move.l %a0,96(%a6)
    move.l 12(%a2),%d0
    add.l %d0,92(%a6)
    subq.l #1,116(%a6)
    bne .Lcache_channel
.Lcached:
    move.l (%a4),%d6
    sub.l (%a3),%d6
    move.l 8(%a3),%d0
    mulu.l %d0,%d6
    move.l 24(%a2),%d0
    movea.l %a4,%a0
    adda.l %d0,%a0
    bsr .Lhorner
    move.l %d0,120(%a6)
    moveq #0,%d1
    moveq #1,%d0
    cmp.l 16(%a2),%d0
    beq .Lenvelope_done
    bsr .Lhorner
    move.l %d0,%d1
.Lenvelope_done:
    move.l 120(%a6),%d0
    rts
.size x0x_field808,.-x0x_field808
