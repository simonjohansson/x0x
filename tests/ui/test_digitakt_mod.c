#include <assert.h>
#include <stdint.h>
#include <string.h>
#include "digitakt-mk1/core3.h"
extern const struct cm_machine x0x_dt_machine;
extern void x0x_dt_render(int32_t *);
volatile uint8_t fw_render_machine[8];
volatile uint32_t fw_voice_start;
const char cm_ui_v3[]="test";
static int32_t values[8][8];
static uint32_t calls[8],starts[8],tones[8],decays[8],which[8],attacks[8];
static int32_t *owners[8];
int32_t cm_src_value(int32_t track,int32_t knob) {return values[track][knob];}
void x0x_silence(int32_t *out) {memset(out,0,128);}
static void record(int32_t *state,int32_t *out,uint32_t start,uint32_t tone,uint32_t decay,uint32_t model)
{
    unsigned slot=0;while(slot<8 && owners[slot] && owners[slot]!=state) ++slot;
    assert(slot<8);owners[slot]=state;++calls[slot];starts[slot]=start;tones[slot]=tone;decays[slot]=decay;which[slot]=model;
    for(unsigned i=0;i<32;++i) out[i]=(int32_t)model;
}
void x0x_field808(int32_t *s,int32_t *o,uint32_t a,uint32_t t,uint32_t d,uint32_t m)
{assert(m==0);record(s,o,a,t,d,808);}
void x0x_field909(int32_t *s,int32_t *o,uint32_t a,uint32_t t,uint32_t d,uint32_t attack)
{record(s,o,a,t,d,909);for(unsigned i=0;i<8;++i)if(owners[i]==s)attacks[i]=attack;}
int main(void)
{
    const struct cm_machine *m=&x0x_dt_machine;
    assert(m->id==20 && m->render==20 && m->params==3 && m->tag==CM_UI_TAG);
    assert(!strcmp(m->name,"X0X KICKS") && !strcmp(m->sname,"KICKS"));
    assert(m->ui->abi==cm_ui_v3 && m->ui->page_from==3 && !m->ui->on_switch);
    const char *labels[]={"TNTUN","DECAY","ATTK",0,0,"MODEL",0,0};
    for(unsigned k=0;k<8;++k) if(labels[k]) {
        const struct cm_knob *knob=&m->ui->knob[k];
        assert(!strcmp(knob->name,labels[k]) && knob->min==0 && knob->max==32512);
        assert(knob->def==(k==5?0:16384));
    }
    int32_t guarded[258];for(unsigned k=0;k<258;++k) guarded[k]=123;
    fw_render_machine[0]=fw_render_machine[7]=20;
    values[0][0]=12345;values[0][1]=17001;values[7][5]=32512;values[7][0]=23456;values[7][1]=7890;values[7][2]=5432;
    x0x_dt_render(guarded+1);assert(!calls[0]);
    fw_voice_start=(1u<<7)|1;x0x_dt_render(guarded+1);
    assert(calls[0]==1 && calls[1]==1 && starts[0] && starts[1]);
    assert(tones[0]==12345 && decays[0]==17001 && which[0]==808 && which[1]==909);
    assert(tones[1]==23456 && decays[1]==7890 && attacks[1]==5432);
    assert(guarded[0]==123 && guarded[257]==123 && guarded[33]==123);
    fw_voice_start=0;values[0][5]=32512;values[7][5]=0;x0x_dt_render(guarded+1);
    assert(which[0]==808 && which[1]==909 && !starts[0]);
    values[0][0]=-1;fw_voice_start=1;unsigned before=calls[0];x0x_dt_render(guarded+1);
    assert(calls[0]==before && guarded[1]==0);
    fw_render_machine[0]=0;x0x_dt_render(guarded+1);
    fw_render_machine[0]=20;fw_voice_start=0;values[0][0]=12345;x0x_dt_render(guarded+1);
    assert(calls[0]==before && guarded[1]==0);
    fw_voice_start=1;x0x_dt_render(guarded+1);assert(which[0]==909 && calls[0]==before+1);
    values[0][5]=0;values[0][2]=0;fw_voice_start=1;x0x_dt_render(guarded+1);
    assert(which[0]==808);before=calls[0];values[0][5]=32512;values[0][2]=-1;
    x0x_dt_render(guarded+1);assert(calls[0]==before && guarded[1]==0);
    fw_voice_start=0;x0x_dt_render(guarded+1);assert(calls[0]==before+1 && which[0]==808);
    return 0;
}
