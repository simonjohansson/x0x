// Combined-model selector diagnostic; not a kick renderer.
// Per slot: {diagnostic tail count, selected code}; 0=inactive, 1=808, 2=909.
// SDK input is in R4. State is author-owned L2, 16 pairs, initially zero.
.SECTION/SW callback_code;
.GLOBAL sharc_voice_render.;
sharc_voice_render.:
    R4=PASS R4;
    IF EQ JUMP finish;
    I4=R4;
    R8=DM(I4,M5);
    R0=4;
    R1=R4+R0;
    I4=R1;
    R2=DM(I4,M5);
    R1=R1+R0;
    I4=R1;
    R5=DM(I4,M5);
    R1=R1+R0;
    I4=R1;
    R7=DM(I4,M5);
    R1=R1+R0;
    I4=R1;
    R15=DM(I4,M5);

    // Reject unsigned metadata before calculating a slot address.
    R0=0xfffffff0;
    R0=R2 AND R0;
    R0=PASS R0;
    IF NE JUMP silent;
    R0=0xffff0000;
    R0=R5 AND R0;
    R0=PASS R0;
    IF NE JUMP silent;
    R0=0xfffffffe;
    R0=R7 AND R0;
    R0=PASS R0;
    IF NE JUMP silent;
    R15=PASS R15;
    IF EQ JUMP silent;

    // Validate TNTUN/DECAY/ATTK/MODEL atomically, skipping blank D/E.
    R9=R15;
    R10=0;
    R11=32512;
    R12=0xffff8000;
validate_word:
    R13=3;
    COMP(R10,R13);
    IF EQ JUMP next_word;
    R13=4;
    COMP(R10,R13);
    IF EQ JUMP next_word;
    I4=R9;
    R0=DM(I4,M5);
    R1=R0 AND R12;
    R1=PASS R1;
    IF NE JUMP silent;
    COMP(R0,R11);
    IF GT JUMP silent;
next_word:
    R13=4;
    R9=R9+R13;
    R10=R10+1;
    R13=6;
    COMP(R10,R13);
    IF LT JUMP validate_word;
    R14=R0;                 // Last validated word was MODEL, parameter 5.

    R3=LSHIFT R2 BY 3;
    R6=0x20092800;
    R3=R3+R6;
    I4=R3;
    R9=DM(I4,M5);
    R0=4;
    R1=R3+R0;
    I4=R1;
    R6=DM(I4,M5);
    R0=0xfffffffc;
    R0=R6 AND R0;
    R0=PASS R0;
    IF NE JUMP silent;
    R0=3;
    COMP(R6,R0);
    IF EQ JUMP silent;

    R7=PASS R7;
    IF NE JUMP starting;
    R6=PASS R6;
    IF EQ JUMP silent;      // No initialized behavior before the first START.
    JUMP selected;
starting:
    R0=16384;
    COMP(R14,R0);
    IF LT JUMP select_808;
    R14=2;
    JUMP compare_model;
select_808:
    R14=1;
compare_model:
    COMP(R14,R6);
    IF EQ JUMP selected;    // Same-model START preserves the diagnostic tail.
    R9=0;                  // First initialization or model change, this slot only.
    R6=R14;
selected:
    // Diagnostic checksum of delivered model controls plus prior tail count.
    // 808 ignores ATTK. Pitch and all undeclared positions have no effect.
    I4=R15;
    R0=DM(I4,M5);
    R1=R0+R9;
    R10=4;
    R15=R15+R10;
    I4=R15;
    R0=DM(I4,M5);
    R1=R1+R0;
    R0=2;
    COMP(R6,R0);
    IF NE JUMP commit;
    R15=R15+R10;
    I4=R15;
    R0=DM(I4,M5);
    R1=R1+R0;
commit:
    R0=R9+1;
    I4=R3;
    DM(I4,M5)=R0;
    R0=4;
    R3=R3+R0;
    I4=R3;
    DM(I4,M5)=R6;
    R7=-17;
    F0=FLOAT R1 BY R7;
    JUMP output;
silent:
    R0=0;
output:
    R9=32;
    R10=4;
write_sample:
    I4=R8;
    DM(I4,M5)=R0;
    R8=R8+R10;
    R9=R9-1;
    IF NE JUMP write_sample;
finish:
    I12=DM(M7,I6);
    JUMP(M14,I12) (DB);
    RFRAME;
    NOP;
