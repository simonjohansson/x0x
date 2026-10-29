/* Frozen 909: Q29 controls/onset, Q28 body, Q31 oscillator, Q64 phase.
 * Private C ABI: (state[352], output[32], START, Tune, Decay, Attack).
 * Frame: saved registers 0..43, saved EMAC 44..75, scratch 76..191.
 * All three controls latch on START; audio arithmetic is entirely ASM.
 */
.text
.globl x0x_field909
.type x0x_field909,@function
x0x_field909:
    lea -192(%sp),%sp
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
    movea.l 200(%a6),%a5
    move.l %a5,%d0
    beq .Lfinish909
    movea.l 196(%a6),%a4
    move.l %a4,%d0
    beq .Lsilent909
    move.l 204(%a6),%d0
    cmpi.l #1,%d0
    bhi .Lsilent909
    move.l 208(%a6),%d0
    cmpi.l #32512,%d0
    bhi .Lsilent909
    move.l 212(%a6),%d0
    cmpi.l #32512,%d0
    bhi .Lsilent909
    move.l 216(%a6),%d0
    cmpi.l #32512,%d0
    bhi .Lsilent909
    tst.l 204(%a6)
    beq .Lcontinued909
    bsr .Lprepare909
.Lcontinued909:
    move.l 244(%a4),%d0
    cmpi.l #2,%d0
    bne .Lsilent909
    moveq #32,%d0
    move.l %d0,76(%a6)
.Lsample909:
    move.l (%a4),%d0
    cmpi.l #96000,%d0
    bge .Lexpired909
    clr.l 140(%a4)
    cmpi.l #288,%d0
    blt .Lprefix909
    cmp.l 116(%a4),%d0
    blt .Lcached909
    bsr .Lcache909
.Lcached909:
    move.l 20(%a4),%d0
    move.l 12(%a4),%d1
    bsr x0x_cf_mul
    lsl.l #4,%d0
    move.l 4(%a4),%d1
    add.l 24(%a4),%d1
    sub.l %d0,%d1
    move.l %d1,124(%a4)
    move.l (%a4),%d6
    sub.l 112(%a4),%d6
    move.l 120(%a4),%d0
    mulu.l %d0,%d6
    lea 256(%a4),%a0
    bsr x0x_cf_horner
    move.l %d0,140(%a4)
    movea.l %a0,%a2
    moveq #1,%d5
.Lharmonic909:
    movea.l %a2,%a0
    bsr x0x_cf_horner
    movea.l %a0,%a2
    move.l %d0,96(%a6)
    move.l 124(%a4),%d0
    mulu.l %d5,%d0
    bsr x0x_cf_sine
    move.l %d0,%d1
    move.l 96(%a6),%d0
    bsr x0x_cf_mul
    add.l %d0,140(%a4)
    movea.l %a2,%a0
    bsr x0x_cf_horner
    movea.l %a0,%a2
    move.l %d0,96(%a6)
    move.l 124(%a4),%d0
    mulu.l %d5,%d0
    addi.l #0x40000000,%d0
    bsr x0x_cf_sine
    move.l %d0,%d1
    move.l 96(%a6),%d0
    bsr x0x_cf_mul
    add.l %d0,140(%a4)
    addq.l #1,%d5
    cmpi.l #6,%d5
    blt .Lharmonic909
    move.l 140(%a4),%d0
    add.l %d0,%d0
    move.l %d0,140(%a4)
.Lprefix909:
    move.l 140(%a4),80(%a6)
    move.l (%a4),%d0
    cmpi.l #1152,%d0
    bge .Lbody_output909
    bsr .Lonset909
    move.l %d0,144(%a4)
    move.l (%a4),%d0
    subi.l #288,%d0
    bsr .Lfade909
    move.l %d0,%d1
    move.l 80(%a6),%d0
    bsr x0x_cf_mul
    move.l %d0,80(%a6)
    move.l (%a4),%d0
    subi.l #1056,%d0
    bsr .Lfade909
    move.l #0x7fffffff,%d1
    sub.l %d0,%d1
    move.l 144(%a4),%d0
    bsr x0x_cf_mul
    add.l 80(%a6),%d0
    bra .Loutput909
.Lbody_output909:
    move.l 80(%a6),%d0
.Loutput909:
    cmpi.l #0x08000000,%d0
    bge .Lpositive909
    cmpi.l #-0x08000000,%d0
    ble .Lnegative909
    lsl.l #4,%d0
    bra .Lwrite909
.Lpositive909:
    move.l #0x7fffffff,%d0
    bra .Lwrite909
