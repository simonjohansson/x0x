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
Only known #78 parameter/page resets fail. DN/DN2 native validation and the
fresh actual-CPU five-setting comparison are still running at this increment;
component passes do not qualify their pending results.
