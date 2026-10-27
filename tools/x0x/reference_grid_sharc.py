"""Private reference renderer: actual frozen SHARC code, never a host substitute.

Import directly from a tracked driver whose PYTHONPATH selects the requested
frozen x0x modules. prepare() builds fresh inputs; no old out/ receipt is needed.
"""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
import struct
import time

from x0x import cpu, sharc_callback as cb, sharc_selector as selector, sharc_body808 as body
from tools.sharc_dev import sharc_transpile_run as nr

HERE = MANIFEST = RUNTIME = CODE = ENTRY = STATE_BYTES = LIBRARY = None


def _configure(support):
 global HERE, MANIFEST, RUNTIME, CODE, ENTRY, STATE_BYTES, LIBRARY
 HERE = Path(support).resolve()
 MANIFEST = json.loads((HERE/'accepted.json').read_text())
 frozen = Path(MANIFEST['frozen_source_root'])
 if not Path(cb.__file__).resolve().is_relative_to(frozen) or cpu.ROOT != frozen:
  raise ValueError('put the requested frozen tools first on PYTHONPATH')
 if cb.STATE != MANIFEST['state_address'] or body.STATE_BYTES != MANIFEST['state_bytes']:
  raise ValueError('frozen fixture/private state disagrees with kernel receipt')
 if os.environ.get(nr.ALLOW_STALE_ENV) == '1' or os.environ.get('SHARC_NATIVE_LIB'):
  raise ValueError('reference rendering forbids stale/native-library overrides')
 CODE = (HERE/'accepted-kernel.bin').read_bytes()
 if hashlib.sha256(CODE).hexdigest() != MANIFEST['code_sha256']:
  raise ValueError('accepted kernel bytes changed')
 ENTRY, STATE_BYTES = MANIFEST['entry_pc16'], MANIFEST['state_bytes']
 RUNTIME = json.loads((HERE/'runtime.json').read_text())
 LIBRARY = Path(RUNTIME['library_path'])
 if hashlib.sha256(LIBRARY.read_bytes()).hexdigest() != RUNTIME['sha256']:
  raise ValueError('qualified native library bytes changed')


def _run(core):
 # Wall-clock hang protection, not an instruction/performance budget.
 deadline = time.monotonic() + cb.CALL_TIMEOUT_SECONDS
 before = core.stats()['traps']; steps = 0
 while core.pc() != cb.RETURN:
  count = core.run(100000); steps += count
  if core.stats()['traps'] != before or (count == 0 and core.pc() != cb.RETURN):
   raise RuntimeError(('actual NativeCore trapped', core.pc(), core.halt_reason))
  if time.monotonic() > deadline:
   raise TimeoutError('actual SHARC callback did not return before the watchdog')
 return steps


def _seed(row):
 fixture=cb.CallbackRunner(CODE,ENTRY);trace=fixture.trace
 pokes={**{cb.STATE+i:0 for i in range(0,STATE_BYTES,4)},**selector.raw_words(row),
        cb.STATE-4:cb.GUARD,cb.STATE+STATE_BYTES:cb.GUARD}
 regs={name:0x10203040+i for i,name in enumerate(trace.UREG_NAMES)
       if name.startswith(('R','I','M','L','B','S')) and name[1:].isdigit()}
 regs.update(R4=cb.INPUT if row['input_present'] else 0,I6=cb.FRAME,I7=cb.FRAME-8,
             MODE1=0x10000,M5=0,M6=1,M7=0xffffffff,M13=0,M14=1,M15=0xffffffff,
             **{f'L{i}':0 for i in range(6)})
 regs.update(MODE2=0x10203040,IMASK=0x10203040,IMASKP=0x10203040,
             PX1=0x5a,PX2=0x12345678,ASTATY=0x101,STKYY=0x202)
 runner=fixture.sr.Runner(fixture.memory,ENTRY,regs=regs,pokes=pokes,
                          breakpoints=[cb.RETURN],diagnose_unknown=True)
 s=runner.state;s.stack_model=True;s.pc_stack=[0x01000100,0x100]
 s.status_stack=[(trace.Const(0x303),trace.Const(0x404),trace.Const(0x10000))]
 s.loops=[trace.Loop(0x100,0x101,3,0)];s.loop_depth=1
 s.loop_slots[0]=(trace.Const(0x101),trace.Const(3))
 s.special.update({name:fixture._mr(0x123456789abcdef) for name in ('MRF','MRB','MSF','MSB')})
 s.special['BFFWRP']=trace.Const(7)
 for sync in fixture._sync:sync(s)
 return fixture,runner


