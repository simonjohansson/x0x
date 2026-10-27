/* Private fixed-block no-op renderer; only the selected track's 32 samples. */
    .text
    .globl x0x_silence
    .type x0x_silence, @function
x0x_silence:
    movea.l 4(%sp), %a0
    moveq #32, %d0
.Lzero:
    clr.l (%a0)+
    subq.l #1, %d0
    bne .Lzero
    rts
    .size x0x_silence, .-x0x_silence
