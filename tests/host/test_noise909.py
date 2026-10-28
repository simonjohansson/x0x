"""Deterministic continuous clock, source KCL and physical bandwidth baseline."""
import unittest
from x0x import noise909 as noise,attack909 as pulse

class Noise909Tests(unittest.TestCase):
 def test_lfsr_recurrence_and_five_delayed_output_bits(self):
  word=noise.DEFAULT_SEED
  bits=[]
  for _ in range(128):
   bits.append((word>>30)&1);word=noise.shift(word)
   if len(bits)>=6:self.assertEqual((word>>35)&1,bits[-5])
  self.assertNotEqual(word,noise.DEFAULT_SEED)
  with self.assertRaises(ValueError):noise.source_interval((0,0))
 def test_one_audio_block_always_advances_two_hundred_clocks(self):
  source=(noise.DEFAULT_SEED,0);expected=noise.DEFAULT_SEED
  for _ in range(200):expected=noise.shift(expected)
  _,after,_=noise.continue_reference(source,noise.INITIAL_FILTER,16384,32)
  self.assertEqual(after,(expected,0))
 def test_source_averages_keep_fractions_and_chunk_independence(self):
  source=(noise.DEFAULT_SEED,7)
  out,a,cap=noise.continue_reference(source,noise.INITIAL_FILTER,16384,64)
  first,b,state=noise.continue_reference(source,noise.INITIAL_FILTER,16384,32)
  second,b,state=noise.continue_reference(b,state,16384,32)
  self.assertEqual(out,first+second);self.assertEqual(a,b);self.assertEqual(cap,state)
 def test_passive_capacitor_kcl_includes_c11_loading(self):
  s=(.1,-.2,.03);drive=.4;raw=16384
  d=noise.derivative(s,drive,raw);z,a,b=noise.mix(raw);node=a*s[1]-b*s[2]
  i15=(drive-s[0]-s[1])/(noise.RTH+noise.R46)
  self.assertAlmostEqual(noise.C15*d[0],i15)
  self.assertAlmostEqual(noise.C13*d[1],i15-(s[1]-node)/pulse.R45)
  self.assertAlmostEqual(pulse.C11*d[2],(-s[2]-node)/pulse.R44)
  self.assertAlmostEqual((-s[2]-node)/pulse.R44+(s[1]-node)/pulse.R45,node/pulse.R56+node/z)
 def test_average_drive_is_bounded_by_clock_edge_oracle(self):
  for raw in (0,16384,32512):
   s=(noise.DEFAULT_SEED,3);a,asrc,_=noise.continue_reference(s,noise.INITIAL_FILTER,raw,512)
   b,bsrc,_=noise.oracle(s,noise.INITIAL_FILTER,raw,512)
   self.assertEqual(asrc,bsrc)
   # Q6's maximal nominal gain is less than1; compare the un-gated current unit.
   self.assertLess(max(abs(x-y)*pulse.CURRENT_TO_AUDIO for x,y in zip(a,b)),1e-5)
 def test_env2_is_identical_to_the_pulse_network(self):
  env=noise.env2(256,substeps=16);state=pulse.INITIAL_STATE;count=96
  for wanted in env:
   _,state,count=pulse.continue_reference(state,count,16384,1,substeps=16)
   self.assertEqual(wanted,max(state[6]-.6,0)/16)
 def test_live_attack_preserves_the_continuous_filter_and_clock(self):
  first,source,state=noise.continue_reference((noise.DEFAULT_SEED,0),noise.INITIAL_FILTER,0,32)
  second,source,state=noise.continue_reference(source,state,32512,32)
  allout,expected,cap=noise.continue_reference((noise.DEFAULT_SEED,0),noise.INITIAL_FILTER,0,64,changes={32:32512})
  self.assertEqual(first+second,allout);self.assertEqual(source,expected);self.assertEqual(state,cap)

if __name__=='__main__':unittest.main()
