"""Frozen 808 field exported to hand-written SHARC assembly; isolated-hit candidate."""
from pathlib import Path
import hashlib
import json
import struct

from . import cpu, field808, field909, fit808, tone_factor808

MODEL = cpu.ROOT / 'models/808.npz'
MODEL_SHA = 'fb4519537afc1142f3c108bc9e94fe40b752f2b967a97ab6e185e5e47a04d112'
OUT = cpu.ROOT / 'out/808-model/sharc'
SOURCE = cpu.ROOT / 'targets/sharc/field808.s'
STATE_BYTES = 512
CODE_BYTES = 6144


def polynomial(values):
    """Values at u=0,1/3,2/3,1 to descending normalized cubic coefficients."""
    import numpy as np
    return np.linalg.solve(np.vander(np.arange(4) / 3), np.asarray(values))


def export_tables(model):
    import numpy as np
    from scipy.interpolate import BSpline, PPoly
    basis = field808.body_basis(model)
    raw = np.concatenate([np.arange(a, b + 1, step) for a, b, step in model['raw_segments']]) / fit808.RATE
    groups, offset, channel = [], 0, 0
    breaks_list = [raw] + [model['envelope_knots'][a:b].astype(float) for a, b in
                           zip(model['envelope_offsets'][:-1], model['envelope_offsets'][1:])]
    for group, breaks in enumerate(breaks_list):
        channels = 1 if group in (0, 4) else 2
        count = len(breaks) + 2
        coefficients = basis[:, offset:offset + channels * count - (group == 0)]
        if group == 0:
            coefficients = np.column_stack([np.zeros(8), coefficients])
        coefficients = coefficients.reshape(8, channels, count)
        knots = np.r_[np.repeat(breaks[0], 4), breaks[1:-1], np.repeat(breaks[-1], 4)]
        widths = np.diff(breaks)
        local = np.zeros((len(widths), 4, 3))
        for segment in range(len(widths)):
            for j in range(3):
                unit = np.zeros(count); unit[segment + j] = 1
                p = PPoly.from_spline((knots, unit, 3))
                local[segment, :, j] = p.c[:, segment + 3] * widths[segment] ** np.arange(3, -1, -1)
        groups.append(dict(breaks=breaks * fit808.RATE,
                           basis=local.astype('float32'), channel=channel,
                           coefficients=coefficients.astype('float32')))
        offset += channels * count - (group == 0)
        channel += channels
    control = field808.decode_rows(model, 'control')
    breaks = np.linspace(0, 1, 17)
    knots = np.r_[np.zeros(4), breaks[1:-1], np.ones(4)]
    cp = np.stack([PPoly.from_spline((knots, row, 3)).c[:, 3:19].T * (1 / 16) ** np.arange(3, -1, -1)
                   for row in control], axis=1).astype('float32')
    # Native-coordinate mapping is affine within each CC interval.
    tone = np.array([polynomial(tone_factor808.poles(model['tone'],
                   [fit808.native_coordinate((cc + u) * 256) for u in np.arange(4) / 3]))
                   for cc in range(127)] + [[0, 0, 0, tone_factor808.poles(model['tone'], 1.)]], dtype='float32')
    # The power law near zero needs shorter intervals than one CC.
    low = np.r_[0, 1, 2, 4, 8, 16, 32, 64, 128, 256]
    low_poly = np.array([polynomial(tone_factor808.poles(model['tone'],
                   [fit808.native_coordinate(a + (b - a) * u) for u in np.arange(4) / 3]))
                   for a, b in zip(low[:-1], low[1:])], dtype='float32')
    return dict(groups=groups, control=cp, tone=tone, low=low, low_poly=low_poly,
                coordinate=np.floor(np.arange(128) * 255 / 127 + .5).astype('float32') / 255,
                canonical_pole=float(tone_factor808.poles(model['tone'], 1.)), frequency=float(model['carrier_hz'][0]))


def weights(tables, raw):
    import numpy as np
    cc, fraction = divmod(raw, 256)
    x = tables['coordinate'][cc] + fraction / 256 * (tables['coordinate'][min(cc + 1, 127)] - tables['coordinate'][cc])
    segment = min(int(x * 16), 15)
    u = x * 16 - segment
    return np.array([np.polyval(p, u) for p in tables['control'][segment]])


