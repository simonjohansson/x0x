/* Provisional 808 body: damped 47.65 Hz sine at 48 kHz with live decay.
 * void x0x_808_body(int32_t state[5], int32_t output[32], uint32_t start, uint32_t decay_raw).
 * decay_raw is caller-bounded to 0..32512; default 16384 gives tau = 143 ms.
 * State is {Q31 x,y,initial_samples_remaining,Q31 C39 node,Q31 C40 node}; 15 V encodes as .25 FS.
 * shortcut: source-separated inputs and fixed 14 V trigger;
 * effective reference-calibrated Q43 hard knee; full feedback/loading and residual retrigger follow in #9/#79.
 */
    /* Exact held-source Q43 flow: capacitor q1 stays fixed during this kick. */
    .macro leakage_half after=0
    cmpa.l #0, %a4
    bne 9f
    move.l %a6, %d0
    addi.l #38680434, %d0 /* Effective negative common-node knee magnitude .018011980654 FS. */
    move.l %d0, %acc2
    move.l 84(%sp), %d1
    mac.l %d4, %d1, %acc2
    move.l 88(%sp), %d1
    mac.l %d5, %d1, %acc2
    movclr.l %acc2, %d0
    .if \after
    move.l 112(%sp), %d1
    cmpi.l #16384, %d1
    bls .Lleakage_clamp_\@
    cmpi.l #32512, %d1
    bcc .Lleakage_clamp_\@
    move.l %acc3, %d1
    move.l %d0, %acc3
    tst.l %d0
    bmi .Lnegative_end_\@
    tst.l %d1
    bpl .Lno_crossing_\@
    neg.l %d1
    bra .Lcrossing_\@
.Lnegative_end_\@:
    tst.l %d1
    ble .Lno_crossing_\@
    neg.l %d0
.Lcrossing_\@:
    /* Integrate a linear threshold crossing instead of its full-sample trapezoid. */
    move.l %d1, %acc0
    move.l %d0, %acc1
    add.l %d0, %d1
    move.l %acc0, %d0
    moveq #0, %d7
    movea.l #31, %a4
.Lcrossing_divide_\@:
    add.l %d7, %d7
    add.l %d0, %d0
    bcs .Lcrossing_subtract_\@
    cmp.l %d1, %d0
    bcs .Lcrossing_next_\@
.Lcrossing_subtract_\@:
    sub.l %d1, %d0
    addq.l #1, %d7
.Lcrossing_next_\@:
    subq.l #1, %a4
    cmpa.l #0, %a4
    bne .Lcrossing_divide_\@
    move.l %acc1, %d0
    mac.l %d0, %d7, %acc2
    movclr.l %acc2, %d0
    moveq #0, %d7
    move.l %acc3, %d1
    tst.l %d1
    bmi .Lcrossing_add_\@
    moveq #0, %d1
.Lcrossing_add_\@:
    add.l %d1, %d0
    bra .Lleakage_gain_\@
.Lno_crossing_\@:
    move.l %acc3, %d0
    .else
    move.l %d0, %acc3
    .endif
.Lleakage_clamp_\@:
    tst.l %d0
    bpl 9f
.Lleakage_gain_\@:
    move.l #65614840, %d1 /* Effective lambda/(2*fs), lambda=2933.211912981/s. */
    mac.l %d0, %d1, %acc2
    movclr.l %acc2, %d0
    add.l %d0, %d4
    move.l 92(%sp), %d1
    mac.l %d0, %d1, %acc2
    movclr.l %acc2, %d0
    sub.l %d0, %d5
9:
    .endm
    .text
    .globl x0x_808_body
    .type x0x_808_body, @function
x0x_808_body:
    lea -96(%sp), %sp
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
    movea.l 100(%sp), %a0
    movea.l 104(%sp), %a1
    move.l (%a0), %d4
    move.l 4(%a0), %d5
    move.l 8(%a0), %d7
    tst.l 108(%sp)
    beq.s .Lcontinue
    moveq #0, %d4
    moveq #0, %d5
    move.l #288, %d7
    move.l #25411890, %d0 /* .71 V / 60; positive D52 clamp at START */
    move.l %d0, 12(%a0)
    move.l #501079518, %d0 /* 14 V / 60, fresh C40 rising edge */
    move.l %d0, 16(%a0)
