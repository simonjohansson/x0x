// Private diagnostic: R4 is a byte-addressed output pointer, R8 sample bits.
.SECTION/SW diagnostic_code;
.GLOBAL x0x_diagnostic.;
x0x_diagnostic.:
    R0=R4;
    R1=32;
    R2=4;
write_sample:
    I4=R0;
    DM(I4,M5)=R8;
    R0=R0+R2;
    R1=R1-1;
    IF NE JUMP write_sample;
    RTS;
