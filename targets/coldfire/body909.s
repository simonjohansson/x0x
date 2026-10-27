/* C9/IC12-controlled 909 triangle, finite R51 reset and loaded C8/Q12 VCA.
 * void x0x_909_body(int32_t state[4], int32_t output[32], uint32_t start,
 *                   uint32_t decay_raw, uint32_t tune_raw).
 * State: phase Q32, C8/64 Q31, C9/15V Q31, trigger samples remaining.
 * Q10 PNP OFF on comparator HIGH makes raw C14 rise; IC11a inverts the audio.
 * shortcut: START clears charges; switch drops, pot taper and retrigger
 * circuit behavior remain provisional.
 */
    .text
    .globl x0x_909_body
    .type x0x_909_body, @function
x0x_909_body:
    lea -140(%sp), %sp
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
    movea.l 144(%sp), %a0
    movea.l 148(%sp), %a1
    move.l (%a0), %d4
    move.l 4(%a0), %d5
    movea.l 8(%a0), %a3
    movea.l 12(%a0), %a4
    tst.l 152(%sp)
    beq.s .L909continue
    move.l #0x40000000, %d4
    moveq #0, %d5
    suba.l %a3, %a3
    movea.l #96, %a4
.L909continue:
    move.l #0xb0, %d0 /* fractional, saturated, nearest-even */
    move.l %d0, %macsr
    move.l 156(%sp), %d6
    move.l #66052, %d0
    mulu.l %d0, %d6
    move.l #2076180480, %d0
    moveq #0, %d3
    move.l %d3, %acc0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d3
    addi.l #97580483, %d3
    move.l #16384, %d2
    moveq #0, %d7
    moveq #31, %d6
.Lvca_divide:
    add.l %d7, %d7
    add.l %d2, %d2
    bcs .Lvca_subtract
    cmp.l %d3, %d2
    bcs .Lvca_nextbit
.Lvca_subtract:
    sub.l %d3, %d2
    addq.l #1, %d7
.Lvca_nextbit:
    subq.l #1, %d6
    bne .Lvca_divide
    lea .Lvca_constants(%pc), %a2
    lea 100(%sp), %a5
    moveq #5, %d6
.Lvca_coefficients:
    move.l (%a2)+, %d0
    add.l %d7, %d0
    move.l %d0, %d1
    mac.l %d1, %d1, %acc0
    movclr.l %acc0, %d2
    mac.l %d2, %d1, %acc0
    movclr.l %acc0, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d0
    sub.l %d2, %d1
    add.l %d3, %d1
    sub.l %d0, %d1
    neg.l %d1
    add.l %d1, %d1
    move.l %d1, (%a5)+
    asr.l #1, %d1
    move.l (%a2)+, %d0
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d2
    add.l %d0, %d2
    move.l %d2, (%a5)+
    subq.l #1, %d6
    bne .Lvca_coefficients
    /* C9 off conductance, Q31. R57+VR2 is Q14. */
    move.l 160(%sp), %d7
    move.l #66052, %d0
    mulu.l %d0, %d7
    move.l #1638400000, %d0
    mac.l %d7, %d0, %acc0
    movclr.l %acc0, %d3
    addi.l #360448000, %d3
    move.l #1034343, %d2
    moveq #0, %d7
    moveq #31, %d6
.L909tune_divide:
    add.l %d7, %d7
    add.l %d2, %d2
    bcs.s .L909tune_subtract
    cmp.l %d3, %d2
    bcs.s .L909tune_nextbit
.L909tune_subtract:
    sub.l %d3, %d2
    addq.l #1, %d7
.L909tune_nextbit:
    subq.l #1, %d6
    bne.s .L909tune_divide
    addi.l #410829, %d7
    move.l %d7, %d1
    bsr .L909tune_coeff
    move.l %d6, 76(%sp)
    move.l #21385359, %d6
    mac.l %d0, %d6, %acc0
    movclr.l %acc0, %d7
    sub.l %d7, %d6
    move.l %d6, 80(%sp)
    addi.l #61624301, %d1
    bsr .L909tune_coeff
    move.l %d6, 84(%sp)
    move.l #57926843, %d6
    mac.l %d0, %d6, %acc0
    movclr.l %acc0, %d7
    sub.l %d7, %d6
    move.l %d6, 88(%sp)
    bsr .L909reset_coeff
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d0
    move.l #1866836429, %d6
    sub.l %d0, %d6
    move.l #21385358, %d7
    mac.l %d6, %d7, %acc0
    movclr.l %acc0, %d6
    move.l %d6, 92(%sp)
    move.l #576855, %d6
    mac.l %d3, %d6, %acc0
    movclr.l %acc0, %d6
    addi.l #4089927, %d6
    move.l %d6, 96(%sp)
    lea 100(%sp), %a5
    movea.l #32, %a6
.L909sample:
    move.l %a4, %d0
    move.l %d0, %d2
    tst.l %d0
    bne.s .L909tune_on
    move.l 76(%sp), %d0
    moveq #0, %d1
    move.l 80(%sp), %d7
    moveq #0, %d3
    bra.s .L909tune_flow
.L909tune_on:
    move.l 84(%sp), %d0
    move.l 88(%sp), %d1
    move.l 92(%sp), %d7
    move.l 96(%sp), %d3
