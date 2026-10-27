# Initial 808 frequency switch

This #9/#79 increment adds the first, brief frequency-switch stage to both
CPUs. It is separate from the slower nonlinear pitch sigh and from the C39
companion retrigger pulse. The excitation remains the existing 1 ms rectangle.
The whole initial pitch/excitation workstream is still incomplete.

## Source baseline and explicit approximation

The archived sources in [the manifest](../research/manifest.json) are unchanged.
S01's bass-drum schematic on p.9 confirms R165=47 kΩ, R166=6.8 kΩ and
R161=1 MΩ. S03 Eq.7 uses `Rk = R161 || (R165+R166)` for the linear feedback
path. In §8.1, Q43 bypasses R165 during attack, leaving `R161 || R166`.
The corresponding natural-frequency ratio is approximately:

```
Rk_normal = 1 / (1/1000000 + 1/53800) = 51053.3308 ohms
Rk_attack = 1 / (1/1000000 + 1/6800)  =  6754.0723 ohms
ratio = sqrt(Rk_normal/Rk_attack) = 2.74934467
```

Apply that ratio to the existing calibrated settled frequency: approximately
131.006273 Hz during the initial window, then 47.65 Hz. This is a switched
modal approximation using the published pole relationship, not the complete
loaded bridged-T/feedback/input-transfer network. Keep the existing calibrated
Decay radius and fixed drive scale; no per-hit gain or phase fit is introduced.

Timing is not silently reconciled. S01 p.5 describes a roughly 4 ms Q43 interval
and a later C39/R161 retrigger. S03 §8.1 describes the envelope remaining high
about 5 ms after the 1 ms trigger falls, about 6 ms total. The original Plaits
class also has a 6 ms FM pulse, but it is not stock calibration. This increment
uses the S03 6 ms working baseline. Exact gating against the captured VST and
original hardware is unqualified; the service-note discrepancy remains visible.

S03 distinguishes this switch from leakage-driven pitch sigh in §8.2. It also
explains why C39/R161/D52 supplies a companion excitation at the switch. That
path, pulse-edge/diode shaping, nonlinear leakage, physical forcing/scale and
residual-state retrigger remain open. Do not treat this isolated switch as a
complete or necessarily closer software-reference attack.

## Model, state and independent checks

At 48 kHz, START clears x/y and loads the existing private counter with 288.
Only its first 48 samples apply the existing `0.25/48` drive. All first 288
samples use the higher rotation frequency; subsequent samples use the settled
one. The state and accumulated phase are retained at the frequency transition.
There are still three ColdFire words per voice and 512 private SHARC bytes.
No C/SDK calling convention, saved format, ID or control changes.

The phase at sample boundary `j` is:

`theta(j) = 2*pi/48000 * (f_attack*min(j,288) + f_normal*max(0,j-288))`.

The independent oracle convolves the 48 drive samples with analytical responses
using `sin(theta(n+1)-theta(k))` and accumulated log retention. It does not copy
either CPU recurrence. Direct convolution checks include the 48-sample drive
edge and the 288-sample frequency transition. Actual CPU tests check the
private counter after every block and the unshifted waveform against that oracle.

Both time windows align to the existing fixed 32-sample callback contract:
the drive spans 32+16 samples; the frequency window spans nine blocks. Existing
native counter hooks now check 288→256→...→0, with the first 48 drive samples
qualified separately by the actual-ASM waveform/edge checks. DN2's settled
counter observation stays separate from that exact component timing proof.

Live controls, retriggers, interleaving, MODEL changes, state/output/context
guards, quarter-scale body/half-scale composed headroom and the 1e-5 FS numeric
limit remain. Instruction counts are informational; no instruction budget.

## Reference comparison and next work

Preserve the same five training settings and raw timing/gain conventions.
The original HTML remains unchanged. New float renders and measurements belong
in `out/reference/808-initial/`. Held-out recordings stay unused.