.Lcontinue:
    move.l #0xb0, %d0 /* fractional, saturated, nearest-even */
    move.l %d0, %macsr
    /* Empirical lower tau and upper retention curves preserve the existing anchors. */
    move.l 112(%sp), %d6
    cmpi.l #4096, %d6
    bcs .Ldecay_short
    cmpi.l #16384, %d6
    bge .Ldecay_high
    move.l #131072, %d0 /* low branch excludes 16384, keeping the product signed-positive */
    mulu.l %d0, %d6
    /* tau=.0333+(.143-.0333)*q; keep the audio/state recurrence. */
    move.l %d6, %d1 /* Preserve x until the lower-coordinate correction. */
    moveq #0, %d0
    move.l %d0, %acc0
    mac.l %d6, %d6, %acc0
    movclr.l %acc0, %d6 /* x*x */
    /* Empirical q=x*x+1.5*x*x*(1-x), preserving both endpoints. */
    move.l #2147483647, %d0
    sub.l %d1, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d0 /* x*x*(1-x) */
    move.l #805306368, %d1 /* k/4 in Q31: bounded training calibration k=1.5. */
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d0
    lsl.l #2, %d0
    add.l %d0, %d6 /* q replaces only the existing squared coordinate. */
    move.l #71511205, %d0
    move.l %d0, %acc0
    move.l #235578956, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d2 /* tau in Q31 seconds */
    move.l #307090162, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d3 /* .143*q */
    /* t_sigma=.143*q/tau, unsigned fractional division. */
    moveq #0, %d6
    moveq #31, %d1
.Ldecay_divide:
    add.l %d6, %d6
    add.l %d3, %d3
    bcs.s .Ldecay_subtract
    cmp.l %d2, %d3
    bcs.s .Ldecay_next
.Ldecay_subtract:
    sub.l %d2, %d3
    addq.l #1, %d6
.Ldecay_next:
    subq.l #1, %d1
    bne.s .Ldecay_divide
    /* Convert damping position to retention position, second-order exp ratio. */
    move.l #2147483647, %d0
    sub.l %d6, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d1
    move.l #515329, %d0 /* (1/.0333-1/.143)/(2*48000), Q31 */
    mac.l %d1, %d0, %acc0
    movclr.l %acc0, %d0
    sub.l %d0, %d6
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
.Ldecay_short:
    move.l #524288, %d0 /* short branch excludes 4096, keeping the product signed-positive */
    mulu.l %d0, %d6
    move.l %d6, %d1 /* Preserve x until the short-coordinate correction. */
    moveq #0, %d0
    move.l %d0, %acc0
    mac.l %d6, %d6, %acc0
    movclr.l %acc0, %d6 /* x*x */
    /* Match retention and its slope at raw4096; q is the new segment coordinate. */
    move.l #2147483647, %d0
    sub.l %d1, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d0 /* x*x*(1-x) */
    move.l #873619983, %d1 /* k/4 in Q31: C1 short-segment retention shape. */
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d0
    lsl.l #2, %d0
    add.l %d0, %d6 /* q replaces only the existing squared coordinate. */
    tst.l %d7
    beq .Lsteady_short
    move.l #2144842869, %d2
    move.l #36784832, %d3
    move.l #1390757, %d0
    movea.l #23852, %a2
    movea.l #-2978300, %a3
    movea.l #-1931, %a4
    movea.l #213815, %a5
    movea.l #-112603, %a6
    bra .Ldecay_coefficients
.Lsteady_short:
    move.l #2145116554, %d2
    move.l #13380060, %d3
    move.l #1390934, %d0
    movea.l #8676, %a2
    movea.l #-2978427, %a3
    movea.l #-1931, %a4
    movea.l #526921, %a5
    movea.l #-309625, %a6
    bra .Ldecay_coefficients
