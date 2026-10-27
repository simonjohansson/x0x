/* Provisional 808 body: damped 47.65 Hz sine at 48 kHz with live decay.
 * void x0x_808_body(int32_t state[4], int32_t output[32], uint32_t start, uint32_t decay_raw).
 * decay_raw is caller-bounded to 0..32512; default 16384 gives tau = 143 ms.
 * State is {Q31 x,y,initial_samples_remaining,Q31 C39 node}; 15 V encodes as .25 FS.
 * shortcut: source-separated C39 and fixed encoding; main pulse shaping,
 * full feedback/loading and residual-state retrigger follow in #9/#79.
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
    move.l 8(%a0), %d7
    tst.l 88(%sp)
    beq.s .Lcontinue
    moveq #0, %d4
    moveq #0, %d5
    move.l #288, %d7
    move.l #25411890, %d0 /* .71 V / 60; positive D52 clamp at START */
    move.l %d0, 12(%a0)
.Lcontinue:
    move.l #0xb0, %d0 /* fractional, saturated, nearest-even */
    move.l %d0, %macsr
    /* Three reference-training anchors; stock feedback/pot modeling remains open. */
    move.l 92(%sp), %d6
    cmpi.l #16384, %d6
    bge .Ldecay_high
    move.l #131072, %d0 /* low branch excludes 16384, keeping the product signed-positive */
    mulu.l %d0, %d6
    tst.l %d7
    beq.s .Lsteady_low
    move.l #2145824990, %d2
    move.l #36801676, %d3
    move.l #1030110, %d0
    movea.l #17667, %a2
    movea.l #-2979664, %a3
    movea.l #-1431, %a4
    movea.l #134297, %a5
    movea.l #-83403, %a6
    bra .Ldecay_coefficients
.Lsteady_low:
    move.l #2146098800, %d2
    move.l #13386187, %d3
    move.l #1030242, %d0
    movea.l #6426, %a2
    movea.l #-2979791, %a3
    movea.l #-1431, %a4
    movea.l #308271, %a5
    movea.l #-229334, %a6
    bra .Ldecay_coefficients
.Ldecay_high:
    subi.l #16384, %d6
    move.l #133152, %d0 /* floor(2^31 / 16128) */
    mulu.l %d0, %d6
    tst.l %d7
    beq.s .Lsteady_high
    move.l #2146855100, %d2
    move.l #36819343, %d3
    move.l #190576, %d0
    movea.l #3268, %a2
    movea.l #-2981094, %a3
    movea.l #-265, %a4
    movea.l #50893, %a5
    movea.l #-15430, %a6
    bra .Ldecay_coefficients
.Lsteady_high:
    move.l #2147129041, %d2
    move.l #13392613, %d3
    move.l #190600, %d0
    movea.l #1189, %a2
    movea.l #-2981221, %a3
    movea.l #-265, %a4
    movea.l #78937, %a5
    movea.l #-42428, %a6
.Ldecay_coefficients:
    move.l %d2, %acc0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d2
    move.l %d3, %acc0
    move.l %a2, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d3
    /* Exact decaying-input integral at the three anchors; interpolate with Decay. */
    move.l %a3, %d0
    move.l %d0, %acc0
    move.l %a4, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d0
    movea.l %d0, %a3 /* companion Gx */
    move.l %a5, %d0
    move.l %d0, %acc0
    move.l %a6, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d0
    movea.l %d0, %a2 /* companion Gy */
    movea.l 12(%a0), %a5
    movea.l %d7, %a4
    moveq #32, %d6
.Lsample:
    tst.l %d7
    beq.s .Lnopulse
    subq.l #1, %d7
    cmpi.l #240, %d7 /* Drive only for the first 48 of 288 initial samples. */
    blt.s .Lnopulse
    addi.l #11184811, %d5 /* round((.25/48)*2^31); provisional internal forcing scale */
.Lnopulse:
    moveq #0, %d0
    move.l %d0, %acc0
    move.l %d0, %acc1
    mac.l %d4, %d2, %acc0
    mac.l %d5, %d3, %acc0
    mac.l %d5, %d2, %acc1
    msac.l %d4, %d3, %acc1
    move.l %a5, %d0
    move.l %a3, %d1
    mac.l %d0, %d1, %acc0
    move.l %a2, %d1
    mac.l %d0, %d1, %acc1
    movclr.l %acc0, %d4
    movclr.l %acc1, %d5
    move.l #2146128341, %d1 /* exp(-1/(48000*.033)) */
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d1
    cmp.l %d0, %d1
    bne.s .Lnode_decay
    moveq #0, %d1 /* Clear only a rounding fixed point, not a fitted tail threshold. */
.Lnode_decay:
    movea.l %d1, %a5
    move.l %d4, (%a1)+
    subq.l #1, %d6
    bne .Lsample
    cmpa.l #32, %a4
    bne .Lstore_body
    /* Preserve physical capacitor voltage at the frequency switch.
     * n=sigma/omega_attack; log/rational series errors are below Q31 audio error.
     * shortcut: effective damping, not the complete feedback shelf.
     */
    move.l #2147167893, %d0 /* cos(omega_attack/fs) */
    sub.l %d2, %d0
    move.l %d0, %d6
    lsr.l #1, %d6
    asl.l #6, %d0
    moveq #0, %d1
    move.l %d1, %acc0
    move.l #1956964868, %d1 /* fs/(64*omega_attack*cos(omega_attack/fs)) */
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d0
    move.l %d0, %acc0
    mac.l %d0, %d6, %acc0 /* -log(rho) = (1-rho)*(1+(1-rho)/2+...) */
    movclr.l %acc0, %d0
    mac.l %d0, %d0, %acc0
    movclr.l %acc0, %d2 /* z=n*n */
    mac.l %d2, %d2, %acc0
    movclr.l %acc0, %d3 /* z*z */
    move.l %d2, %d6
    sub.l %d3, %d6
    asl.l #2, %d6
    move.l #781089281, %d1 /* 1/r, r=omega_attack/omega_normal */
    move.l %d1, %acc0
    move.l #1280770858, %d1 /* (r-1/r)/4 */
    mac.l %d6, %d1, %acc0
    movclr.l %acc0, %d6 /* alpha = 1/r+(r-1/r)*(z-z*z) */
    sub.l %d2, %d3
    addi.l #2147483647, %d3
    mac.l %d0, %d3, %acc0
    movclr.l %acc0, %d3
    asl.l #2, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3 /* -beta = (r-1/r)*n*(1-z+z*z) */
    mac.l %d5, %d6, %acc0
    msac.l %d4, %d3, %acc0
    movclr.l %acc0, %d5
    move.l %a5, %d0
    subi.l #536870912, %d0 /* 15 V envelope falls; D52 does not clamp the negative edge. */
    movea.l %d0, %a5
.Lstore_body:
    move.l %d4, (%a0)
    move.l %d5, 4(%a0)
    move.l %d7, 8(%a0)
    move.l %a5, 12(%a0)
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
