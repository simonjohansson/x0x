/* 808 passive Tone low-pass: R171=220, R172=VR5=10k, C45=100 nF.
 * void x0x_808_tone(int32_t *state, int32_t output[32], uint32_t tone_raw).
 * Q1.31 in-place TPT one-pole; state and output are aligned, disjoint extents.
 * tone_raw is caller-bounded to 0..32512. The caller owns lifecycle resets.
 * shortcut: calibrated sqrt-coordinate rational curve; exact vintage track is unproven.
 */
    /* Unsigned D0*D1 -> D2:D3 using the ColdFire's 16-bit products. */
    .macro tone_mulu64
    move.l %d0, %d2
    andi.l #65535, %d2
    swap %d0
    andi.l #65535, %d0
    move.l %d1, %d4
    andi.l #65535, %d4
    swap %d1
    andi.l #65535, %d1
    move.l %d2, %d6
    mulu.w %d4, %d6
    move.l %d2, %d7
    mulu.w %d1, %d7
    mulu.w %d0, %d4
    mulu.w %d1, %d0
    move.l %d6, %d3
    move.l %d0, %d2
    move.l %d7, %d0
    swap %d0
    andi.l #65535, %d0
    add.l %d0, %d2
    swap %d7
    andi.l #0xffff0000, %d7
    moveq #0, %d0
    add.l %d7, %d3
    addx.l %d0, %d2
    move.l %d4, %d0
    swap %d0
    andi.l #65535, %d0
    add.l %d0, %d2
    swap %d4
    andi.l #0xffff0000, %d4
    moveq #0, %d0
    add.l %d4, %d3
    addx.l %d0, %d2
    .endm
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
    /* Rounded Q32 sqrt(raw/32512); only the two constant endpoints bypass it. */
    tst.l %d3
    beq .Ldark_endpoint
    cmpi.l #32512, %d3
    beq .Lbright_endpoint
    moveq #0, %d4 /* root */
    moveq #0, %d5 /* remainder low */
    moveq #0, %d6 /* remainder high */
    moveq #32, %d7
.Lsqrt:
    lsl.l #2, %d3
    moveq #0, %d2
    cmpi.l #65024, %d3
    bcs .Lsqrt_digit_one
    subi.l #65024, %d3
    moveq #2, %d2
.Lsqrt_digit_one:
    cmpi.l #32512, %d3
    bcs .Lsqrt_digit_ready
    subi.l #32512, %d3
    addq.l #1, %d2
.Lsqrt_digit_ready:
    add.l %d5, %d5
    addx.l %d6, %d6
    add.l %d5, %d5
    addx.l %d6, %d6
    add.l %d2, %d5
    moveq #0, %d1
    addx.l %d1, %d6
    move.l %d4, %d0
    move.l %d4, %d1
    moveq #30, %d2
    lsr.l %d2, %d1
    lsl.l #2, %d0
    addq.l #1, %d0
    add.l %d4, %d4
    cmp.l %d1, %d6
    bcs .Lsqrt_next
    bhi .Lsqrt_subtract
    cmp.l %d0, %d5
    bcs .Lsqrt_next
.Lsqrt_subtract:
    sub.l %d0, %d5
    subx.l %d1, %d6
    addq.l #1, %d4
.Lsqrt_next:
    subq.l #1, %d7
    bne .Lsqrt
    tst.l %d6
    bne .Lsqrt_round
    cmp.l %d4, %d5
    bhi .Lsqrt_round
    bcs .Lsqrt_done
    lsl.l #2, %d3
    cmpi.l #32512, %d3
    bcs .Lsqrt_done
.Lsqrt_round:
    addq.l #1, %d4
.Lsqrt_done:
    movea.l %d4, %a2
    /* N=2*2^32+round((a-1)*S), a=1.3739869594783976. */
    move.l %d4, %d0
    move.l #803130880, %d1
    tone_mulu64
    move.l %d2, %d4
    add.l %d4, %d4
    move.l %d3, %d5
    moveq #31, %d7
    lsr.l %d7, %d5
    or.l %d5, %d4
    andi.l #0x7fffffff, %d3
    cmpi.l #0x40000000, %d3
    bhi .Ln_round
    bcs .Ln_ready
    btst #0, %d4
    beq .Ln_ready
.Ln_round:
    addq.l #1, %d4
.Ln_ready:
    movea.l %d4, %a3 /* N low; N high is always two. */
    /* round(.112*N)=floor((14*N+62)/125), exact rational arithmetic. */
    move.l %d4, %d3
    moveq #2, %d2
    move.l %d4, %d0
    moveq #2, %d1
    add.l %d0, %d0
    addx.l %d1, %d1
    add.l %d3, %d3
    addx.l %d2, %d2
    add.l %d3, %d3
    addx.l %d2, %d2
    add.l %d3, %d3
    addx.l %d2, %d2
    add.l %d3, %d3
    addx.l %d2, %d2
    sub.l %d0, %d3
    subx.l %d1, %d2
    moveq #62, %d0
    moveq #0, %d1
    add.l %d0, %d3
    addx.l %d1, %d2
    moveq #0, %d4
    moveq #32, %d7
.Ldivide125:
    add.l %d3, %d3
    addx.l %d2, %d2
    add.l %d4, %d4
    cmpi.l #125, %d2
    bcs .Ldivide125_next
    subi.l #125, %d2
    addq.l #1, %d4
.Ldivide125_next:
    subq.l #1, %d7
    bne .Ldivide125
    movea.l %d4, %a5
    move.l %a2, %d0
    neg.l %d0
    moveq #96, %d1
    tone_mulu64
    /* D=3*N+round(.112*N)+96*(2^32-S). */
    move.l %a3, %d0
    moveq #2, %d4
    add.l %d0, %d3
    addx.l %d4, %d2
    add.l %d0, %d3
    addx.l %d4, %d2
    add.l %d0, %d3
    addx.l %d4, %d2
    move.l %a5, %d0
    moveq #0, %d4
    add.l %d0, %d3
    addx.l %d4, %d2
    move.l %a3, %d5
    moveq #2, %d4
    moveq #0, %d6
    moveq #31, %d7
.Ldivide:
    add.l %d5, %d5
    addx.l %d4, %d4
    add.l %d6, %d6
    cmp.l %d2, %d4
    bcs .Lnext
    bhi .Lsubtract
    cmp.l %d3, %d5
    bcs .Lnext
.Lsubtract:
    sub.l %d3, %d5
    subx.l %d2, %d4
    addq.l #1, %d6
.Lnext:
    subq.l #1, %d7
    bne .Ldivide
    bra .Lcoefficient_ready
.Ldark_endpoint:
    move.l #42015253, %d6
    bra .Lcoefficient_ready
.Lbright_endpoint:
    move.l #690065439, %d6
.Lcoefficient_ready:
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
