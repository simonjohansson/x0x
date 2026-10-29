// Diagnostic only: one 704-byte frozen record inside the existing voice owner.
// 0x2009f800..fc00 is unused by tables/states; the builder checks this placement.
.SECTION/SW seg_swco;
.GLOBAL x0x_capture_voice_exit;
.GLOBAL x0x_capture_frame;
.EXTERN field_state_base.;
x0x_capture_voice_exit:
    I4=DM(0x2009fac8);       // context saved before the normal kernel
    R0=I4;
    R0=PASS R0;
    IF EQ JUMP voice_return;
    R1=DM(1,I4);
    R0=16;
    COMPU(R1,R0);
    IF GE JUMP voice_return;
    R0=DM(0,I4);
    R0=PASS R0;
    IF EQ JUMP voice_return;
    R0=LSHIFT R1 BY 9;
    R2=DM(field_state_base.);
    R0=R0+R2;
    R2=DM(5,I4);
    COMP(R0,R2);
    IF NE JUMP voice_return;
    R0=DM(3,I4);
    R0=PASS R0;
    IF EQ JUMP continuing;
    R2=1;
    COMP(R0,R2);
    IF NE JUMP voice_return;
    DM(0x2009f804)=R2;       // invalidate the previous snapshot before rearming
    R2=DM(0x2009fac4);
    R2=R2+1;
    DM(0x2009fac4)=R2;
    DM(0x2009f808)=R2;
    DM(0x2009f80c)=R1;
    R0=150;
    DM(0x2009f824)=R0;
    DM(0x2009f828)=R0;
continuing:
    R0=DM(0x2009f804);
    R2=1;
    COMP(R0,R2);
    IF NE JUMP voice_return;
    R0=DM(0x2009f80c);
    COMP(R0,R1);
    IF NE JUMP voice_return;
    R0=DM(0x2009f828);
    R0=R0-1;
    DM(0x2009f828)=R0;
    IF NE JUMP voice_return;
    R0=DM(0,I4);
    DM(0x2009f82c)=R0;
    I0=R0;
    I1=0x2009f840;
    R3=32;
raw_copy:
    R0=DM(I0,M6);
    DM(I1,M6)=R0;
    R3=R3-1;
    IF NE JUMP raw_copy;
    I0=DM(5,I4);
    R0=DM(61,I0);           // model tag: 1=808, 2=909
    DM(0x2009f810)=R0;
    R1=1;
    COMP(R0,R1);
    IF EQ JUMP age808;
    R0=DM(0,I0);
    JUMP age_ready;
age808:
    R0=DM(58,I0);
age_ready:
    DM(0x2009f820)=R0;
    R0=DM(0x2009fac0);
    R0=R0+1;
    DM(0x2009f814)=R0;
    R0=2;
    DM(0x2009f804)=R0;       // raw block ready for this handler's end hook
voice_return:
    I12=DM(M7,I6);
    JUMP(M14,I12)(DB);
    RFRAME;
    NOP;

// Same scratch registers as the existing peek; R1/R2/I4/I6/I12 stay live.
// No MODE, interrupt, hardware-loop or software-stack changes here.
x0x_capture_frame:
    R10=DM(0x2009fac0);
    R10=R10+1;
    DM(0x2009fac0)=R10;
    R11=DM(0x2009f804);
    R13=2;
    COMP(R11,R13);
    IF NE JUMP 0x170000;
    R11=DM(0x2009f814);
    COMP(R10,R11);
    IF NE JUMP stale;
    // The stock ping-pong selector must name one of the two PCM banks.
    R11=DM(0x268a38);
    R13=1;
    COMPU(R11,R13);
    IF GT JUMP stale;
    DM(0x2009f838)=R11;
    R13=LSHIFT R11 BY 8;
    R14=0x2c0478;
    R13=R13+R14;
    DM(0x2009f834)=R13;
    DM(0x2009f818)=R10;
    DM(0x2009f81c)=R10;
    R11=L2;
    DM(0x2009facc)=R11;
    R11=L3;
    DM(0x2009fad0)=R11;
    L2=0;
    L3=0;
    I2=0x268438;
    R11=I2;
    DM(0x2009f830)=R11;
    I3=0x2009f8c0;
    R15=64;
master_copy:
    R11=DM(0,I2);
    DM(0,I3)=R11;
    I2=MODIFY(I2,4);
    I3=MODIFY(I3,4);
    R15=R15-1;
    IF NE JUMP master_copy;
    // 0x268a38 still names the completed bank: original peek toggles it later.
    I2=DM(0x2009f834);
    I3=0x2009f9c0;
    R15=64;
pcm_copy:
    R11=DM(0,I2);
    DM(0,I3)=R11;
    I2=MODIFY(I2,4);
    I3=MODIFY(I3,4);
    R15=R15-1;
    IF NE JUMP pcm_copy;
    L2=DM(0x2009facc);
    L3=DM(0x2009fad0);
    R11=DM(0x2009f808);
    DM(0x2009f83c)=R11;      // matching generation at both ends of the header
    R11=3;
    DM(0x2009f804)=R11;      // publish only after all three copies complete
    JUMP 0x170000;           // existing peek, busy accounting and displaced store
stale:
    R11=4;
    DM(0x2009f804)=R11;
    JUMP 0x170000;
.ENDSEG;
