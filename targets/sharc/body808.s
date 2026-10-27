// First provisional 808 resonator/Tone and unshaped 909 triangle bodies.
// Per slot: {callback count since model change, selected code}; 0=inactive, 1=808, 2=909.
// Metadata L2; body +128, Tone +256, coupling +320, counters +448, C39 nodes +512.
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
    R13=LSHIFT R2 BY 2;
    R0=0x20092100;
    R13=R13+R0;
    R0=LSHIFT R2 BY 3;
    R1=0x20092140;
    R0=R0+R1;
    I3=R0;
    R1=4;
    R0=R0+R1;
    I5=R0;

    R3=LSHIFT R2 BY 3;
    R6=0x20092000;
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
    R0=LSHIFT R2 BY 2;
    R1=0x200921c0;
    R0=R0+R1;
    I4=R0;
    R0=0;
    DM(I4,M5)=R0;
    R0=LSHIFT R2 BY 2;
    R1=0x20092200;
    R0=R0+R1;
    I4=R0;
    R0=0;
    DM(I4,M5)=R0;
    // shortcut: reset Tone on START until residual-state retrigger and logical ownership are qualified.
    I4=R13;
    R0=0;
    DM(I4,M5)=R0;
    DM(I3,M5)=R0;
    DM(I5,M5)=R0;
    R0=16384;
    COMP(R14,R0);
    IF LT JUMP select_808;
    R14=2;
    JUMP compare_model;
select_808:
    R14=1;
compare_model:
    COMP(R14,R6);
    IF EQ JUMP selected;    // Same-model START retains the diagnostic callback count.
    R9=0;                  // First initialization or model change, this slot only.
    R6=R14;
    R0=128;
    R0=R3+R0;
    I4=R0;
    R1=0;
    DM(I4,M5)=R1;
    R1=4;
    R0=R0+R1;
    I4=R0;
    R1=0;
    DM(I4,M5)=R1;
selected:
    R0=R9+1;
    I4=R3;
    DM(I4,M5)=R0;
    R0=4;
    R3=R3+R0;
    I4=R3;
    DM(I4,M5)=R6;
    R0=1;
    COMP(R6,R0);
    IF NE JUMP body909;
    I4=R15;
    R6=DM(I4,M5);
    R0=4;
    R0=R15+R0;
    I4=R0;
    R11=DM(I4,M5);
    F11=FLOAT R11;
    R12=0x38010204;
    F11=F11*F12;
    R0=124;
    R14=R3+R0;
    R0=4;
    R15=R14+R0;
    R4=0x20092080;
    R4=R14-R4;
    R5=-1;
    R4=LSHIFT R4 BY R5;
    R5=0x200921c0;
    R4=R4+R5;
    I0=R4;
    R7=PASS R7;
    IF EQ JUMP continue_body;
    // shortcut: 1 ms rectangular drive; edge shaping, physical forcing/gain and residual retrigger follow.
    R0=0;
    R1=0;
    R4=288;
    DM(I0,M5)=R4;
    R4=I0;
    R5=64;
    R4=R4+R5;
    I4=R4;
    R4=0x3c41e099; // .71 V / 60; ideal positive D52 clamp
    DM(I4,M5)=R4;
    JUMP render_body;
continue_body:
    I4=R14;
    R0=DM(I4,M5);
    I4=R15;
    R1=DM(I4,M5);
render_body:
    I1=R15;
    // shortcut: three training anchors, not the stock feedback network/pot curve.
    // Use c-1 to avoid float32 radius bias when c is close to one.
    // S03 equation7/section8.1: nominal 131.006 Hz for 6 ms, then 47.65 Hz.
    R2=0x3f010204; // 64/127, the approved default in the existing raw/32512 normalization.
    COMP(F11,F2);
    IF GE JUMP decay_high;
    R4=DM(I0,M5);
    R4=PASS R4;
    IF EQ JUMP steady_low;
    R2=0x3a7986e6;
    R3=0xba4a7914;
    R4=0x3788f17b;
    R5=0x3c8c6323;
    R14=0xb5b16be3;
    R15=0xbab5dd3f;
    R4=0xb8a19fdd;
    I12=R4;
    R4=0x3883262d;
    I13=R4;
    R4=0x3788f17b;
    JUMP decay_coefficients;
