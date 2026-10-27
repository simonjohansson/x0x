/* Private diagnostic: void render(int32_t *out, int32_t sample_word). */
    .text
    .globl x0x_diagnostic
    .type x0x_diagnostic, @function
x0x_diagnostic:
    movea.l 4(%sp), %a0
    move.l 8(%sp), %d0
    moveq #31, %d1
.Lsample:
    move.l %d0, (%a0)+
    subq.l #1, %d1
    bpl.s .Lsample
    rts
    .size x0x_diagnostic, .-x0x_diagnostic
