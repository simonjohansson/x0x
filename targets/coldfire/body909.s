/* Diode-shaped 909 triangle at 48 kHz: provisional 50 Hz, live unloaded C8 Decay, gain .25.
 * void x0x_909_body(int32_t state[2], int32_t output[32], uint32_t start, uint32_t decay_raw).
 * State is {unsigned phase, Q1.31 amplitude}; caller owns aligned disjoint extents.
 * shortcut: START resets to a rising zero crossing; replace the fixed pitch,
 * unloaded envelope/taper and restart when the full circuit is implemented.
 * Clear a rounding-induced constant-amplitude fixed point to retain eventual silence.
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
    /* D = 1489.96 + 31680*t, t=raw/32512; Q16 D fits unsigned32. */
    move.l 92(%sp), %d6
    move.l #66052, %d0
    mulu.l %d0, %d6
    move.l #2076180480, %d0
    moveq #0, %d3
    move.l %d3, %acc0
    mac.l %d6, %d0, %acc0
    movclr.l %acc0, %d3
    addi.l #97646019, %d3
    /* Loss = 2/D, using unsigned fractional division including the carry bit. */
    move.l #131072, %d2
    moveq #0, %d7
    moveq #31, %d6
.L909divide:
    add.l %d7, %d7
    add.l %d2, %d2
    bcs.s .L909subtract
    cmp.l %d3, %d2
    bcs.s .L909nextbit
.L909subtract:
    sub.l %d3, %d2
    addq.l #1, %d7
.L909nextbit:
    subq.l #1, %d6
    bne.s .L909divide
    move.l #0x80000000, %d2
    sub.l %d7, %d2
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
    moveq #0, %d0
    move.l %d0, %acc0
    move.l %d5, %d7
    mac.l %d5, %d2, %acc0
    movclr.l %acc0, %d5
    /* A decaying RC must not retain a constant quantization residue forever. */
    cmp.l %d7, %d5
    bne.s .L909decaying
    moveq #0, %d5
.L909decaying:
    mac.l %d5, %d3, %acc0
    movclr.l %acc0, %d0
    move.l %d0, (%a1)+
    subq.l #1, %d6
    bne .L909sample
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
    .size x0x_909_body, .-x0x_909_body