steady_low:
    R2=0x3a798f0c;
    R3=0xba290c80;
    R4=0x36c73f05;
    R5=0x3bcc41cb;
    R14=0xb5b16dd2;
    R15=0xbab5df3a;
    R4=0xb95e3583;
    I12=R4;
    R4=0x391685d9;
    I13=R4;
    R4=0x36c73f05;
    JUMP decay_coefficients;
decay_high:
    R4=DM(I0,M5);
    R4=PASS R4;
    IF EQ JUMP steady_high;
    R2=0x393b9629;
    R3=0xb9c8b858;
    R4=0x364de63d;
    R5=0x3c8c7126;
    R14=0xb4856141;
    R15=0xbab5ef66;
    R4=0xb773022b;
    I12=R4;
    R4=0x38020432;
    I13=R4;
    R4=0x364de63d;
    JUMP decay_coefficients;
steady_high:
    R2=0x393b9c4a;
    R3=0xb985d886;
    R4=0x3595c97c;
    R5=0x3bcc562d;
    R14=0xb48562b5;
    R15=0xbab5f161;
    R4=0xb8270cc1;
    I12=R4;
    R4=0x386e5b47;
    I13=R4;
    R4=0x3595c97c;
decay_coefficients:
    F2=F2*F11;
    F2=F2+F3;
    F3=F4*F11;
    F3=F3+F5;
    // Source-separated C39 continuous-input integral, at the same Decay anchors.
    F14=F14*F11;
    F14=F14+F15;
    R15=I12;
    R4=I13;
    F15=F15*F11;
    F15=F15+F4;
    // shortcut: resistance-linear bright-up Tone mapping until the C-taper is calibrated.
    // Physical RC TPT coefficient: (2-t)/(102.224-99.112*t), t=raw/32512.
    F6=FLOAT R6;
    R11=0x38010204;
    F6=F6*F11;
    R11=0x40000000;
    F4=F11-F6;
    R11=0x42c63958;
    F5=F11*F6;
    R11=0x42cc72b0;
    F5=F11-F5;
    // Positive normal-float reciprocal seed, refined without an undocumented ROM lookup.
    R6=0x7f000000;
    R6=R6-R5;
    R11=0x40000000;
    F12=F5*F6;
    F12=F11-F12;
    F6=F6*F12;
    F12=F5*F6;
    F12=F11-F12;
    F6=F6*F12;
    F12=F5*F6;
    F12=F11-F12;
    F6=F6*F12;
    F12=F5*F6;
    F12=F11-F12;
    F6=F6*F12;
    F11=F4*F6;
    I4=R13;
    R12=DM(I4,M5);
    I2=R13;
    // Unloaded C47=.47uF into fixed wide-open VR4=100k; full output loading remains open.
    R7=DM(I3,M5);
    R10=DM(I5,M5);
    R9=32;
    R13=4;
    R4=DM(I0,M5);
    I12=R4;
    R4=I0;
    R5=64;
    R4=R4+R5;
    I4=R4;
    R4=DM(I4,M5);
    I13=R4;
body_sample:
    R4=DM(I0,M5);
    R4=PASS R4;
    IF EQ JUMP no_pulse;
    R4=R4-1;
    DM(I0,M5)=R4;
    R5=240;
    COMP(R4,R5);
    IF LT JUMP no_pulse;
    R4=0x3baaaaab;
    F1=F1+F4;