def pole(tables, raw):
    import numpy as np
    if raw < 256:
        index = min(np.searchsorted(tables['low'], raw, side='right') - 1, len(tables['low']) - 2)
        a, b = tables['low'][index:index + 2]
        return float(np.polyval(tables['low_poly'][index], (raw - a) / (b - a)))
    cc, fraction = divmod(raw, 256)
    return float(np.polyval(tables['tone'][cc], fraction / 256))


def render_tables(tables, tone, decay, frames=fit808.FRAMES):
    import numpy as np
    from scipy.signal import lfilter
    age = np.arange(frames)
    w = weights(tables, decay)
    channels = []
    for group in tables['groups']:
        index = np.clip(np.searchsorted(group['breaks'], age, side='right') - 1, 0, len(group['breaks']) - 2)
        u = (age - group['breaks'][index]) / np.diff(group['breaks'])[index]
        coefficient = np.einsum('rcn,r->cn', group['coefficients'], w)
        local = np.stack([coefficient[:,index+j].T for j in range(4)],axis=2)
        p = np.einsum('ndj,ncj->ncd',group['basis'][index],local[:,:,:3]-local[:,:,3:])
        p[:,:,3] += local[:,:,3]
        values = ((p[:, :, 0] * u[:, None] + p[:, :, 1]) * u[:, None] + p[:, :, 2]) * u[:, None] + p[:, :, 3]
        channels.extend(values.T)
    fade = np.clip((age - 960) / 480, 0, 1); fade = fade * fade * (3 - 2 * fade)
    phase = age * (2 * np.pi * tables['frequency'] / fit808.RATE)
    body = sum(channels[2*h-1] * np.sin(h*phase) + channels[2*h] * np.cos(h*phase) for h in (1,2,3)) + channels[7]
    x = np.where(age < 1440, (1-fade)*channels[0], 0) + np.where(age >= 960, fade*body, 0)
    p = pole(tables, tone); gain = (1-p)/(1-tables['canonical_pole'])
    return lfilter([gain, -gain*tables['canonical_pole']], [1.,-p], x)


def load_model():
    import numpy as np
    if fit808.digest(MODEL) != MODEL_SHA:
        raise ValueError('Frozen listening model hash mismatch')
    with np.load(MODEL, allow_pickle=False) as archive:
        return {k: archive[k] for k in archive.files}


def write_data(tables, folder):
    import math
    import numpy as np
    from .sharc_layout import voice_layout
    lines, count = ['.SECTION/DOUBLE32 seg_dmda;'], 0
    addresses = {}
    base = voice_layout(CODE_BYTES)['data_address']
    def add(name, values):
        nonlocal count
        addresses[name] = base + count
        lines.extend(['.GLOBAL ' + name + '.;', '.VAR ' + name + '. = ' + str(values[0]) + ';'])
        lines.extend('.VAR = ' + str(v) + ';' for v in values[1:])
        count += len(values) * 4
    def bits(x):
        return '0x%08x' % struct.unpack('<I', struct.pack('<f', float(x)))[0]
    def floats(name, values):
        add(name, [bits(x) for x in np.asarray(values).ravel()])
    body = np.concatenate([g['coefficients'].reshape(8, -1) for g in tables['groups']], axis=1)
    floats('field_body', body.T)
    headers = []
    offset = 0
    for h, group in enumerate(tables['groups']):
        floats(f'field_basis{h}', group['basis'])
        descriptor = []
        for j, (a, b) in enumerate(zip(group['breaks'][:-1], group['breaks'][1:])):
            descriptor.extend([bits(a), bits(b), bits(1/(b-a)), hex(addresses[f'field_basis{h}'] + j*48)])
        add(f'field_descriptor{h}', descriptor)
        channels = group['coefficients'].shape[1]
        size = group['coefficients'].shape[2]
        headers.extend([f'field_descriptor{h}.', hex(addresses['field_body'] + offset*32),
                        channels, 32+4*h, 52+16*group['channel'], size*32])
        offset += channels*size
    add('field_groups', headers)
    floats('field_control', tables['control'])
    floats('field_coordinate', tables['coordinate'])
    floats('field_tone', tables['tone'])
    add('field_low', tables['low'].tolist())
    floats('field_low_poly', tables['low_poly'])
    constants = dict(zero=0, one=1, two=2, three=3, four=4, half=.5, quarter=.25,
        negative_quarter=-.25, negative_half=-.5, cycle_scale=2**-32, twopi=2*math.pi,
        sin_c1=-1/6, sin_c2=1/120, sin_c3=-1/5040, sin_c4=1/362880, sin_c5=-1/39916800,
        step_sin=math.sin(2*math.pi*tables['frequency']/48000),
        step_cos=math.cos(2*math.pi*tables['frequency']/48000), fade_inverse=1/480,
        fraction=1/256, sixteen=16, inverse_canonical=1/(1-tables['canonical_pole']), canonical=tables['canonical_pole'])
    for name, value in constants.items():
        floats('k_'+name, [value])
    step = round(tables['frequency']*32/48000*2**64)
    add('phase_step_hi', [step >> 32]); add('phase_step_lo', [step & 0xffffffff])
    from .sharc_field909 import write_tables
    write_tables(add, floats)
    add('sharc_voice_state_bytes', [STATE_BYTES])
    data_bytes = count + 4
    state_base = voice_layout(CODE_BYTES)['data_address'] + (data_bytes + 7)//8*8
    add('field_state_base', [hex(state_base)])
    (folder/'tables.s').write_text('\n'.join(lines)+'\n')
    return data_bytes, state_base