class FastRunner:
 def __init__(self,support):
  _configure(support)
  self.manifest,self.runtime,self.code,self.entry = MANIFEST,RUNTIME,CODE,ENTRY
  row=selector.case('initial',model=0)
  self.fixture,py=_seed(row);self.template=py.state
  self.core=nr.NativeCore(nr.pack_image(self.fixture.memory),str(LIBRARY))
  nr.to_native(self.core,py.state)
  self.core.set_option(nr.OPT_RUNTIME_DECODE,1)
  self.core.set_option(nr.OPT_BLOCKS,0)
  self.core.set_option(nr.OPT_STOP_PC,cb.RETURN)
  self.calls=0;self.worst_instructions=0
  self.info=self.core.info()

 def _poke(self,address,data):
  if self.core.poke(address,data,1)!=len(data):raise RuntimeError('short native poke')

 def call_raw(self,row,state_writable=True):
  # Fresh software frames do not reset the author state; START is actual code.
  self.core.fresh_call(ENTRY)
  for name,value in [('R4',cb.INPUT if row['input_present'] else 0),('I6',cb.FRAME),('I7',cb.FRAME-8)]:
   self.core.set_reg(self.fixture.trace.UREG_CODES[name],self.fixture.trace.Const(value))
  self._poke(cb.INPUT,struct.pack('<5I',cb.OUTPUT,row['slot'],row['pitch'],row['flags'],cb.PARAM if row['params_present'] else 0))
  self._poke(cb.PARAM,struct.pack('<40I',*row['params']))
  steps=_run(self.core)
  self.calls+=1;self.worst_instructions=max(self.worst_instructions,steps)
  for address in (cb.STATE-4,cb.STATE+STATE_BYTES,cb.OUTPUT-4,cb.OUTPUT+128):
   if self.core.peek(address)!=cb.GUARD:raise AssertionError(('guard',hex(address)))
  words=[self.core.peek(cb.OUTPUT+4*i) for i in range(32)] if row['input_present'] else None
  if words is not None and any(v is None or v==cb.GUARD for v in words):raise AssertionError('unwritten output')
  return words

 def state_words(self):return [self.core.peek(cb.STATE+i) for i in range(0,STATE_BYTES,4)]

 def render(self,model,tone_raw,decay_raw,frames,attack_raw=16384):
  if model not in (808,909):raise ValueError('model must be 808 or 909')
  if type(frames) is not int or frames<0:raise ValueError('bad sample count')
  if any(type(v) is not int or not 0<=v<=32512 for v in (tone_raw,decay_raw,attack_raw)):raise ValueError('native controls required')
  row=selector.case('training-grid',model=0 if model==808 else 32512)
  row['params'][0:3]=[tone_raw,decay_raw,attack_raw]
  result=bytearray()
  for block in range((frames+31)//32):
   row['flags']=int(block==0);words=self.call_raw(row)
   result.extend(struct.pack('<32I',*words))
  return bytes(result[:frames*4])


def context_proof(row):
 fixture,py=_seed(row)
 core=nr.NativeCore(nr.pack_image(fixture.memory),str(LIBRARY));nr.to_native(core,py.state)
 core.set_option(nr.OPT_RUNTIME_DECODE,1);core.set_option(nr.OPT_BLOCKS,0);core.set_option(nr.OPT_STOP_PC,cb.RETURN)
 _run(core)
 native=nr.to_python(core,py.state)
 while True:
  try:py.step()
  except fixture.sr.Halt as h:
   assert h.reason=='breakpoint' and py.state.pc_sw==cb.RETURN;break
 # Whole modeled architectural state, plus every author/input/output/frame word.
 from tools.sharc_dev import sharc_diff as sd
 regions=[(cb.STATE-4,STATE_BYTES+8),(cb.INPUT,20),(cb.PARAM,160),(cb.OUTPUT-4,136),(cb.FRAME-12,20)]
 a=sd.export_state(py.state,memory_ranges=regions,page_hash=False)
 b=sd.export_state(native,memory_ranges=regions,page_hash=False)
 a['stopped']=b['stopped']=None
 differences=sd.compare_states(a,b)
 assert not differences,differences[:10]
 return dict(label=row['label'],native_steps=core.stats()['instructions'],whole_context_equal=True)


def _immutable(path, data):
 path = Path(path)
 if path.exists():
  if path.read_bytes() != data:
   raise ValueError('use a new support directory for changed immutable inputs: '+str(path))
 else:
  path.write_bytes(data); path.chmod(0o444)


def prepare(frozen, support):
 """Compile requested tracked code, qualify the real native runtime and cache it.

 ``frozen`` is reference_grid_common.prepare_frozen's source/pin receipt.
 Generated-core prerequisites remain the standard Digikit bootstrap's job.
 """
 if os.environ.get(nr.ALLOW_STALE_ENV) == '1' or os.environ.get('SHARC_NATIVE_LIB'):
  raise ValueError('reference rendering forbids stale/native-library overrides')
 support = Path(support).resolve(); support.mkdir(parents=True, exist_ok=True)
 source_root = Path(frozen['frozen_source_root']).resolve()
 if cpu.ROOT != source_root or not Path(cb.__file__).resolve().is_relative_to(source_root):
  raise ValueError('re-enter this driver with the frozen package first on PYTHONPATH')
 for name, pin in frozen['pins'].items():
  if cpu.revision(source_root/'vendor'/name) != pin:
   raise ValueError('vendor pin changed: '+name)
 source = source_root/'targets/sharc/body808.s'
 source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
 if source_hash != frozen['source_sha256']['targets/sharc/body808.s']:
  raise ValueError('frozen SHARC source changed')
 helper_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
 proof_path = support/'proof.json'
 if proof_path.exists():
  cached = json.loads(proof_path.read_text())
  if (cached.get('status') == 'passed' and cached.get('helper_sha256') == helper_hash
      and cached['manifest']['source_snapshot'] == frozen):
   runner = FastRunner(support)  # Includes current core/generator stale checks.
   if runner.manifest != cached['manifest'] or runner.runtime != cached['runtime']:
    raise ValueError('cached native proof inputs changed')
   return dict(manifest=runner.manifest, runtime=runner.runtime,
               proof_path=str(proof_path), proof_sha256=hashlib.sha256(proof_path.read_bytes()).hexdigest())
  raise ValueError('use a fresh support directory for a different source/helper')
 kernel = support/'kernel'; kernel.mkdir(exist_ok=True)
 code, entry, _ = cb.build(kernel, source)
 sdk = cpu.require_module('elekloader.sdk.sharc', 'elekloader')
 layout = body.voice_layout() if hasattr(body, 'voice_layout') else sdk.machine_layout('voice')
 cb.validate_layout(layout, code, entry)
 if body.STATE_BYTES > layout['data_bytes']:
  raise ValueError('frozen private state exceeds its own layout')
 cb.decoded_instructions(code, entry)
 manifest = dict(source_snapshot=frozen, accepted_commit=frozen['commit'],
  frozen_source_root=str(source_root), source_sha256=source_hash,
  code_sha256=hashlib.sha256(code).hexdigest(), code_bytes=len(code),
  entry_pc16=entry, state_address=cb.STATE, state_bytes=body.STATE_BYTES, layout=layout)
 _immutable(support/'accepted-kernel.bin', code)
 from tools.sharc_dev import sharc_native_lib
 standard = sharc_native_lib.library_path()
 vendor = (source_root/'vendor/digikit').resolve()
 # Cargo also checks Rust wrapper changes, beyond the core/version stamp.
 subprocess.run([sys.executable, '-m', 'tools.devtools.benchlock', 'run', '--shared',
  '--label', 'x0x reference NativeCore library', '--', sys.executable, '-m',
  'tools.sharc_dev.sharc_native_lib'], cwd=vendor, check=True)
 current = nr.NativeCore(nr.pack_image(None), str(standard))
 library = support/standard.name; _immutable(library, standard.read_bytes())
 runtime = dict(library_path=str(library), built_standard_path=str(standard),
  sha256=hashlib.sha256(library.read_bytes()).hexdigest(), native_info=current.info(),
  generated_fingerprint=(standard.parents[2]/'gen/CORE_FINGERPRINT').read_text().strip(),
  stale_override=False)
 (support/'accepted.json').write_text(json.dumps(manifest, indent=2)+'\n')
 (support/'runtime.json').write_text(json.dumps(runtime, indent=2)+'\n')
 _configure(support)
 contexts=[]
 for model in (0,32512):
  for slot in (0,15):
   row=selector.case(f'context-{model}-{slot}',slot=slot,model=model)
   row['params'][0:3]=[16384]*3; contexts.append(context_proof(row))
 rows=[]
 for model in (808,909):
  for raw in (0,16384,32512):
   guarded=selector.SelectorRunner(code,entry,state_bytes=body.STATE_BYTES,
    extra_slot_state_offset=128,tone_state_offset=256,coupling_state_offset=320,
    pulse_state_offset=448,companion_state_offset=512,main_state_offset=576,
    coefficient_state_offset=640,vca_coefficient_state_offset=1024)
   fast=FastRunner(support)
   for block in range(16):
    row=selector.case('native-preflight',model=0 if model==808 else 32512,flags=int(block==0))
    row['params'][0:3]=[raw,raw,16384]
    expected, state=guarded.call_raw(row,True); actual=fast.call_raw(row)
    if struct.pack('<32f',*expected)!=struct.pack('<32I',*actual) or state!=fast.state_words():
     raise AssertionError('actual native audio/private state differs from guarded execution')
   rows.append(dict(model=model,tone_raw=raw,decay_raw=raw,frames=512,
                    output_and_private_state_byte_identical=True))
 proof=dict(status='passed',scope='actual firmware-free NativeCore vs guarded instruction fixture; not native OS/hardware',
  manifest=manifest,runtime=runtime,helper_sha256=helper_hash,contexts=contexts,cases=rows,
  stale_override=False,model_substitution=False)
 proof_path.write_text(json.dumps(proof,indent=2)+'\n')
 return dict(manifest=manifest,runtime=runtime,proof_path=str(proof_path),
             proof_sha256=hashlib.sha256(proof_path.read_bytes()).hexdigest())
