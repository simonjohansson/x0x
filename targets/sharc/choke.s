// Private per-track metadata in unused state words 124..127 (both engines).
// A 128-sample ramp retires old hits without continuing their synthesis.
.SECTION/SW seg_swco;
.GLOBAL x0x_choke_start.;
.GLOBAL x0x_choke_block.;
.GLOBAL x0x_voice_done.;
.EXTERN field_state_base.;
.EXTERN x0x_render_return.;
.EXTERN x0x_silent.;

// Preserve the delivered controls, descriptor, flags and output/state pointers.
x0x_choke_start.:
    I0=R2;
    R8=DM(39,I0);
    I0=R15;
    R0=0;
    DM(124,I0)=R0;
    DM(125,I0)=R0;
    DM(126,I0)=R0;
    DM(127,I0)=R0;
    R0=0xa500;
    COMP(R8,R0);
    IF LT JUMP choke_start_done;
    R0=0xa50f;
    COMP(R8,R0);
    IF GT JUMP choke_start_done;
    DM(124,I0)=R8;
    R10=DM(field_state_base.);
    R11=16;
choke_other:
    COMP(R10,R15);
    IF EQ JUMP choke_next;
    I0=R10;
    R0=DM(124,I0);
    COMP(R0,R8);
    IF NE JUMP choke_next;
    R0=DM(125,I0);
    R0=PASS R0;
    IF NE JUMP choke_next;
    R0=1;
    DM(125,I0)=R0;
    R0=128;
    DM(126,I0)=R0;
choke_next:
    R0=512;
    R10=R10+R0;
    R11=R11-1;
    IF NE JUMP choke_other;
choke_start_done:
    RTS;

x0x_choke_block.:
    R13=DM(126,I4);
    R13=PASS R13;
    IF EQ JUMP x0x_silent.;
    R1=DM(127,I4);
    R2=0x3c000000;
    I0=R14;
    R12=32;
choke_ramp:
    R13=R13-1;
    F0=FLOAT R13;
    F0=F0*F2;
    F0=F0*F1;
    DM(I0,M6)=R0;
    R12=R12-1;
    IF NE JUMP choke_ramp;
    DM(126,I4)=R13;
    R14=I0;
    JUMP x0x_render_return.;

x0x_voice_done.:
    I0=R14;
    R0=DM(-1,I0);
    I0=R15;
    DM(127,I0)=R0;
    JUMP x0x_render_return.;
