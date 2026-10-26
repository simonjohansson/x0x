/* Private selector test ABI, no firmware IDs or saved positions.
 * int x0z_selector(bank*, notice*, input*), normal m68k C stack arguments.
 * bank: 8 x {uint32 initialized, model, diagnostic_tail}; caller zeroes ownership.
 * input: {lane, delivered_raw_MODEL, delivered_trigger, delivery_status}.
 * delivery_status: 0 missing, 1 fresh, 2 stale, classified by the caller.
 * notice: {model, initialize, model_changed, clear_tail}, written only on APPLY.
 * Pointers must name valid, aligned, disjoint caller-owned extents (null fails).
 * return: 0 invalid, 1 apply, 2 missing, 3 stale, 4 wait for first trigger.
 * Model 0=808, 1=909. Only MODEL changes clear old tail; same-model triggers
 * do not classify native ownership or implement analog retrigger behavior.
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
    lea -12(%sp), %sp
    move.l 16(%sp), %d0
    move.l %d0, 0(%sp)
    move.l 20(%sp), %d0
    move.l %d0, 4(%sp)
    move.l 24(%sp), %d0
    move.l %d0, 8(%sp)
    bsr x0z_selector
    lea 12(%sp), %sp
    movea.l 16(%sp), %a0
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
    .size x0z_diagnostic, .-x0z_diagnostic

    .globl x0z_selector
    .type x0z_selector, @function
x0z_selector:
    lea -16(%sp), %sp
    movem.l %d2-%d4/%a2, (%sp)
    movea.l 20(%sp), %a0
    movea.l 24(%sp), %a1
    movea.l 28(%sp), %a2
    moveq #0, %d0
    cmpa.l #0, %a0
    beq .Ldone
    cmpa.l #0, %a1
    beq .Ldone
    cmpa.l #0, %a2
    beq .Ldone
    move.l 12(%a2), %d1
    tst.l %d1
    beq .Lmissing
    cmpi.l #2, %d1
    beq .Lstale
    cmpi.l #1, %d1
    bne .Ldone
    move.l (%a2), %d2
    cmpi.l #7, %d2
    bhi .Ldone
    move.l 4(%a2), %d3
    cmpi.l #32512, %d3
    bhi .Ldone
    move.l 8(%a2), %d4
    cmpi.l #1, %d4
    bhi .Ldone
    move.l %d2, %d1
    add.l %d2, %d1
    add.l %d2, %d1
    lsl.l #2, %d1
    adda.l %d1, %a0 /* selected lane */
    move.l (%a0), %d1
    cmpi.l #1, %d1
    bhi .Ldone
    tst.l %d1
    beq .Lfirst
    move.l 4(%a0), %d1
    cmpi.l #1, %d1
    bhi .Ldone
    tst.l %d4
    beq .Lcontinued
    bra .Lselect
.Lfirst:
    tst.l %d4
    beq .Lwait
.Lselect:
    cmpi.l #16384, %d3 /* MODEL threshold */
    bcs .L808
    moveq #1, %d3
    bra .Lselected
.L808:
    moveq #0, %d3
.Lselected:
    tst.l (%a0)
    beq .Linitialize
    cmp.l 4(%a0), %d3
    beq .Lcontinued
    moveq #1, %d2
    move.l %d2, 8(%a1) /* model changed */
    clr.l 4(%a1)
    bra .Lclear
.Linitialize:
    moveq #1, %d2
    move.l %d2, (%a0)
    move.l %d2, 4(%a1)
    clr.l 8(%a1)
.Lclear:
    clr.l 8(%a0) /* diagnostic tail only */
    move.l %d2, 12(%a1)
    move.l %d3, 4(%a0)
    move.l %d3, (%a1)
    bra .Lapplied
.Lcontinued:
    move.l 4(%a0), %d3
    move.l %d3, (%a1)
    clr.l 4(%a1)
    clr.l 8(%a1)
    clr.l 12(%a1)
.Lapplied:
    moveq #1, %d0
    bra .Ldone
.Lmissing:
    moveq #2, %d0
    bra .Ldone
.Lstale:
    moveq #3, %d0
    bra .Ldone
.Lwait:
    moveq #4, %d0
.Ldone:
    movem.l (%sp), %d2-%d4/%a2
    lea 16(%sp), %sp
    rts
    .size x0z_selector, .-x0z_selector
