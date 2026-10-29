"""Fixed-point 909 tables and independent integer reference; firmware audio is ASM."""
from pathlib import Path
import ctypes
import hashlib
import json
import math
import os
import numpy as np
from scipy.interpolate import PPoly
from . import cpu,field909,sharc_field808,coldfire_field808

OUT=cpu.ROOT/'out/909-model/coldfire'


def quantize(values,bits):
    q=np.rint(np.asarray(values)*2**bits)
    if not np.isfinite(q).all() or np.any(q<-(1<<31)) or np.any(q>=(1<<31)):
        raise ValueError('909 coefficient exceeds fixed-point range')
    return q.astype('int64')


def power_basis(intervals):
    b=np.linspace(0,1,intervals+1);knots=np.r_[np.repeat(0.,4),b[1:-1],np.repeat(1.,4)]
    count=intervals+3;result=np.empty((intervals,4,count))
    for j in range(count):
        unit=np.zeros(count);unit[j]=1
        result[:,:,j]=PPoly.from_spline((knots,unit,3)).c[:,3:3+intervals].T*(1/intervals)**np.arange(3,-1,-1)
    return result


def hull(p):
    degree=p.shape[-1]-1;a=p[...,::-1]
    return np.stack([sum(a[...,j]*math.comb(i,j)/math.comb(degree,j) for j in range(i+1)) for i in range(degree+1)],axis=-1)


def prefix_bound(p):
    return max(float(abs(hull(p[...,:k])).max()) for k in range(1,p.shape[-1]+1))


def export():
    m=field909.load();basis=field909.decode(m,'body').reshape(5,11,30)
    controls=field909.decode(m,'control');onset_control=field909.decode(m,'onset_control').reshape(12,11,11)
    cp=np.einsum('sik,rk->sri',power_basis(16),controls)
    bp=power_basis(8);joint=np.einsum('sik,rkl,tjl->strij',bp,onset_control,bp)
    inner=prefix_bound(joint)
    outer=max(float(abs(hull(hull(joint[...,:k,:]).swapaxes(-1,-2))).max()) for k in range(1,5))
    # Both intermediate tensor Horner stages must fit, including continuous controls.
    if max(prefix_bound(cp),inner,outer)>=4-1e-5:raise ValueError('909 control Horner range exceeds Q29')
    nodes=np.einsum('rk,rct->kct',controls,basis)
    tp=m['time_poly_q'].astype(float).transpose(0,2,1)/4096
    power=[]
    for segment in range(1,27):
        c=nodes[:,:,segment:segment+4];p=np.einsum('dj,kcj->kcd',tp[segment],c[:,:,:3]-c[:,:,3:])
        p[:,:,3]+=c[:,:,3];power.append(p)
    envelope=prefix_bound(np.asarray(power))
    if envelope>=8-1e-4:raise ValueError('909 body Horner range exceeds Q28')
    pp=m['phase_poly'].astype(float)
    for j,bits in enumerate((32,28,39)):
        if prefix_bound(pp[:,j,:])>=(2**(31-bits))-1e-10:raise ValueError('909 phase Horner range exceeded')
    phase=np.stack([quantize(pp[:,j,:],bits) for j,bits in enumerate((32,28,39))],axis=1)
    step=round(float(m['frequency'][0])/48000*2**64)
    arrays=dict(cf9_phase=phase,cf9_control=quantize(cp,29),cf9_onset_control=quantize(joint,29),
        cf9_body=quantize(basis.reshape(5,-1).T,30),cf9_onset=quantize(field909.decode(m,'onset').T,31),
        cf9_frames=m['time_frames'].astype('int64'),cf9_inverse=(2**31//np.diff(m['time_frames'].astype('int64'))),
        cf9_time=quantize(tp,28),cf9_step=np.array([step>>32,step&0xffffffff],dtype='int64'))
    return {k:v.ravel() for k,v in arrays.items()},dict(control_horner=max(prefix_bound(cp),inner,outer),body_horner=envelope,rounding_margin=1e-4)


def write_tables(folder):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True);arrays,bounds=export()
    assembly=['.section .rodata'];header=['#include <stdint.h>']
    for name,values in arrays.items():
        assembly+=['.balign 4','.globl '+name,name+':']
        assembly+=['.long '+','.join(str(int(v)) for v in values[i:i+8]) for i in range(0,len(values),8)]
        header+=['static const int32_t '+name+'[] = {'+','.join(str(int(v)) if int(v)<2**31 else str(int(v)-2**32) for v in values)+'};']
    (folder/'tables909.s').write_text('\n'.join(assembly)+'\n');(folder/'tables909.h').write_text('\n'.join(header)+'\n')
    return dict(model_sha256=field909.MODEL_SHA,table_bytes=sum(v.size*4 for v in arrays.values()),range_bounds=bounds)