.Ldecay_high:
    subi.l #16384, %d6
    move.l #133152, %d0 /* floor(2^31 / 16128) */
    mulu.l %d0, %d6
    move.l 112(%sp), %d0
    cmpi.l #32512, %d0
    beq.s .Ldecay_high_shaped /* Keep the exact maximum anchor. */
    /* Upper duration curve q=p+k*p*(1-p), sharing all existing coefficient banks. */
    moveq #0, %d0
    move.l %d0, %acc0
    move.l #2147483647, %d0
    sub.l %d6, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d0
    move.l #2039958712, %d1
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d0
    add.l %d0, %d6
.Ldecay_high_shaped:
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
    /* Main exponential-input and ON-bias gains, quadratic over each Decay segment. */
    move.l 112(%sp), %d0
    cmpi.l #4096, %d0
    bcs .Lmain_short
    cmpi.l #16384, %d0
    bge .Lmain_high
    tst.l %d7
    beq.s .Lmain_steady_low
    lea .Lmain_attack_low(%pc), %a6
    bra.s .Lmain_interpolate
.Lmain_steady_low:
    lea .Lmain_steady_low_data(%pc), %a6
    bra.s .Lmain_interpolate
.Lmain_high:
    tst.l %d7
    beq.s .Lmain_steady_high
    lea .Lmain_attack_high(%pc), %a6
    bra.s .Lmain_interpolate
.Lmain_steady_high:
    lea .Lmain_steady_high_data(%pc), %a6
    bra .Lmain_interpolate
.Lmain_short:
    tst.l %d7
    beq .Lmain_steady_short
    lea .Lmain_attack_short_data(%pc), %a6
    bra .Lmain_interpolate
.Lmain_steady_short:
    lea .Lmain_steady_short_data(%pc), %a6
    bra .Lmain_interpolate
.Lmain_interpolate:
    move.l #2147483647, %d0
    sub.l %d6, %d0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d1 /* t*(1-t) */
    move.l (%a6)+, %d0
    move.l %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d6, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d1, %d0, %acc0
    movclr.l %acc0, %d0
    move.l %d0, 76(%sp)
    move.l (%a6)+, %d0
    move.l %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d6, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d1, %d0, %acc0
    movclr.l %acc0, %d0
    move.l %d0, 80(%sp)
    move.l (%a6)+, %d0
    move.l %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d6, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d1, %d0, %acc0
    movclr.l %acc0, %d0
    move.l %d0, 84(%sp)
    move.l (%a6)+, %d0
    move.l %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d6, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d1, %d0, %acc0
    movclr.l %acc0, %d0
    move.l %d0, 88(%sp)
    tst.l %d7
    bne .Lleakage_ready
    move.l 112(%sp), %d0
    cmpi.l #4096, %d0
    bcs .Lleakage_short
    cmpi.l #16384, %d0
    bge.s .Lleakage_high
    lea .Lleakage_low_data(%pc), %a6
    bra.s .Lleakage_coefficients
.Lleakage_high:
    lea .Lleakage_high_data(%pc), %a6
    bra .Lleakage_coefficients
.Lleakage_short:
    lea .Lleakage_short_data(%pc), %a6
.Lleakage_coefficients:
    /* Cubic remainder reduces coefficient error before output calibration. */
    move.l %d6, %d0
    subi.l #1073741824, %d0
    mac.l %d1, %d0, %acc0
    movclr.l %acc0, %d7 /* t*(1-t)*(t-.5); steady branch has counter zero. */
    /* ON biases are unused in the steady stage; reuse their stack words. */
    move.l (%a6)+, %d0
    move.l %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d6, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d1, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d7, %d0, %acc0
    movclr.l %acc0, %d0
    move.l %d0, 84(%sp)
    move.l (%a6)+, %d0
    move.l %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d6, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d1, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d7, %d0, %acc0
    movclr.l %acc0, %d0
    move.l %d0, 88(%sp)
    move.l (%a6)+, %d0
    move.l %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d6, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d1, %d0, %acc0
    move.l (%a6)+, %d0
    mac.l %d7, %d0, %acc0
    movclr.l %acc0, %d0
    move.l %d0, 92(%sp)
    moveq #0, %d7
.Lleakage_ready:
    movea.l 12(%a0), %a5
    movea.l 16(%a0), %a6
    movea.l %d7, %a4
    moveq #32, %d6
