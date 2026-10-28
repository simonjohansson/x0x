"""Frozen 808 model in fixed point; host reference and hand-written ColdFire ASM."""
from pathlib import Path
import ctypes
import hashlib
import json
import math
import os
import struct
import sys

from . import cpu, sharc_field808 as shared

OUT=cpu.ROOT/'out/808-model/coldfire'
SOURCE=cpu.ROOT/'targets/coldfire/field808.s'
WORDS=352


def export():
    import numpy as np
    from scipy.interpolate import BSpline,PPoly
    t=shared.export_tables(shared.load_model())
    def quantize(value,bits):
        q=np.rint(np.asarray(value)*2**bits)
        if np.any(q<-(1<<31)) or np.any(q>(1<<31)):
            raise ValueError('Coefficient exceeds its fixed-point range')
        return np.clip(q,-(1<<31),(1<<31)-1).astype('int64')
    # Every Horner prefix must fit, not only the final control weight.
    for p in t['control'].reshape(-1,4):
        for k in range(1,5):
            poly=p[:k].astype(float);roots=np.roots(np.polyder(poly)) if k>2 else []
            xs=[0.,1.]+[float(x.real) for x in roots if abs(x.imag)<1e-9 and 0<x.real<1]
            if max(abs(np.polyval(poly,x)) for x in xs)>=4:
                raise ValueError('Control Horner prefix exceeds Q29')
    arrays=dict(cf_control=quantize(t['control'].ravel(),29),cf_tone=quantize(t['tone'].ravel(),31),
        cf_low=quantize(t['low_poly'].ravel(),31),cf_low_break=t['low'].astype('int64'),
        cf_coordinate=np.floor(np.arange(128)*255/127+.5).astype('int64'),
        cf_sine=quantize(np.sin(np.arange(2049)*2*np.pi/2048),31))
    arrays['cf_body']=quantize(np.concatenate([g['coefficients'].reshape(8,-1) for g in t['groups']],axis=1).T.ravel(),28)
    groups=[];offset=0
    # Knot insertion gives convex Bezier weights. Convert their cached values to
    # power coefficients in integers, avoiding low-precision large basis terms.
    transform=np.array([[0,0,0,1],[0,0,1/3,1],[0,1/3,2/3,1],[1,1,1,1]])
    for g,source in enumerate(t['groups']):
        breaks=np.rint(source['breaks']).astype(int);count=len(breaks)+2
        knots=np.r_[np.repeat(breaks[0],4),breaks[1:-1],np.repeat(breaks[-1],4)]
        segments=[]
        for j,(a,b) in enumerate(zip(breaks[:-1],breaks[1:])):
            power=[]
            for k in range(4):
                unit=np.zeros(count);unit[j+k]=1
                c=PPoly.from_spline((knots,unit,3)).c[:,j+3]*(b-a)**np.arange(3,-1,-1)
                power.append(c)
            matrix=transform@np.array(power).T
            if matrix.min()<-1e-10 or abs(matrix.sum(axis=1)-1).max()>1e-10:
                raise ValueError('Bezier basis is not convex')
            segments.extend([int(a),int(b),(1<<31)//int(b-a),*quantize(np.clip(matrix,0,1).ravel(),31)])
        arrays[f'cf_segments{g}']=np.asarray(segments,dtype='int64')
        channels=source['coefficients'].shape[1]
        groups.append((len(breaks)-1,g,208+4*offset,4*count,channels,60+4*g,80+16*source['channel']))
        offset+=channels*count
    if offset!=300:raise ValueError('Unexpected frozen coefficient count')
    phase=round(t['frequency']/48000*2**64)
    constants=[phase>>32,phase&0xffffffff,*quantize([t['canonical_pole'],1/(2*(1-t['canonical_pole']))],31)]
    arrays['cf_constants']=np.asarray(constants,dtype='int64')
    return arrays,groups



def range_bounds(arrays,groups):
    """Tensor Bezier hulls cover continuous Decay and time, including fractions."""
    import numpy as np
    transform=np.array([[0,0,0,1],[0,0,1/3,1],[0,1/3,2/3,1],[1,1,1,1.]])
    weights=np.einsum('ij,srj->sir',transform,arrays['cf_control'].reshape(16,8,4)/2**29)
    body=arrays['cf_body'].reshape(300,8).T/2**28
    coefficient=prefix=0.
    for count,g,offset,stride,channels,_,_ in groups:
        at=(offset-208)//4;length=stride//4
        combined=np.einsum('sar,rcn->sacn',weights,body[:,at:at+channels*length].reshape(8,channels,length))
        coefficient=max(coefficient,float(np.abs(combined).max()))
        matrices=arrays[f'cf_segments{g}'].reshape(count,19)[:,3:].reshape(count,4,4)/2**31
        for j,matrix in enumerate(matrices):
            b=np.einsum('ij,sacj->saci',matrix,combined[:,:,:,j:j+4])
            p=np.stack([b[...,3]-3*b[...,2]+3*b[...,1]-b[...,0],
                        3*(b[...,2]-2*b[...,1]+b[...,0]),3*(b[...,1]-b[...,0]),b[...,0]],axis=-1)
            for k in range(1,5):
                degree=k-1;ascending=p[...,:k][...,::-1]
                hull=np.stack([sum(ascending[...,q]*math.comb(i,q)/math.comb(degree,q)
                                   for q in range(i+1)) for i in range(k)],axis=-1)
                prefix=max(prefix,float(np.abs(hull).max()))
    # Margin covers weight/dot/Horner rounding; this is an internal range proof,
    # not an all-control waveform or perceptual acceptance claim.
    if max(coefficient,prefix)>=32-1e-4:raise ValueError('Continuous envelope range exceeds Q26 headroom')
    return dict(combined_coefficient=coefficient,horner_prefix=prefix,q26_limit=32,rounding_margin=1e-4)


def write_tables(folder):
    arrays,groups=export();bounds=range_bounds(arrays,groups);assembly=['.section .rodata'];header=['#include <stdint.h>']
    for name,values in arrays.items():
        assembly+=['.balign 4','.globl '+name,name+':']
        assembly+=['.long '+','.join(str(int(v)) for v in values[i:i+8]) for i in range(0,len(values),8)]
        header+=['static const int32_t '+name+'[] = {'+','.join(str(int(v)) if int(v)<2**31 else str(int(v)-2**32) for v in values)+'};']
    assembly+=['.globl cf_groups','cf_groups:']
    for row in groups:
        n,g,offset,stride,channels,index,cache=row
        assembly+=['.long '+','.join(map(str,(n,f'cf_segments{g}',offset,stride,channels,index,cache)))]
    header+=['struct cf_group {int count; const int32_t *segments; int coefficient,stride,channels,index,cache;};',
             'static const struct cf_group cf_groups[] = {']
    header+=['{'+','.join(map(str,(n,f'cf_segments{g}',offset,stride,ch,idx,cache)))+'},' for n,g,offset,stride,ch,idx,cache in groups]
    header+=['};']
    folder.mkdir(parents=True,exist_ok=True)
    (folder/'tables.s').write_text('\n'.join(assembly)+'\n')
    (folder/'tables.h').write_text('\n'.join(header)+'\n')
    return dict(table_bytes=sum(len(a)*4 for a in arrays.values())+28*len(groups),state_bytes=WORDS*4,range_bounds=bounds,
                model_sha256=shared.MODEL_SHA,tables_sha256=hashlib.sha256((folder/'tables.s').read_bytes()).hexdigest())


class Reference:
    def __init__(self,folder=OUT):
        self.folder=Path(folder);self.receipt=write_tables(self.folder)
        source=cpu.ROOT/'tools/x0x/coldfire_field808_ref.c';library=self.folder/'reference.dylib'
        cpu.command([os.environ.get('CC','clang'),'-O3','-std=c99','-shared','-fPIC','-Wall','-Wextra','-Werror',
                     '-I',self.folder,source,'-o',library])
        self.library=ctypes.CDLL(str(library))
        self.library.cf_reference.argtypes=[ctypes.POINTER(ctypes.c_int32),ctypes.POINTER(ctypes.c_int32),ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32]
        self.library.cf_reference.restype=None
        self.library.cf_errors.restype=ctypes.c_uint32
        self.state=(ctypes.c_int32*WORDS)()
    def call(self,tone,decay,start=False,model=0):
        out=(ctypes.c_int32*32)();self.library.cf_reference(self.state,out,int(start),tone,decay,model)
        if self.library.cf_errors():raise ArithmeticError('Fixed-point intermediate exceeded its range')
        return list(out)
    def render(self,tone,decay,frames=264000):
        import numpy as np
        self.state=(ctypes.c_int32*WORDS)()
        return np.asarray([x for block in range((frames+31)//32) for x in self.call(tone,decay,block==0)][:frames],dtype='int64')


def build(folder=OUT):
    folder=Path(folder);receipt=write_tables(folder)
    seed=(cpu.ROOT/'targets/coldfire/selector.s').read_text().split('    .globl x0x_selector\n')[0]
    begin=seed.index('    lea -12(%sp), %sp');end=seed.index('    move.l %d0, 32(%a0)')
    call=['    lea -24(%sp),%sp']
    for k in range(6):call += [f'    move.l {28+4*k}(%sp),%d0',f'    move.l %d0,{4*k}(%sp)']
    call+=['    bsr x0x_field808','    lea 24(%sp),%sp','    movea.l 28(%sp),%a0']
    probe=folder/'probe.s';probe.write_text(seed[:begin]+'\n'.join(call)+'\n'+seed[end:]+'\n'+SOURCE.read_text()+'\n'+(folder/'tables.s').read_text())
    image,_=cpu.build_coldfire(folder,probe)
    symbol=next(line.split() for line in cpu.command(['m68k-elf-nm','-S',folder/'diagnostic.elf']).splitlines() if line.split()[-1:] == ['x0x_field808'])
    receipt.update(kernel_bytes=int(symbol[1],16),diagnostic_wrapper_bytes=int(symbol[0],16)-0x40000400,image_sha256=hashlib.sha256(image).hexdigest(),source_sha256=hashlib.sha256(SOURCE.read_bytes()).hexdigest(),image_bytes=len(image))
    (folder/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt,image


class Runner:
    BASE,OUTPUT,STATES=0x40000400,0x40010004,0x40011004
    SNAPSHOT,STACK,STOP=0x40018004,0x40020000,0x40030000
    def __init__(self,image,guarded=True):
        harness=cpu.require_module('emu.harness','digiemu')
        from unicorn import UC_HOOK_CODE,UC_HOOK_MEM_WRITE,m68k_const
        self.machine=harness.Machine();self.machine.ensure(0x40000000)
        self.uc=self.machine.uc;self.regs=m68k_const;self.extent=8*WORDS*4+8
        self.uc.mem_write(self.BASE,image);self.image=image
        self.uc.mem_write(self.STATES-4,b'\xa5'*self.extent)
        for voice in range(8):self.uc.mem_write(self.STATES+voice*WORDS*4,bytes(WORDS*4))
        self.steps=0;self.invalid=[];self.allowed=[];self.maximum_instructions=0
        if guarded:
            self.uc.hook_add(UC_HOOK_CODE,self._step)
            self.uc.hook_add(UC_HOOK_MEM_WRITE,self._write)
    def _step(self,*_):self.steps+=1
    def _write(self,_uc,_access,address,size,_value,_data):
        if not any(a<=address and address+size<=b for a,b in self.allowed):self.invalid.append((address,size))
    def check_tables(self):
        assert bytes(self.uc.mem_read(self.BASE,len(self.image)))==self.image,'Code/table changed'
    def call(self,tone,decay,start=False,slot=0,model=0):
        from .coldfire_arithmetic import EMAC_SEED
        assert 0<=slot<8
        b=self;u=self.uc;r=lambda n:getattr(self.regs,'UC_M68K_REG_'+n)
        state=self.STATES+slot*WORDS*4
        before=bytes(u.mem_read(self.STATES-4,b.extent))
        u.mem_write(self.OUTPUT-4,b'\xa5'*136);u.mem_write(self.SNAPSHOT-4,b'\xa5'*44)
        u.mem_write(self.STACK-184,b'\xa5'*248)
        args=struct.pack('>8I',self.STOP,state,self.OUTPUT,int(start),tone,decay,model,self.SNAPSHOT)
        u.mem_write(self.STACK,args);u.reg_write(r('SR'),0x2700)
        saved={r(n):0x10203040+i for i,n in enumerate([*(f'D{i}' for i in range(2,8)),*(f'A{i}' for i in range(2,7))])}
        for reg,v in saved.items():u.reg_write(reg,v)
        u.reg_write(r('A7'),self.STACK);b.steps=0;b.invalid=[]
        b.allowed=[(state,state+WORDS*4),(self.OUTPUT,self.OUTPUT+128),(self.SNAPSHOT,self.SNAPSHOT+36),(self.STACK-168,self.STACK)]
        u.emu_start(self.BASE,self.STOP,timeout=10000000)
        assert u.reg_read(r('PC'))==self.STOP and not b.invalid,(hex(u.reg_read(r('PC'))),b.invalid[:4])
        assert u.reg_read(r('A7'))==self.STACK+4
        assert all(u.reg_read(k)==v for k,v in saved.items()),'Callee register changed'
        assert bytes(u.mem_read(self.STACK,len(args)))==args
        assert bytes(u.mem_read(self.STACK-184,16))==b'\xa5'*16
        assert bytes(u.mem_read(self.STACK+len(args),8))==b'\xa5'*8
        snapshot=bytes(u.mem_read(self.SNAPSHOT-4,44));assert snapshot[:4]==snapshot[-4:]==b'\xa5'*4
        assert struct.unpack('>8I',snapshot[4:36])==EMAC_SEED,'EMAC context changed'
        after=bytes(u.mem_read(self.STATES-4,b.extent));at=state-self.STATES+4
        assert before[:at]==after[:at] and before[at+WORDS*4:]==after[at+WORDS*4:],'Other slot/guard changed'
        out=bytes(u.mem_read(self.OUTPUT-4,136));assert out[:4]==out[-4:]==b'\xa5'*4
        self.maximum_instructions=max(self.maximum_instructions,self.steps)
        return list(struct.unpack('>32i',out[4:-4]))


def qualify(folder=OUT):
    import numpy as np
    import soundfile as sf
    import time
    from . import fit808,field808,diagnose808
    folder=Path(folder);receipt,image=build(folder)
    (folder/'engine-source.s').write_bytes(SOURCE.read_bytes())
    (folder/'qualification-driver.py').write_bytes(Path(__file__).read_bytes())
    model=shared.load_model();reference=Reference(folder)
    config,events=fit808.protocol();hashes=fit808.verify_artifacts(fit808.CORPUS,config,events)
    chosen=field808.listening_subset(list({(e['tone_cc'],e['decay_cc']):e for e in reversed(events)}.values()))
    extra=[(128,0),(255,32512),(63*256+128,63*256+128),(1,1),(32511,32511),(17*256+128,68*256+128)]
    cohort=[(e['tone_cc']*256,e['decay_cc']*256,e) for e in chosen]+[(t,d,None) for t,d in extra]
    rows=[];references={};predictions={};runner=Runner(image,guarded=False);maximum_count=0
    with sf.SoundFile(fit808.CORPUS/'808-corpus.wav') as wav:
        for tone,decay,event in cohort:
            began=time.monotonic()
            integers=np.asarray([v for i in range(8250) for v in runner.call(tone,decay,i==0)],dtype='int64')
            integer_reference=reference.render(tone,decay)
            if not np.array_equal(integers,integer_reference):raise AssertionError(('Integer output disagreement',tone,decay))
            if bytes(runner.uc.mem_read(runner.STATES,WORDS*4))!=struct.pack('>352i',*reference.state):
                raise AssertionError('End-state integer disagreement')
            output=integers/2**31;expected=4*field808.render(model,tone,decay)
            error=output-expected;maximum=float(abs(error).max());relative=float(np.linalg.norm(error)/np.linalg.norm(expected))
            if output[0]!=0 or maximum>1e-5 or relative>.001:raise AssertionError(('Numerical port gate',tone,decay,maximum,relative))
            if any(runner.call(tone,decay)):raise AssertionError('Terminal output is not silent')
            counted=Runner(image)
            for frame in range(50):counted.call(tone,decay,frame==0)
            counted.check_tables();maximum_count=max(maximum_count,counted.maximum_instructions)
            row=dict(tone_raw=tone,decay_raw=decay,port_max_dsp_fs=maximum,port_relative_l2=relative,
                     integer_output_and_end_state_exact=True,peak_dsp_fs=float(abs(output).max()),
                     maximum_counted_first_50_blocks_including_wrapper=counted.maximum_instructions,
                     render_wall_seconds=time.monotonic()-began)
            if event is not None:
                pair=(event['tone_cc'],event['decay_cc']);source=fit808.read_slot(wav,event)
                references[pair]=source;predictions[pair]=output/4
                row.update(index=event['index'],partition=event['partition'],tone_cc=pair[0],decay_cc=pair[1],source=fit808.measure(output/4,source,config))
            sf.write(folder/f't{tone}-d{decay}-asm.wav',output/4,48000,subtype='FLOAT')
            rows.append(row);(folder/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
            print(json.dumps(row),flush=True)
    runner.check_tables()
    import unicorn
    native_library=Path(unicorn.__file__).parent/'lib'/('libunicorn.2.dylib' if sys.platform=='darwin' else 'libunicorn.so.2')
    report=dict(native_library_sha256=hashlib.sha256(native_library.read_bytes()).hexdigest(),unicorn_version=unicorn.__version__,
        status='passed',scope='Isolated assembled ColdFire 808; recorded-source development cohort; no OS/device boot',
        build=receipt,records=rows,source_sha256=hashes['808-corpus.wav'],model_sha256=shared.MODEL_SHA,
        source_asm_sha256=receipt['source_sha256'],image_sha256=receipt['image_sha256'],tables_sha256=receipt['tables_sha256'],
        driver_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        integer_reference_sha256=hashlib.sha256((cpu.ROOT/'tools/x0x/coldfire_field808_ref.c').read_bytes()).hexdigest(),
        protocol_sha256=fit808.digest(fit808.FIXTURES/'protocol.json'),
        emulator_revision=cpu.revision(cpu.ROOT/'vendor/digiemu'),project_revision=cpu.revision(cpu.ROOT),
        maximum_port_dsp_fs=max(r['port_max_dsp_fs'] for r in rows),maximum_counted_instructions_including_wrapper=maximum_count,
        timing_note='Counts sample the first 50 blocks, covering onset/blend/body. They include the EMAC seed/snapshot test wrapper, are not complete-hit worst-case cycles and do not establish physical timing.',
        unqualified=['physical ColdFire timing','full-OS wiring is reported separately','MODEL=909 silent in this development kernel','fresh independent source acceptance'])
    manifest={k:v for k,v in report.items() if k.endswith('_sha256')};manifest.update(scope=report['scope'],
        cohort_note='Same development cohort as SHARC; actual assembled ColdFire prediction audio, no new fitting or per-recording gain/alignment.')
    report['listening_gain']=diagnose808.listening_report(folder,chosen,references,predictions,manifest)
    shared.make_plots(folder,references,predictions,rows,backend='ColdFire')
    page=folder/'index.html'
    page.write_text(page.read_text().replace('Native integration and physical deadlines remain untested.',
        'This report covers isolated instruction rendering. OS integration has a separate emulator smoke; physical timing is untested.'))
    if SOURCE.read_bytes()!=(folder/'engine-source.s').read_bytes():raise ValueError('ASM source changed during qualification')
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('command',choices=('qualify',))
    p.parse_args();qualify()