The analytical trial showed mixed raw-waveform results: the long settings
improved, while default and short settings worsened. The missing companion
retrigger/forcing and diode paths are consequently the next planned work,
not extra fitting to hide the mismatch. Actual-CPU/native evidence must be
recorded before qualifying this integrated slice. #9/#79/#2 remain open for
the full attack and fidelity; #78/#20/#80 retain their existing native gates.

## Component and first native evidence

120 host tests and independent C/UI suites pass. The shared SHARC suite passes
9,012 calls, with 1,308 code bytes and unchanged 512 private state bytes. Matching
composed CPU errors remain under 1e-5 FS: maximum errors are 1.403e-6 FS
(ColdFire), 6.951e-7 FS (SHARC), and 2.065e-6 FS between CPUs. Guard, fractional,
join/live-control, retrigger/interleaving and existing 909 checks remain active.

DT native functional checks pass across 39,779 callbacks and 28,969 observed
initial-counter/coupling blocks, with every post-block value 0/32/.../256 seen.
Only known #78 parameter/page resets fail. DN passes 100,801 callbacks and
92,420 observed counter/coupling blocks, with the same complete counter set
and all three exact-zero capture baselines. The historical #20 residue remains
unresolved; another waveform's passing baseline does not identify its cause.
DN2's tested native scenario passes 31,879 DSP frames with no halt/missing
blocks. The native counter bank is consumed after the settled note; exact
1 ms drive / 6 ms frequency timing remains component proof. Native controls,
locks/LFO, reload, mixed models, Tone/coupling and 909 checks remain passing.
#80 is separately unqualified.

## Actual-CPU reference diagnostic

Fresh 96,000-sample renders on both CPUs retain the same fifteen verified
fresh training references, scheduled MIDI at zero and one reference multiplier
×4 to undo the known host gain. No fitted gain, normalization or alignment.
The previous revision is the reference-informed Decay increment.

| Setting | Whole-clip raw RMS FS, before / after | First 6 ms raw RMS FS, before / after |
| --- | --- | --- |
| Default | 0.02770 / 0.06564 | 0.33318 / 0.26926 |
| Dark, short | 0.02034 / 0.02409 | 0.28472 / 0.21871 |
| Bright, short | 0.02126 / 0.02516 | 0.31264 / 0.24848 |
| Dark, long | 0.08514 / 0.06791 | 0.31949 / 0.23705 |
| Bright, long | 0.08638 / 0.06912 | 0.35060 / 0.26723 |

The source-selected first 6 ms window improves at every setting. The first 25 ms
and first 150 ms windows worsen at every setting. Whole-clip default/short
residuals also worsen; long clips improve. These are descriptive comparisons,
not a fidelity pass or a justification to prefer only the favorable window.
The missing companion/forcing stages are the next required work before
claiming the attack is improved as a whole. Detailed windows, analyzer outputs,
source/executable hashes and raw floats remain in
`out/reference/808-initial/measurements.json`. The HTML remains unchanged.

For the default, first 25 ms RMS rises 0.21302→0.28938 FS and first 150 ms RMS
rises 0.09693→0.22422 FS. Do not judge the stage only by its first 6 ms or
long-clip improvements. The gate currently applies on every START with fixed
intrinsic excitation; accent-dependent behavior remains unmodeled.

Full two-second model-error maxima are 1.409e-6 FS (ColdFire), 6.509e-7 FS
(SHARC), and 2.005e-6 FS between CPUs, below the unchanged 1e-5 FS numeric
limit. These do not resolve the software-reference regressions.

Firmware SHA256 for the native runs:

- DT: `8ccc3f59131218f6590e4bd06e07515b3fa81be271c79c84e1dc7df2bc191efb`.
- DN: `87b25590e4782546f735aa8f8f19955f33e8fbd5f53b40db19045deea055a983`.
- DN2: `f1b936a5601572df11e1fc88f6e2f263e196a5baa77bfd7f684fcee31906df7a`.
