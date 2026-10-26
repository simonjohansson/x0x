/* Private fixed-block no-op renderer; only the selected track's 32 samples. */
    .text
    .globl x0z_silence
    .type x0z_silence, @function
x0z_silence:
    movea.l 4(%sp), %a0
    moveq #32, %d0
.Lzero:
    clr.l (%a0)+
    subq.l #1, %d0
    bne .Lzero
    rts
    .size x0z_silence, .-x0z_silence