.Lsample:
    leakage_half
    tst.l %d7
    beq.s .Lmain_off
    cmpi.l #240, %d7
    bne.s .Lnot_main_fall
    movea.l #-25411890, %a6 /* Ideal D53 negative clamp updates C40 charge. */
.Lnot_main_fall:
    subq.l #1, %d7
    cmpi.l #240, %d7
    blt.s .Lmain_off
    move.l 84(%sp), %d0
    move.l %d0, %acc0
    move.l 88(%sp), %d0
    move.l %d0, %acc1
    bra.s .Lrotate
.Lmain_off:
    moveq #0, %d0
    move.l %d0, %acc0
    move.l %d0, %acc1
.Lrotate:
    mac.l %d4, %d2, %acc0
    mac.l %d5, %d3, %acc0
    mac.l %d5, %d2, %acc1
    msac.l %d4, %d3, %acc1
    move.l %a5, %d0
    move.l %a3, %d1
    mac.l %d0, %d1, %acc0
    move.l %a2, %d1
    mac.l %d0, %d1, %acc1
    move.l %a6, %d0
    move.l 76(%sp), %d1
    mac.l %d0, %d1, %acc0
    move.l 80(%sp), %d1
    mac.l %d0, %d1, %acc1
    movclr.l %acc0, %d4
    movclr.l %acc1, %d5
    move.l %a5, %d0
    move.l #2146128341, %d1
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d1
    cmp.l %d0, %d1
    bne.s .Lnode_decay
    moveq #0, %d1
.Lnode_decay:
    movea.l %d1, %a5
    move.l %a6, %d0
    move.l #1589336992, %d1 /* C40 retention, effective tau=69.21837318138271 us */
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d1
    cmpi.l #240, %d7
    blt.s .Lmain_decay
    addi.l #5846235, %d1 /* ON equilibrium contribution */
    bra.s .Lmain_node_store
.Lmain_decay:
    cmp.l %d0, %d1
    bne.s .Lmain_node_store
    moveq #0, %d1 /* Only clear an OFF rounding fixed point. */
.Lmain_node_store:
    movea.l %d1, %a6
    leakage_half 1
    move.l %a6, %d0
    add.l %d4, %d0 /* Main source direct feedthrough, not part of modal state. */
    move.l %d0, (%a1)+
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
    move.l %a6, 16(%a0)
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
    lea 96(%sp), %sp
    rts
    .balign 4
.Lmain_attack_low:
    .long 395721862,1484983,-307748
    .long -18005560,11054144,-26425
    .long 655183,2343,-509
    .long -27745,18308,-44
.Lmain_attack_high:
    .long 397206846,342200,-10534
    .long -6951416,2052163,-1427
    .long 657526,545,-17
    .long -9437,3399,-2
.Lmain_steady_low_data:
    .long 55262072,1313413,-307761
    .long -5725781,4218944,-78946
    .long 91493,2158,-509
    .long -9374,6987,-131
.Lmain_steady_high_data:
    .long 56575485,310461,-10534
    .long -1506836,801385,-4140
    .long 93651,511,-17
    .long -2387,1327,-7
.Lleakage_low_data:
    .long 47485539,-36322559,508524,-209502
    .long 473421941,4502196,2763962,51387
    .long 215398591,-165239339,-39652,13

.Lleakage_high_data:
    .long 11162980,-6799472,4412,-1375
    .long 477924137,220915,96699,81
    .long 50159252,-30561512,-1356,0
.Lmain_attack_short_data:
    .long 394879193,1358097,-560927
    .long -28518806,14892220,-11539
    .long 653898,2093,-928
    .long -45158,24665,-19
.Lmain_steady_short_data:
    .long 54583005,1126432,-560951
    .long -9665186,5594715,-43198
    .long 90384,1843,-928
    .long -15898,9265,-71
.Lleakage_short_data:
    .long 80627205,-47423645,1772721,-461012
    .long 464180079,11688025,4714554,238553
    .long 373013863,-223173810,-72332,31
    .size x0x_808_body, .-x0x_808_body