.L909tune_flow:
    move.l %a3, %d6
    mac.l %d7, %d6, %acc0
    movclr.l %acc0, %d7
    add.l %d3, %d7
    move.l %a4, %d3
    tst.l %d3
    beq.s .L909free_phase
    move.l %d4, %d3
    subi.l #0x40000000, %d3
    move.l #1611775306, %d0
    mac.l %d3, %d0, %acc0
    movclr.l %acc0, %d3
    move.l 84(%sp), %d0
    add.l %d7, %d3
    move.l #0x40000000, %d4
    add.l %d3, %d4
    subq.l #1, %a4
    bra.s .L909phase_ready
.L909free_phase:
    addi.l #4704779, %d7
    add.l %d7, %d4
.L909phase_ready:
    mac.l %d0, %d6, %acc0
    movclr.l %acc0, %d0
    add.l %d1, %d0
    cmp.l %d0, %d6
    bne.s .L909tune_store
    move.l %a4, %d7
    tst.l %d7
    bne.s .L909tune_store
    moveq #0, %d0
.L909tune_store:
    movea.l %d0, %a3
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
    /* R52/D10/D11 passive-loaded KCL curve, before the envelope. */
    move.l %d3, %d1
    bpl.s .L909magnitude
    neg.l %d1
    bpl.s .L909magnitude
    move.l #0x7fffffff, %d1
.L909magnitude:
    move.l %d1, %d7
    moveq #27, %d0
    lsr.l %d0, %d1
    lsl.l #4, %d1
    lea .L909shape_table(%pc), %a2
    adda.l %d1, %a2
    lsl.l #4, %d7
    andi.l #0x7fffffff, %d7
    moveq #0, %d0
    move.l %d0, %acc0
    move.l 12(%a2), %d0
    mac.l %d0, %d7, %acc0
    movclr.l %acc0, %d0
    add.l 8(%a2), %d0
    mac.l %d0, %d7, %acc0
    movclr.l %acc0, %d0
    add.l 4(%a2), %d0
    mac.l %d0, %d7, %acc0
    movclr.l %acc0, %d0
    add.l (%a2), %d0
    tst.l %d3
    bpl.s .L909shaped
    neg.l %d0
.L909shaped:
    move.l %d0, %d3
    moveq #4, %d7
.Lvca_quarter:
    moveq #0, %d0
    tst.l %d2
    beq .Lvca_off
    cmpi.l #431368647, %d5
    bge .Lvca_off
    moveq #32, %d0
    cmpi.l #87123788, %d5
    bgt .Lvca_apply
    moveq #24, %d0
    cmpi.l #20132659, %d5
    bgt .Lvca_apply
    moveq #16, %d0
    bra .Lvca_apply
.Lvca_off:
    cmpi.l #20132659, %d5
    ble .Lvca_apply
    moveq #8, %d0
.Lvca_apply:
    movea.l %a5, %a2
    adda.l %d0, %a2
    move.l (%a2), %d0
    mac.l %d5, %d0, %acc0
    movclr.l %acc0, %d1
    add.l %d1, %d5
    add.l 4(%a2), %d5
    subq.l #1, %d7
    bne .Lvca_quarter
    move.l %d5, %d7
    subi.l #20132659, %d7
    bpl .Lvca_amplitude_ready
    moveq #0, %d7
.Lvca_amplitude_ready:
    mac.l %d7, %d3, %acc0
    movclr.l %acc0, %d0
    neg.l %d0 /* Q12 conductance into IC11a's minus summing node. */
    move.l %d0, (%a1)+
    subq.l #1, %a6
    move.l %a6, %d6
    tst.l %d6
    bne .L909sample
    move.l %d4, (%a0)
    move.l %d5, 4(%a0)
    move.l %a3, 8(%a0)
    move.l %a4, 12(%a0)
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
    lea 140(%sp), %sp
    rts
    /* Stable (1-(1-exp(-x))/x)/x, x <= .0318. */
.L909tune_coeff:
    move.l #2982616, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #-17895697, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #89478485, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #-357913941, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #1073741824, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d0
    mac.l %d0, %d1, %acc0
    movclr.l %acc0, %d6
    sub.l %d1, %d6
    addi.l #0x80000000, %d6
    rts
.L909reset_coeff:
    move.l #-411278, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #2864596, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #-17073671, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #84579016, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #-333643103, %d3
    mac.l %d3, %d1, %acc0
    movclr.l %acc0, %d3
    addi.l #977999427, %d3
    rts
    .balign 4
.L909shape_table:
    .long 0,134208257,116,-1498
    .long 134206875,134203994,-4044,-2846
    .long 268403979,134187368,-11843,-6745
    .long 402572759,134143446,-30294,-16650
    .long 536669262,134032910,-75926,-41120
    .long 670585126,133757699,-189289,-100009
    .long 804053527,133079093,-468805,-233650
    .long 936430164,131440532,-1140454,-495841
    .long 1066234401,127672100,-2630885,-847961
    .long 1190427655,119866448,-5285163,-929644
    .long 1304079296,106507190,-8186880,-374137
    .long 1402025470,89011020,-9254079,327440
    .long 1482109850,71485181,-8179017,599872
    .long 1546015886,56926762,-6343350,548094
    .long 1597147392,45884345,-4696942,412084
    .long 1638746878,37726712,-3467184,291918
    .balign 4
.Lvca_constants:
    .long 0,0
    .long 36057,676
    .long 16946683,7467132
    .long 16982740,7467808
    .long 19037976,7634571
    .size x0x_909_body, .-x0x_909_body