.Lnegative909:
    move.l #0x80000000,%d0
.Lwrite909:
    move.l %d0,(%a5)+
    move.l 12(%a4),%d0
    move.l 16(%a4),%d1
    bsr x0x_cf_mul
    move.l 12(%a4),%d1
    sub.l %d0,%d1
    move.l %d1,12(%a4)
    move.l 8(%a4),%d0
    move.l cf9_step+4,%d1
    add.l %d1,%d0
    move.l %d0,8(%a4)
    move.l 4(%a4),%d0
    move.l cf9_step,%d1
    addx.l %d1,%d0
    move.l %d0,4(%a4)
    addq.l #1,(%a4)
    bra .Lnext909
.Lexpired909:
    clr.l (%a5)+
.Lnext909:
    subq.l #1,76(%a6)
    bne .Lsample909
    bra .Lfinish909
.Lsilent909:
    moveq #32,%d0
.Lzero909:
    clr.l (%a5)+
    subq.l #1,%d0
    bne .Lzero909
.Lfinish909:
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
    lea 192(%sp),%sp
    rts


/* Source coordinate through the original 255-step control lattice. */
.Lcoordinate909:
    move.l %d0,%d1
    andi.l #255,%d1
    lsr.l #8,%d0
    lsl.l #2,%d0
    lea cf_coordinate,%a0
    adda.l %d0,%a0
    move.l (%a0),%d2
    move.l %d2,%d3
    cmpi.l #508,%d0
    beq .Lcoordinate_end909
    move.l 4(%a0),%d3
.Lcoordinate_end909:
    sub.l %d2,%d3
    mulu.l %d1,%d3
    lsl.l #8,%d2
    add.l %d3,%d2
    move.l %d2,%d0
    move.l #65280,%d1
    bsr x0x_cf_fraction
    rts
/* Q31 coordinate in d0, log2(intervals) in d1 -> cell d0, local u d6. */
.Lsegment909:
    move.l %d0,%d6
    lsl.l %d1,%d6
    andi.l #0x7fffffff,%d6
    moveq #31,%d2
    sub.l %d1,%d2
    lsr.l %d2,%d0
    rts
.Lprepare909:
    move.l 208(%a6),216(%a4)
    move.l 216(%a6),220(%a4)
    move.l 212(%a6),224(%a4)
    move.l 208(%a6),%d0
    bsr .Lcoordinate909
    move.l %d0,100(%a6)
    moveq #4,%d1
    bsr .Lsegment909
    moveq #48,%d1
    mulu.l %d1,%d0
    lea cf9_phase,%a0
    adda.l %d0,%a0
    bsr x0x_cf_horner
    move.l %d0,124(%a4)
    bsr x0x_cf_horner
    move.l %d0,20(%a4)
    lsl.l #4,%d0
    add.l 124(%a4),%d0
    move.l %d0,24(%a4)
    bsr x0x_cf_horner
    addi.l #128,%d0
    lsr.l #8,%d0
    move.l %d0,16(%a4)
    clr.l (%a4)
    clr.l 4(%a4)
    clr.l 8(%a4)
    clr.l 116(%a4)
    move.l #0x7fffffff,%d0
    move.l %d0,12(%a4)
    moveq #-1,%d0
    move.l %d0,28(%a4)
    moveq #2,%d0
    move.l %d0,244(%a4)
    move.l 100(%a6),%d0
    moveq #3,%d1
    bsr .Lsegment909
    move.l %d0,208(%a4)
    move.l %d6,192(%a4)
    move.l 216(%a6),%d0
    bsr .Lcoordinate909
    moveq #3,%d1
    bsr .Lsegment909
    move.l %d0,212(%a4)
    move.l %d6,196(%a4)
    move.l 208(%a4),%d0
    lsl.l #3,%d0
    add.l 212(%a4),%d0
    move.l #768,%d1
    mulu.l %d1,%d0
    lea cf9_onset_control,%a2
    adda.l %d0,%a2
    lea 64(%a4),%a3
    moveq #12,%d7
.Lonset_rank909:
    movea.l %a2,%a0
    lea 112(%a6),%a1
    move.l 196(%a4),%d6
    moveq #4,%d4
