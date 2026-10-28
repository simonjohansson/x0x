/* Independent integer specification only; never linked into firmware. */
#include "tables.h"
#include <limits.h>
#include <string.h>
static uint32_t errors;
uint32_t cf_errors(void) { return errors; }
static int64_t round_shift(__int128 n,unsigned bits) {
    __int128 scale=(__int128)1<<bits;
    __int128 q=n>=0?n/scale:-((-n+scale-1)/scale),r=n-q*scale;
    return (int64_t)(q+(r>scale/2 || (r==scale/2 && (q&1))));
}
static int32_t checked(int64_t n) {
    if(n<INT32_MIN || n>INT32_MAX) {++errors;return 0;}
    return (int32_t)n;
}
static int32_t extract(int64_t a) {
    int64_t n=round_shift(a,8);
    if(n<INT32_MIN || n>INT32_MAX) {++errors;return n<0?INT32_MIN:INT32_MAX;}
    return (int32_t)n;
}
static int64_t product(int32_t a,int32_t b) {return round_shift((__int128)2*a*b,24);}
static int32_t mul(int32_t a,int32_t b) {return extract(product(a,b));}
static int32_t dot(const int32_t *a,const int32_t *b,int count) {
    int64_t sum=0;for(int i=0;i<count;++i)sum+=product(a[i],b[i]);return extract(sum);
}
static int32_t horner(const int32_t *p,int32_t u) {
    int32_t y=p[0];for(int i=1;i<4;++i)y=checked((int64_t)mul(y,u)+p[i]);return y;
}
static int32_t fraction(uint32_t a,uint32_t b) {return a>=b?INT32_MAX:(int32_t)(((uint64_t)a<<31)/b);}
static int32_t sine(uint32_t phase) {
    unsigned i=phase>>21;int32_t u=(int32_t)((phase&0x1fffff)<<10);
    return checked((int64_t)cf_sine[i]+mul(cf_sine[i+1]-cf_sine[i],u));
}
static void prepare(int32_t *s,uint32_t tone,uint32_t decay) {
    unsigned cc=decay>>8,f=decay&255;
    unsigned n=16*(cf_coordinate[cc]*256+f*(cf_coordinate[cc<127?cc+1:127]-cf_coordinate[cc]));
    unsigned segment=n/65280;if(segment>15)segment=15;
    int32_t u=fraction(n-segment*65280,65280);
    for(int k=0;k<8;++k)s[7+k]=horner(cf_control+32*segment+4*k,u);
    for(int k=0;k<300;++k)s[52+k]=dot(cf_body+8*k,s+7,8);
    if(tone<256) {
        unsigned j=0;while(j<8 && tone>=(unsigned)cf_low_break[j+1])++j;
        s[4]=horner(cf_low+4*j,fraction(tone-cf_low_break[j],cf_low_break[j+1]-cf_low_break[j]));
    } else s[4]=horner(cf_tone+4*(tone>>8),(int32_t)((tone&255)<<23));
    s[5]=mul(INT32_MAX-s[4],cf_constants[3]);
    s[0]=s[1]=s[2]=s[3]=0;s[6]=1;
    for(int k=0;k<5;++k)s[15+k]=-1;
}
static void envelope(int32_t *s,int g,int32_t *out) {
    const struct cf_group *group=&cf_groups[g];int j=s[group->index/4];
    if(j<0)j=0;
    while(j<group->count-1 && s[0]>=group->segments[19*j+1])++j;
    const int32_t *seg=group->segments+19*j;
    if(j!=s[group->index/4]) {
        for(int c=0;c<group->channels;++c) {
            const int32_t *co=s+(group->coefficient+c*group->stride)/4+j;
            int32_t b[4];for(int k=0;k<4;++k)b[k]=dot(seg+3+4*k,co,4);
            int32_t *p=s+group->cache/4+4*c;
            p[0]=checked((int64_t)b[3]-3LL*b[2]+3LL*b[1]-b[0]);
            p[1]=checked(3LL*(b[2]-2LL*b[1]+b[0]));
            p[2]=checked(3LL*(b[1]-(int64_t)b[0]));p[3]=b[0];
        }
        s[group->index/4]=j;
    }
    int32_t u=(int32_t)((uint32_t)(s[0]-seg[0])*(uint32_t)seg[2]);
    for(int c=0;c<group->channels;++c)out[c]=horner(s+group->cache/4+4*c,u);
}
void cf_reference(int32_t *s,int32_t *output,uint32_t start,uint32_t tone,uint32_t decay,uint32_t model) {
    if(!output)return;
    if(!s || start>1 || tone>32512 || decay>32512 || model>32512) {memset(output,0,128);return;}
    if(start) {if(model>=16384)s[6]=2;else prepare(s,tone,decay);}
    if(s[6]!=1) {memset(output,0,128);return;}
    for(int i=0;i<32;++i) {
        if(s[0]>=264000) {output[i]=0;continue;}
        int32_t onset=0,body=0,v[2];
        if(s[0]<1440) {envelope(s,0,v);onset=v[0];}
        uint32_t phase=(uint32_t)s[1];
        if(s[0]>=960) {
            for(int h=1;h<=3;++h) {
                envelope(s,h,v);
                int32_t part=checked((int64_t)mul(v[0],sine(phase*h))+mul(v[1],sine(phase*h+0x40000000u)));
                body=checked((int64_t)body+part);
            }
            envelope(s,4,v);body=checked((int64_t)body+v[0]);
        }
        int32_t x;
        if(s[0]<960)x=onset;
        else if(s[0]>=1440)x=body;
        else {
            int32_t u=(int32_t)((uint32_t)(s[0]-960)*((1u<<31)/480));
            int32_t b=mul(u,u),c=mul(b,u),fade=checked((int64_t)b+2LL*(b-c));
            x=checked((int64_t)onset+mul(body-onset,fade));
        }
        int32_t a=checked(2LL*mul(x,s[5])),y=checked((int64_t)a+s[3]);
        s[3]=checked((int64_t)mul(y,s[4])-mul(a,cf_constants[2]));
        output[i]=checked((int64_t)y*128);
        uint64_t phase64=((uint64_t)(uint32_t)s[1]<<32)|(uint32_t)s[2];
        phase64+=((uint64_t)(uint32_t)cf_constants[0]<<32)|(uint32_t)cf_constants[1];
        s[1]=(int32_t)(phase64>>32);s[2]=(int32_t)phase64;++s[0];
    }
}