def read_executable(raw, layout):
    if (len(raw) < 52 or raw[:7] != b'\x7fELF\x01\x01\x01' or
            struct.unpack_from('<HH',raw,16) != (2,0x85)):
        raise ValueError('Expected linked SHARC ELF32')
    shoff = struct.unpack_from('<I',raw,32)[0]
    shsize, count = struct.unpack_from('<HH',raw,46)
    entry = struct.unpack_from('<I',raw,24)[0]
    if shsize != 40 or shoff+count*40 > len(raw) or entry != layout['code_pc16']:
        raise ValueError('Invalid SHARC executable extent or entry')
    allocated = {}
    for i in range(count):
        _, kind, flags, address, offset, size, *_ = struct.unpack_from('<10I',raw,shoff+40*i)
        if kind in (4,9):
            raise ValueError('Unresolved SHARC relocation')
        if flags & 2:
            if kind != 1 or flags not in (3,7) or offset+size > len(raw) or flags in allocated:
                raise ValueError('Unexpected allocated section')
            allocated[flags] = (address,raw[offset:offset+size])
    if (set(allocated) != {3,7} or allocated[7][0] != entry or
            allocated[3][0] != layout['data_address']):
        raise ValueError('SHARC sections do not match the private partition')
    code = allocated[7][1]
    if len(code)%2:
        raise ValueError('SHARC code is not whole parcels')
    return b''.join(code[i:i+2][::-1] for i in range(0,len(code),2)), allocated[3][1], entry