class Reference:
    def __init__(self,folder=OUT):
        self.folder=Path(folder);self.receipt=write_tables(self.folder)
        coldfire_field808.write_tables(self.folder)
        source=cpu.ROOT/'tools/x0x/coldfire_field909_ref.c';library=self.folder/'reference909.dylib'
        cpu.command([os.environ.get('CC','clang'),'-O3','-std=c99','-shared','-fPIC','-Wall','-Wextra','-Werror','-I',self.folder,source,'-o',library])
        self.library=ctypes.CDLL(str(library));self.library.cf9_reference.argtypes=[ctypes.POINTER(ctypes.c_int32),ctypes.POINTER(ctypes.c_int32),ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32];self.library.cf9_reference.restype=None
        self.library.cf9_errors.restype=ctypes.c_uint32;self.state=(ctypes.c_int32*352)()
    def call(self,tune,attack,decay,start=False):
        output=(ctypes.c_int32*32)();self.library.cf9_reference(self.state,output,int(start),tune,decay,attack)
        if self.library.cf9_errors():raise ArithmeticError('909 integer intermediate exceeded range')
        return list(output)
    def render(self,tune,attack,decay,frames=96000):
        self.state=(ctypes.c_int32*352)()
        return np.asarray([x for b in range((frames+31)//32) for x in self.call(tune,attack,decay,b==0)][:frames],dtype='int64')


def build(folder=OUT):
    folder=Path(folder);receipt=write_tables(folder);coldfire_field808.write_tables(folder)
    probe=(cpu.ROOT/'tests/asm/coldfire_probe.s').read_text().replace('bsr x0x_field808','bsr x0x_field909')
    source=cpu.ROOT/'targets/coldfire/field909.s'
    text=probe+'\n'+coldfire_field808.SOURCE.read_text()+'\n'+source.read_text()+'\n'+(folder/'tables.s').read_text()+'\n'+(folder/'tables909.s').read_text()
    path=folder/'probe909.s';path.write_text(text);image,_=cpu.build_coldfire(folder,path)
    symbol=next(line.split() for line in cpu.command(['m68k-elf-nm','-S',folder/'diagnostic.elf']).splitlines() if line.split()[-1:]==['x0x_field909'])
    receipt.update(kernel_bytes=int(symbol[1],16),image_bytes=len(image),state_bytes=352*4,source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),image_sha256=hashlib.sha256(image).hexdigest())
    (folder/'build.json').write_text(json.dumps(receipt,indent=2)+'\n');return receipt,image


class Runner(coldfire_field808.Runner):
    STATES,OUTPUT,SNAPSHOT=0x40040004,0x40048004,0x40049004
    STACK,STOP=0x40050000,0x40060000
    def __init__(self,image,guarded=True):super().__init__(image,guarded=guarded,stack_bytes=232)
    def call(self,tune,attack,decay,start=False,slot=0):
        return super().call(tune,decay,start=start,slot=slot,model=attack)