.Lonset_row909:
    bsr x0x_cf_horner
    move.l %d0,(%a1)+
    subq.l #1,%d4
    bne .Lonset_row909
    movea.l %a0,%a2
    lea 112(%a6),%a0
    move.l 192(%a4),%d6
    bsr x0x_cf_horner
    move.l %d0,(%a3)+
    subq.l #1,%d7
    bne .Lonset_rank909
    move.l 212(%a6),%d0
    bsr .Lcoordinate909
    moveq #4,%d1
    bsr .Lsegment909
    move.l %d0,204(%a4)
    move.l %d6,200(%a4)
    moveq #80,%d1
    mulu.l %d1,%d0
    lea cf9_control,%a0
    adda.l %d0,%a0
    lea 32(%a4),%a3
    moveq #5,%d7
.Lbody_rank909:
    bsr x0x_cf_horner
    move.l %d0,(%a3)+
    subq.l #1,%d7
    bne .Lbody_rank909
    rts

.Lcache909:
    lea cf9_frames,%a0
    move.l (%a0)+,%d0
    move.l (%a4),%d2
    moveq #0,%d4
.Lfind909:
    move.l (%a0)+,%d1
    cmp.l %d1,%d2
    blt .Lfound909
    move.l %d1,%d0
    addq.l #1,%d4
    bra .Lfind909
.Lfound909:
    move.l %d4,28(%a4)
    move.l %d0,112(%a4)
    move.l %d1,116(%a4)
    move.l %d4,%d0
    lsl.l #2,%d0
    lea cf9_inverse,%a0
    adda.l %d0,%a0
    move.l (%a0),120(%a4)
    lea 256(%a4),%a2
    moveq #0,%d5
.Lcache_channel909:
    lea 148(%a4),%a3
    moveq #0,%d6
.Lcache_node909:
    moveq #30,%d0
    mulu.l %d5,%d0
    add.l %d4,%d0
    add.l %d6,%d0
    moveq #20,%d1
    mulu.l %d1,%d0
    lea cf9_body,%a0
    adda.l %d0,%a0
    lea 32(%a4),%a1
    moveq #5,%d3
    bsr x0x_cf_dot
    move.l %d0,(%a3)+
    addq.l #1,%d6
    cmpi.l #4,%d6
    blt .Lcache_node909
    move.l 148(%a4),%d0
    sub.l 160(%a4),%d0
    move.l %d0,112(%a6)
    move.l 152(%a4),%d0
    sub.l 160(%a4),%d0
    move.l %d0,116(%a6)
    move.l 156(%a4),%d0
    sub.l 160(%a4),%d0
    move.l %d0,120(%a6)
    moveq #48,%d0
    mulu.l %d4,%d0
    lea cf9_time,%a0
    adda.l %d0,%a0
    moveq #0,%d6
.Lcache_degree909:
    lea 112(%a6),%a1
    moveq #3,%d3
    bsr x0x_cf_dot
    lsl.l #3,%d0
    cmpi.l #3,%d6
    bne .Lcache_store909
    add.l 160(%a4),%d0
.Lcache_store909:
    move.l %d0,(%a2)+
    addq.l #1,%d6
    cmpi.l #4,%d6
    blt .Lcache_degree909
    addq.l #1,%d5
    cmpi.l #11,%d5
    blt .Lcache_channel909
    rts

.Lonset909:
    move.l (%a4),%d0
    moveq #0,%d6
    cmpi.l #320,%d0
    blt .Lonset_node909
    subi.l #320,%d0
    move.l %d0,%d6
    andi.l #3,%d6
    moveq #29,%d1
    lsl.l %d1,%d6
    lsr.l #2,%d0
    addi.l #320,%d0
.Lonset_node909:
    moveq #48,%d1
    mulu.l %d1,%d0
    lea cf9_onset,%a0
    adda.l %d0,%a0
    lea 64(%a4),%a1
    moveq #12,%d3
    bsr x0x_cf_dot
    move.l %d0,%d4
    lea 64(%a4),%a1
    moveq #12,%d3
    bsr x0x_cf_dot
    sub.l %d4,%d0
    move.l %d6,%d1
    bsr x0x_cf_mul
    add.l %d4,%d0
    rts
.Lfade909:
    tst.l %d0
    ble .Lfade_zero909
    cmpi.l #96,%d0
    bge .Lfade_one909
    move.l #22369621,%d1
    mulu.l %d1,%d0
    move.l %d0,%d6
    move.l %d0,%d1
    bsr x0x_cf_mul
    move.l %d0,%d4
    move.l %d6,%d1
    bsr x0x_cf_mul
    move.l %d4,%d1
    sub.l %d0,%d1
    add.l %d1,%d1
    add.l %d4,%d1
    move.l %d1,%d0
    rts
.Lfade_zero909:
    moveq #0,%d0
    rts
.Lfade_one909:
    move.l #0x7fffffff,%d0
    rts
.size x0x_field909,.-x0x_field909