def build(folder=OUT):
    import os
    from .sharc_layout import voice_layout, voice_artifact
    folder = Path(folder); folder.mkdir(parents=True, exist_ok=True)
    if folder.resolve().is_relative_to(fit808.CORPUS.resolve()):
        raise ValueError('Build outside the immutable reference corpus')
    model = load_model(); tables = export_tables(model)
    data_bytes, state_base = write_data(tables, folder)
    layout = voice_layout(CODE_BYTES)
    selache = Path(os.environ.get('SELACHE', cpu.ROOT/'vendor/digikit/out/tools/selache')).resolve()
    if cpu.revision(selache) != cpu.SELACHE_PIN:
        raise ValueError('Selache revision mismatch')
    programs = selache/'target/release'
    for source, name in ((SOURCE,'engine'), (cpu.ROOT/'targets/sharc/field909.s','909'),
                         (cpu.ROOT/'targets/sharc/choke.s','choke'), (folder/'tables.s','tables')):
        cpu.command([programs/'selas','-proc','ADSP-21569','-o',folder/(name+'.doj'), source])
    ldf = f'''ARCHITECTURE(ADSP-21569)
$OBJECTS = $COMMAND_LINE_OBJECTS;
MEMORY {{
 code {{ TYPE(BW RAM) START(0x{layout['code_pc16']*2:x}) END(0x{layout['code_pc16']*2+CODE_BYTES-1:x}) WIDTH(8) }}
 data {{ TYPE(BW RAM) START(0x{layout['data_address']:x}) END(0x{layout['data_address']+layout['data_bytes']-1:x}) WIDTH(8) }}
}}
PROCESSOR p0 {{ OUTPUT($COMMAND_LINE_OUTPUT_FILE) SECTIONS {{
 machine_code SW {{ INPUT_SECTION_ALIGN(2) INPUT_SECTIONS($OBJECTS(seg_swco)) }} > code
 machine_data BW {{ INPUT_SECTION_ALIGN(4) INPUT_SECTIONS($OBJECTS(seg_dmda)) }} > data
}} }}
'''
    (folder/'layout.ldf').write_text(ldf)
    executable = folder/'field808.dxe'
    cpu.command([programs/'seld','-proc','ADSP-21569','-T',folder/'layout.ldf',
                 '-entry','sharc_voice_render.','-Map',folder/'field808.map','-o',executable,
                 folder/'engine.doj',folder/'909.doj',folder/'choke.doj',folder/'tables.doj'])
    raw = executable.read_bytes()
    code, data, entry = read_executable(raw, layout)
    assert len(data) == data_bytes, (len(data), data_bytes)
    doc = voice_artifact(code,data,0,20,0,code_bytes=CODE_BYTES,voice_bytes=STATE_BYTES)
    assert 0x20090000+doc['voice_state']['offset_bytes']==state_base
    (folder/'voice.sharc.json').write_text(json.dumps(doc,indent=2)+'\n')
    receipt = dict(model_sha256=MODEL_SHA, model909_sha256=field909.MODEL_SHA, source_sha256=fit808.digest(SOURCE),
        field909_sha256=fit808.digest(cpu.ROOT/'targets/sharc/field909.s'),
        choke_sha256=fit808.digest(cpu.ROOT/'targets/sharc/choke.s'),
        data_bytes=len(data), code_bytes=len(code), state_bytes=STATE_BYTES,
        state_base=state_base, layout=layout, initialized_plus_states=(len(data)+7)//8*8+16*STATE_BYTES,
        entry=struct.unpack_from('<I',raw,24)[0], artifact_sha256=fit808.digest(folder/'voice.sharc.json'))
    (folder/'build.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt, doc


class Runner:
    """Firmware-free execution of the assembled parcels on the pinned native core."""
    INPUT, OUTPUT, PARAM = 0x200b0000, 0x200b1004, 0x200b2000
    FRAME, STOP = 0x2deffc, 0xbc7ff0

    def __init__(self, receipt, artifact, state_bytes=STATE_BYTES):
        cpu.require_module('tools.sharc_dev.sharc_run', 'digikit')
        from tools.sharc_dev import sharcldr, sharc_run, sharc_transpile_run as native
        self.native, self.receipt = native, receipt
        self.state_bytes = state_bytes
        payload, blocks = b'', []
        self.immutable = []
        for segment in artifact['segments'][1:]:
            data = bytes.fromhex(segment['hex'])
            address = (sharcldr.sw_to_byte(0xb80000 + (0x90000+segment['offset_bytes'])//2)
                       if segment['kind'] == 'code' else 0x20090000+segment['offset_bytes'])
            blocks.append(dict(target_address=address,byte_count=len(data),fill=False,
                               payload_offset=len(payload),payload_len=len(data)))
            payload += data
            if segment['kind'] == 'data':
                self.immutable.append((address,data))
        for address,size in [(receipt['state_base'],16*state_bytes),(0,4),(0x200000,4),
                             (self.FRAME-128,132)]:
            blocks.append(dict(target_address=address,byte_count=size,fill=False,
                               payload_offset=len(payload),payload_len=size))
            payload += bytes(size)
        self.memory = sharcldr.LoadedMemory(payload,blocks)
        self.seed = sharc_run.Runner(self.memory,receipt['entry'],regs=dict(
            R4=self.INPUT,I6=self.FRAME,I7=self.FRAME-8,MODE1=0x10000),
            pokes={self.FRAME:0x12345678,self.FRAME-4:self.STOP-1})
        self.seed.state.stack_model=True
        self.core = native.NativeCore(native.pack_image(self.memory))
        native.to_native(self.core,self.seed.state)
        self.core.set_option(native.OPT_RUNTIME_DECODE,1)
        self.core.set_option(native.OPT_STOP_PC,self.STOP)
        self.maximum_instructions=0

    def call(self, tone, decay, start=False, slot=0, model=0, attack=16384, track=None):
        from tools.sharc_dev import sharc_trace as trace
        state = self.receipt['state_base']+slot*self.state_bytes
        words = [self.OUTPUT,slot,60*256,int(start),self.PARAM,state]
        self.core.poke(self.INPUT,struct.pack('<6I',*words),4)
        params=[tone,decay,attack,0,0,model,*([0]*34)]
        if track is not None:
            params[39]=0xa500+track
        self.core.poke(self.PARAM,struct.pack('<40I',*params),4)
        self.core.poke(self.OUTPUT-4,b'\xa5'*136,4)
        for name,value in dict(R4=self.INPUT,I6=self.FRAME,I7=self.FRAME-8,M5=0,M6=1,M7=0xffffffff,M13=0,M14=1,M15=0xffffffff).items():
            self.core.set_reg(trace.UREG_CODES[name],trace.Const(value))
        self.core.fresh_call(self.receipt['entry'])
        count = self.core.run(100000)
        if self.core.pc() != self.STOP:
            raise AssertionError((self.core.halt_reason,hex(self.core.pc()),count))
        self.maximum_instructions=max(self.maximum_instructions,count)
        values=[self.core.peek(self.OUTPUT+4*i) for i in range(-1,33)]
        if values[0] != 0xa5a5a5a5 or values[-1] != 0xa5a5a5a5 or any(v is None for v in values):
            raise AssertionError('ASM left unknown output or changed a guard')
        return struct.unpack('<32f',struct.pack('<32I',*values[1:-1])),count

    def check_tables(self):
        for address,data in self.immutable:
            for offset in range(0,len(data),4):
                if self.core.peek(address+offset) != struct.unpack_from('<I',data,offset)[0]:
                    raise AssertionError('ASM changed an immutable coefficient table')



def python_witness(receipt,artifact):
    """Cross-check native execution and every write on two independent Python traces."""
    from tools.sharc_dev import sharc_run,sharc_trace as trace
    from tools.sharc_dev.sharc_core.memory import _canonical_dm_address
    rows=[]
    for frame in (0,960):
        native=Runner(receipt,artifact)
        pokes={native.FRAME:0x12345678,native.FRAME-4:native.STOP-1}
        if frame:
            native.call(0,32512,True)
            base=receipt['state_base']
            step=round(float(load_model()['carrier_hz'][0])*32/48000*2**64)
            phase=(frame//32)*step
            native.core.poke(base+232,struct.pack('<III',frame,phase>>32,phase&0xffffffff),4)
            pokes.update({base+i:native.core.peek(base+i) for i in range(0,STATE_BYTES,4)})
        words=[native.OUTPUT,0,60*256,int(frame==0),native.PARAM,receipt['state_base']]
        params=[0,32512,16384,0,0,0]+[0]*34
        pokes.update({native.INPUT+i*4:v for i,v in enumerate(words)})
        pokes.update({native.PARAM+i*4:v for i,v in enumerate(params)})
        pokes.update({native.OUTPUT+4*i:0xa5a5a5a5 for i in range(-1,33)})
        regs=dict(R4=native.INPUT,I6=native.FRAME,I7=native.FRAME-8,MODE1=0x10000)
        runner=sharc_run.Runner(native.memory,receipt['entry'],regs=regs,pokes=pokes,
            breakpoints=[native.STOP],diagnose_unknown=True,
            watchpoints=[sharc_run.Watchpoint(0,0x100000000,on_read=False,stop=False)])
        runner.state.stack_model=True
        result=runner.run(max_steps=100000)
        if result.halt.reason!='breakpoint':
            raise AssertionError(result.halt.to_json())
        expected,_=native.call(0,32512,start=frame==0)
        read=lambda address:trace._dm_read(runner.state,trace.Const(address),4)
        got=[]
        for i in range(32):
            value=read(native.OUTPUT+4*i)
            if not isinstance(value,trace.Const):
                raise AssertionError('Unknown Python instruction result')
            got.append(struct.unpack('<f',struct.pack('<I',value.value))[0])
        if tuple(got)!=expected:
            raise AssertionError('Native/Python instruction outputs differ')
        for offset in range(0,STATE_BYTES,4):
            if read(receipt['state_base']+offset)!=trace.Const(native.core.peek(receipt['state_base']+offset)):
                raise AssertionError(('Native/Python state differs',offset))
        ranges=[(receipt['state_base'],STATE_BYTES),(native.OUTPUT,128)]
        allowed=[(_canonical_dm_address(runner.state,a,1,for_write=True),size) for a,size in ranges]
        for write in runner.watch_log:
            if not any(a<=write.address and write.address+write.width<=a+size for a,size in allowed):
                raise AssertionError(('ASM write escaped its voice/output',write))
        if read(native.FRAME)!=trace.Const(0x12345678) or read(native.FRAME-4)!=trace.Const(native.STOP-1):
            raise AssertionError('Callback changed its caller frame')
        rows.append(dict(frame=frame,instructions=result.instructions,write_count=len(runner.watch_log),
                         exact_native_python_output_and_state=True,kernel_software_stack_bytes=0))
    return rows

def qualify(folder=OUT):
    import numpy as np
    import soundfile as sf
    from . import listening808
    folder=Path(folder)
    driver_bytes=Path(__file__).read_bytes()
    receipt,artifact=build(folder)
    (folder/'qualification-driver.py').write_bytes(driver_bytes)
    (folder/'engine-source.s').write_bytes(SOURCE.read_bytes())
    model=load_model()
    config,events=fit808.protocol()
    hashes=fit808.verify_artifacts(fit808.CORPUS,config,events)
    chosen=field808.listening_subset(list({(e['tone_cc'],e['decay_cc']):e for e in reversed(events)}.values()))
    runner=Runner(receipt,artifact)
    references,predictions,rows={},{},[]
    extra=[(128,0),(255,32512),(63*256+128,63*256+128),(1,1),(32511,32511),(17*256+128,68*256+128)]
    cohort=[(e['tone_cc']*256,e['decay_cc']*256,e) for e in chosen]+[(t,d,None) for t,d in extra]
    with sf.SoundFile(fit808.CORPUS/'808-corpus.wav') as wav:
        for tone,decay,event in cohort:
            output=[];counts=[]
            for block in range(fit808.FRAMES//32):
                chunk,count=runner.call(tone,decay,block==0)
                output.extend(chunk);counts.append(count)
            output=np.asarray(output)
            expected=4*field808.render(model,tone,decay)
            error=output-expected
            maximum=float(abs(error).max())
            relative=float(np.linalg.norm(error)/np.linalg.norm(expected))
            if not np.isfinite(output).all() or output[0]!=0 or maximum>1e-5 or relative>.001:
                raise AssertionError(('ASM numerical gate',tone,decay,maximum,relative))
            row=dict(tone_raw=tone,decay_raw=decay,port_max_dsp_fs=maximum,port_relative_l2=relative,
                     maximum_block_instructions=max(counts),start_instructions=counts[0],
                     peak_dsp_fs=float(abs(output).max()))
            if event is not None:
                pair=(event['tone_cc'],event['decay_cc'])
                source=fit808.read_slot(wav,event)
                references[pair]=source;predictions[pair]=output/4
                row.update(index=event['index'],partition=event['partition'],tone_cc=pair[0],decay_cc=pair[1],
                           source=fit808.measure(output/4,source,config))
            rows.append(row)
            sf.write(folder/f't{tone}-d{decay}-asm.wav',output/4,48000,subtype='FLOAT')
            print(json.dumps(row),flush=True)
            (folder/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
    runner.check_tables()
    tables=export_tables(model)
    controls=np.array([weights(tables,r) for r in range(32513)])
    poles=np.array([pole(tables,r) for r in range(32513)])
    if not np.isfinite(controls).all() or not np.all((poles>0)&(poles<1)):
        raise AssertionError('Native control map sanity')
    report=dict(status='passed',scope='isolated assembled SHARC 808; recorded-source development cohort; no device boot',
        build=receipt,records=rows,source_sha256=hashes['808-corpus.wav'],model_sha256=MODEL_SHA,
        artifact_sha256=receipt['artifact_sha256'],protocol_sha256=fit808.digest(fit808.FIXTURES/'protocol.json'),
        driver_sha256=hashlib.sha256(driver_bytes).hexdigest(),source_asm_sha256=receipt['source_sha256'],
        reference_driver_sha256=fit808.digest(Path(field808.__file__)),
        tone_driver_sha256=fit808.digest(Path(tone_factor808.__file__)),
        benchmark_driver_sha256=fit808.digest(Path(fit808.__file__)),
        project_revision=cpu.revision(cpu.ROOT),
        native_library_sha256=fit808.digest(Path(runner.native.DEFAULT_LIB)),native_info=runner.core.info(),
        digikit_revision=cpu.revision(cpu.ROOT/'vendor/digikit'),elekloader_revision=cpu.revision(cpu.ROOT/'vendor/elekloader'),
        controls=dict(native_words=32513,finite_weights=True,stable_poles=True),
        python_instruction_witnesses=python_witness(receipt,artifact),
        maximum_port_dsp_fs=max(r['port_max_dsp_fs'] for r in rows),
        maximum_instructions=runner.maximum_instructions,
        timing_note='Instruction counts are not cycle counts or physical deadline/headroom proof.',
        unqualified=['this isolated report does not qualify the native package or physical timing',
                     'analog retrigger behaviour','fresh independent source acceptance'])
    manifest={k:v for k,v in report.items() if k.endswith('_sha256')}
    manifest.update(scope=report['scope'],cohort_note='Same development listening cohort as the frozen model; four fitting corners and twelve validation settings. Prediction audio is actual assembled SHARC output.')
    if SOURCE.read_bytes() != (folder/'engine-source.s').read_bytes():
        raise ValueError('ASM source changed during qualification')
    report['listening_gain']=listening808.listening_report(folder,chosen,references,predictions,manifest)
    make_plots(folder,references,predictions,rows)
    (folder/'report.json').write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    return report


def make_plots(folder,references,predictions,rows,backend='SHARC'):
    import numpy as np
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    pairs=[(0,0),(0,127),(127,0),(127,127)]
    fig,axes=plt.subplots(4,2,figsize=(12,10),layout='constrained')
    for i,pair in enumerate(pairs):
        a,b=references[pair],predictions[pair]
        axes[i,0].plot(np.arange(2400)/48,a[:2400],label='Recorded',color='#333333')
        axes[i,0].plot(np.arange(2400)/48,b[:2400],'--',label=f'{backend} ASM',color='#00838c')
        axes[i,0].set(xlabel='Time (ms)',ylabel=f'Capture FS\nTone {pair[0]} / Decay {pair[1]}')
        axes[i,1].plot(np.arange(24000)/48,(b-a)[:24000],color='#00838c')
        axes[i,1].set(xlabel='Time (ms)',ylabel='Residual (capture FS)')
        axes[i,0].grid(alpha=.2);axes[i,1].grid(alpha=.2)
    axes[0,0].legend()
    fig.suptitle(f'Executed {backend} ASM — frozen 808 candidate')
    fig.savefig(folder/'waveforms.png',dpi=140);plt.close(fig)
    # Preserve the native audio/ABX player; append scientific plots and the actual numerical receipt.
    decorate_html(folder/'index.html',rows)


def decorate_html(page,rows):
    text=page.read_text().replace('src="corners.png"','src="waveforms.png"')
    text=text.replace('Full numerical report and optimizer diagnostics','Full numerical report and ASM qualification')
    summary=f"<section><h2>Executed ASM qualification</h2><p>Maximum port error: {max(r['port_max_dsp_fs'] for r in rows):.4g} DSP FS. Native-package and physical checks are reported separately. Tone/Decay latch on START. The combined SHARC mod also includes the reference-driven 909; this report evaluates the 808 only.</p><img src='waveforms.png' style='width:100%;max-width:1200px' alt='Four-corner recorded and assembled waveforms and residuals'><p><a href='report.json'>Full numerical receipt</a></p></section>"
    page.write_text(text.replace('</html>',summary+'</html>'))



if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command',choices=('build','qualify'))
    args=parser.parse_args()
    result=qualify() if args.command=='qualify' else build()[0]
    print(json.dumps(result if args.command!='qualify' else dict(status=result['status'],report=str(OUT/'index.html'),maximum_port_dsp_fs=result['maximum_port_dsp_fs'])))
