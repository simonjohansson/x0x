#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "../../machines/digitone/adapter.h"

extern const struct dnm_machine x0x_dn_machine;
extern void x0x_dn_begin(void), x0x_dn_capture(int16_t *words), x0x_dn_ready(int32_t *voices), x0x_dn_end(void);
volatile int16_t fw_voice_params[9 + 8 * CORE_PARAMS_VOICE];
#if __BYTE_ORDER__ == __ORDER_LITTLE_ENDIAN__
#define WORD(p, o, v) [60*(p)+(o)] = (v)&255, [60*(p)+(o)+1] = ((v)>>8)&255
#else
#define WORD(p, o, v) [60*(p)+(o)+2] = ((v)>>8)&255, [60*(p)+(o)+3] = (v)&255
#endif
#define RECORD(p, slot) WORD(p, 4, slot), WORD(p, 12, 32512)
const uint8_t fw_params[134 * 60] __attribute__((aligned(4))) = {
    RECORD(119, 27), RECORD(120, 28), RECORD(121, 29), RECORD(124, 32)
};
static unsigned count,kind,started,tone,decay,attack_value;
int32_t dnm_knob(int32_t s,int32_t k) {(void)s;(void)k;assert(0);return 0;}
void dnm_knob_range(int32_t k,int32_t *l,int32_t *h) {(void)k;(void)l;(void)h;assert(0);}
void x0x_silence(int32_t *out) {memset(out,0,128);}
static void record(int32_t *s,int32_t *o,uint32_t a,uint32_t t,uint32_t d,unsigned model)
{assert(s);++count;kind=model;started=a;tone=t;decay=d;for(unsigned k=0;k<32;++k)o[k]=model;}
void x0x_field808(int32_t *s,int32_t *o,uint32_t a,uint32_t t,uint32_t d,uint32_t m)
{assert(m==0);record(s,o,a,t,d,808);}
void x0x_field909(int32_t *s,int32_t *o,uint32_t a,uint32_t t,uint32_t d,uint32_t attack)
{record(s,o,a,t,d,909);attack_value=attack;}
int main(void)
{
    const struct dnm_machine *m=&x0x_dn_machine;
    assert(m->id==80 && !strcmp(m->name,"X0X KICKS") && !m->flags && !m->icon);
    assert(!strcmp(m->knobs[8].name,"TNTUN") && !strcmp(m->knobs[13].name,"MODEL"));
    assert(m->defaults[8]==16384 && m->defaults[9]==16384 && m->defaults[13]==0);
    int16_t words[8*CORE_PARAMS_VOICE]={0};
    struct dnm_voice voice={60<<16,100,1,2,1};
    int32_t out[34];for(unsigned i=0;i<34;++i)out[i]=12345;
    FW_VOICE_PARAM(3,0)=80<<8;
    words[3*79+27]=12345;words[3*79+28]=17001;words[3*79+29]=23456;
    x0x_dn_begin();x0x_dn_capture(words);x0x_dn_ready(0);
    m->render(3,out+1,&voice);assert(count==1 && kind==808 && started && tone==12345 && decay==17001);
    assert(out[0]==12345 && out[33]==12345 && out[1]==808);
    voice.fresh=0;words[3*79+32]=32512;m->render(3,out+1,&voice);
    assert(count==2 && kind==808 && !started);
    voice.fresh=1;m->render(3,out+1,&voice);assert(count==3 && kind==909 && started && attack_value==23456);
    x0x_dn_end();m->render(3,out+1,&voice);assert(count==3 && !out[1]);
    words[3*79+32]=0;x0x_dn_begin();x0x_dn_capture(words);x0x_dn_ready(0);
    m->render(3,out+1,&voice);assert(count==4 && kind==808);
    voice.track=1;voice.fresh=0;m->render(3,out+1,&voice);assert(count==4 && !out[1]);
    voice.fresh=1;m->render(3,out+1,&voice);assert(count==5 && kind==808);
    words[3*79+32]=32512;words[3*79+29]=-1;
    m->render(3,out+1,&voice);assert(count==5 && !out[1]);
    words[3*79+29]=16384;voice.fresh=0;m->render(3,out+1,&voice);
    assert(count==6 && kind==808); /* Failed 909 START must not commit the tag. */
    FW_VOICE_PARAM(3,0)=0;x0x_dn_begin();FW_VOICE_PARAM(3,0)=80<<8;
    x0x_dn_capture(words);x0x_dn_ready(0);voice.fresh=0;
    m->render(3,out+1,&voice);assert(count==6 && !out[1]);
    return 0;
}