no_pulse:
    F4=F2*F0;
    F5=F3*F1;
    F4=F4+F5;
    F4=F0+F4;
    F5=F2*F1;
    F6=F3*F0;
    F5=F5-F6;
    F1=F1+F5;
    R5=I13;
    F6=F14*F5;
    F4=F4+F6;
    F6=F15*F5;
    F1=F1+F6;
    R0=R4;
    R6=0x3f7fd6a4; // exp(-1/(48000*.033))
    F5=F5*F6;
    I13=R5;
    F4=F0-F12;
    F4=F11*F4;
    F5=F12+F4;
    F12=F5+F4;
    F4=F5-F7;
    R7=R5;
    R6=0x3f7ff17a;
    F4=F6*F4;
    R6=0x3f7fe2f5;
    F10=F6*F10;
    F10=F10+F4;
    I4=R8;
    DM(I4,M5)=R10;
    R8=R8+R13;
    R9=R9-1;
    IF NE JUMP body_sample;
    R4=I12;
    R5=32;
    COMP(R4,R5);
    IF NE JUMP store_body;
    // Preserve C41/C42 voltage using effective damping, not a full feedback shelf.
    R4=0xb91a2d6a; // cos(omega_attack/fs)-1
    F4=F4-F2;
    R5=0x426949d4; // fs/(omega_attack*cos(omega_attack/fs))
    F5=F4*F5;
    R6=0x3f000000;
    F4=F4*F6;
    F4=F4*F5;
    F2=F5+F4;      // n=sigma/omega_attack, second-order log approximation
    F3=F2*F2;
    F4=F3*F3;
    F5=F3-F4;
    R6=0x4018ae06; // r-1/r
    F5=F5*F6;
    R11=0x3eba39e8; // 1/r
    F5=F5+F11;     // alpha
    F4=F4-F3;
    R11=0x3f800000;
    F4=F4+F11;
    F4=F4*F2;
    F4=F4*F6;      // -beta
    F1=F1*F5;
    F4=F4*F0;
    F1=F1-F4;
    R4=I13;
    R5=0x3e800000;
    F4=F4-F5;
    I13=R4;
store_body:
    R4=I1;
    R4=R4-R13;
    I4=R4;
    DM(I4,M5)=R0;
    DM(I1,M5)=R1;
    DM(I2,M5)=R12;
    DM(I3,M5)=R7;
    DM(I5,M5)=R10;
    R4=I0;
    R5=64;
    R4=R4+R5;
    I4=R4;
    R4=I13;
    DM(I4,M5)=R4;
    JUMP finish;
body909:
    R0=4;
    R0=R15+R0;
    I4=R0;
    R11=DM(I4,M5);
    F11=FLOAT R11;
    R12=0x38010204;
    F11=F11*F12;
    R0=124;
    R14=R3+R0;
    R0=4;
    R15=R14+R0;
    R7=PASS R7;
    IF EQ JUMP continue909;
    // shortcut: fixed pitch and zero-crossing START until the complete 909 circuit is modeled.
    R0=0x40000000;
    R1=0x3e800000;
    JUMP render909;
continue909:
    I4=R14;
    R0=DM(I4,M5);
    I4=R15;
    R1=DM(I4,M5);
render909:
    // Unloaded C8*(R58+VR5*t) discharge; resistance-linear taper remains provisional.
    R4=0x46f78000;
    F2=F11*F4;
    R4=0x44ba3eb8;
    F2=F2+F4;
    R3=0x7f000000;
    R3=R3-R2;
    R4=0x40000000;
    F5=F2*F3;
    F5=F4-F5;
    F3=F3*F5;
    F5=F2*F3;
    F5=F4-F5;
    F3=F3*F5;
    F5=F2*F3;
    F5=F4-F5;
    F3=F3*F5;
    F5=F2*F3;
    F5=F4-F5;
    F3=F3*F5;
    R4=0xc0000000;
    F2=F3*F4;
    R3=4473924;
    R9=32;
    R10=4;
sample909:
    R0=R0+R3;
    R4=LSHIFT R0 BY 1;
    R5=0x80000000;
    R4=R4 XOR R5;
    R0=PASS R0;
    IF GE JUMP rising909;
    R4=NOT R4;
rising909:
    R5=-31;
    F4=FLOAT R4 BY R5;
    F5=F1*F2;
    F1=F1+F5;
    F4=F4*F1;
    I4=R8;
    DM(I4,M5)=R4;
    R8=R8+R10;
    R9=R9-1;
    IF NE JUMP sample909;
    I4=R14;
    DM(I4,M5)=R0;
    I4=R15;
    DM(I4,M5)=R1;
    JUMP finish;
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
