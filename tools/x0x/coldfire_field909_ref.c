/* Independent integer specification only. Never linked into firmware. */
#include "tables909.h"
#include "tables.h"
#include <limits.h>
#include <string.h>
static uint32_t errors;
uint32_t cf9_errors(void) { return errors; }
static int64_t round_shift(__int128 n,unsigned bits) {
    __int128 scale=(__int128)1<<bits;
    __int128 q=n>=0?n/scale:-((-n+scale-1)/scale),r=n-q*scale;
    return (int64_t)(q+(r>scale/2 || (r==scale/2 && (q&1))));
}
static int32_t checked(int64_t n) {
    if(n<INT32_MIN || n>INT32_MAX) {++errors;return 0;}
    return (int32_t)n;
}
static int64_t product(int32_t a,int32_t b) {return round_shift((__int128)2*a*b,24);}
static int32_t extract(int64_t a) {return checked(round_shift(a,8));}
static int32_t mul(int32_t a,int32_t b) {return extract(product(a,b));}
static int32_t dot(const int32_t *a,const int32_t *b,int count) {
    int64_t sum=0;for(int i=0;i<count;++i)sum+=product(a[i],b[i]);return extract(sum);
}
static int32_t horner(const int32_t *p,int32_t u) {
    int32_t y=p[0];for(int i=1;i<4;++i)y=checked((int64_t)mul(y,u)+p[i]);return y;
}
static int32_t coordinate(unsigned raw) {
    unsigned cc=raw>>8,f=raw&255;
    unsigned a=cf_coordinate[cc],b=cf_coordinate[cc<127?cc+1:127];
    unsigned n=a*256+f*(b-a);
    return n>=65280?INT32_MAX:(int32_t)(((uint64_t)n<<31)/65280);
}
static int cell(int32_t x,unsigned bits,int32_t *u) {
    *u=(int32_t)(((uint32_t)x<<bits)&INT32_MAX);
    return (int)((uint32_t)x>>(31-bits));
}
static int32_t sine(uint32_t phase) {
    unsigned i=phase>>21;int32_t u=(int32_t)((phase&0x1fffff)<<10);
    return checked((int64_t)cf_sine[i]+mul(cf_sine[i+1]-cf_sine[i],u));
}
static int32_t fade(int age) {
    if(age<=0)return 0;if(age>=96)return INT32_MAX;
    int32_t u=age*(INT32_MAX/96),b=mul(u,u),c=mul(b,u);
    return checked((int64_t)b+2LL*(b-c));
}
static void prepare(int32_t *s,unsigned tune,unsigned decay,unsigned attack) {
    s[54]=(int32_t)tune;s[55]=(int32_t)attack;s[56]=(int32_t)decay;
    int32_t u;int j=cell(coordinate(tune),4,&u);
    s[31]=horner(cf9_phase+12*j,u);s[5]=horner(cf9_phase+12*j+4,u);
    s[6]=(int32_t)(((uint32_t)s[5]<<4)+(uint32_t)s[31]);
    s[4]=(horner(cf9_phase+12*j+8,u)+128)>>8;
    s[0]=s[1]=s[2]=s[29]=0;s[3]=INT32_MAX;s[7]=-1;s[61]=2;
    s[52]=cell(coordinate(tune),3,s+48);s[53]=cell(coordinate(attack),3,s+49);
    for(int r=0;r<12;++r) {
        const int32_t *p=cf9_onset_control+((s[52]*8+s[53])*12+r)*16;int32_t temporary[4];
        for(int k=0;k<4;++k)temporary[k]=horner(p+4*k,s[49]);
        s[16+r]=horner(temporary,s[48]);
    }
    s[51]=cell(coordinate(decay),4,s+50);
    for(int r=0;r<5;++r)s[8+r]=horner(cf9_control+20*s[51]+4*r,s[50]);
}
static void cache(int32_t *s) {
    int j=0;while(s[0]>=cf9_frames[j+1])++j;
    s[7]=j;s[28]=cf9_frames[j];s[29]=cf9_frames[j+1];s[30]=cf9_inverse[j];
    for(int c=0;c<11;++c) {
        for(int k=0;k<4;++k)s[37+k]=dot(cf9_body+5*(c*30+j+k),s+8,5);
        int32_t diff[3];for(int k=0;k<3;++k)diff[k]=checked((int64_t)s[37+k]-s[40]);
        for(int k=0;k<4;++k) {
            int32_t p=checked((int64_t)dot(cf9_time+j*12+3*k,diff,3)*8);
            s[64+4*c+k]=k==3?checked((int64_t)p+s[40]):p;
        }
    }
}
static int32_t onset(int32_t *s) {
    int n=s[0],u=0;if(n>=320) {u=((n-320)&3)<<29;n=320+((n-320)>>2);}
    const int32_t *p=cf9_onset+12*n;
    int32_t a=dot(p,s+16,12),b=dot(p+12,s+16,12);
    return checked((int64_t)a+mul(b-a,u));
}
void cf9_reference(int32_t *s,int32_t *out,uint32_t start,uint32_t tune,uint32_t decay,uint32_t attack) {
    if(!out)return;
    if(!s || start>1 || tune>32512 || decay>32512 || attack>32512) {memset(out,0,128);return;}
    if(start)prepare(s,tune,decay,attack);
    if(s[61]!=2) {memset(out,0,128);return;}
    for(int i=0;i<32;++i) {
        if(s[0]>=96000) {out[i]=0;continue;}
        int32_t body=0;
        if(s[0]>=288) {
            if(s[0]>=s[29])cache(s);
            uint32_t phase=(uint32_t)s[1]+(uint32_t)s[6]-((uint32_t)mul(s[5],s[3])<<4);
            s[31]=(int32_t)phase;
            int32_t u=(int32_t)((uint32_t)(s[0]-s[28])*(uint32_t)s[30]);
            body=horner(s+64,u);
            for(unsigned h=1;h<=5;++h) {
                body=checked((int64_t)body+mul(horner(s+64+4*(2*h-1),u),sine(h*phase)));
                body=checked((int64_t)body+mul(horner(s+64+8*h,u),sine(h*phase+0x40000000u)));
            }
            body=checked((int64_t)body*2);
        }
        s[35]=body;
        int32_t value=body;
        if(s[0]<1152) {
            int32_t click=onset(s);s[36]=click;
            value=checked((int64_t)mul(body,fade(s[0]-288))+mul(click,INT32_MAX-fade(s[0]-1056)));
        }
        if(value>=0x08000000)out[i]=INT32_MAX;
        else if(value<=-0x08000000)out[i]=INT32_MIN;
        else out[i]=checked((int64_t)value*16);
        s[3]=checked((int64_t)s[3]-mul(s[3],s[4]));
        uint64_t phase=((uint64_t)(uint32_t)s[1]<<32)|(uint32_t)s[2];
        phase+=((uint64_t)(uint32_t)cf9_step[0]<<32)|(uint32_t)cf9_step[1];
        s[1]=(int32_t)(phase>>32);s[2]=(int32_t)phase;++s[0];
    }
}
