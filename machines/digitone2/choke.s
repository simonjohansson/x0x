| DN2 1.12: the completed outgoing frame, before core's unchanged DSP transfer.
    .section .text
    .globl x0x_frame_owner
x0x_frame_owner:
    lea -20(%sp),%sp
    movem.l %d0-%d1/%a0-%a1,(%sp)
    move.w %sr,%d0
    move.l %d0,16(%sp)
    pea 0x40288305
    pea 0x80005e60
    jsr x0x_tag_frame
    addq.l #8,%sp
    move.l 16(%sp),%d0
    move.w %d0,%sr
    movem.l (%sp),%d0-%d1/%a0-%a1
    lea 20(%sp),%sp
    pea 0x80005e60
    jmp 0x40025e9a
