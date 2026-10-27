# 808 C47 coupling stage

The 808 path now runs body → Tone → C47 coupling in the existing combined mods.
This [#9](https://github.com/simonjohansson/x0x/issues/9)/
[#79](https://github.com/simonjohansson/x0x/issues/79) increment models one
unloaded RC stage. It adds no saved control: native track level still controls
volume, and the internal VR4 position is fixed wide open.

## Source and approximation

Roland service notes S01 p.9 show C47=0.47 µF and VR4=100 kΩ. Werner/Abel/Smith
S03 §9/Table1 describes this as the level/coupling high-pass; its VR6 identifier
is corrected to VR4 against the schematic. S04 §1.7 cross-checks the values and
warns that treating the output network as separate unloaded stages omits loading.
Source paths, URLs and hashes are in [the manifest](../research/manifest.json).

For this explicitly isolated, full-level approximation,
`H(s)=s*R*C/(1+s*R*C)`, `R=100000`, `C=0.47e-6`.
The time constant is 47 ms and cutoff is 3.386275 Hz. It is not the C49/R176/R177
network, transistor buffer or C50 output stage. Coupling/loading between those
stages and the Tone/level network remains open; this is not a complete or
calibrated 808 output model.

## Model and implementation

At 48 kHz, bilinear coefficients are `A=4511/4513` and `B=4512/4513`:

`y[n] = A*y[n-1] + B*(x[n]-x[n-1])`.

The [independent reference](../tools/x0x/coupling808.py) instead integrates
capacitor voltage/current with the trapezoidal rule and obtains output from the
resistor voltage. Host tests compare its step and frequency response with the
closed-form transfer and check long DC/sign changes. Actual CPU comparisons
use the complete body/Tone/coupling signal, with no alignment or normalization
and the unchanged 1e-5 FS waveform-error limit.

The [ColdFire kernel](../targets/coldfire/coupling808.s) uses two Q31 state words
per voice and accumulates all three products in EMAC before extraction. Its
constant-input rounding fixed point is projected to zero when both input and
output would otherwise remain unchanged. Such a fixed point is bounded by
half an output LSB divided by `1-A`, approximately 5.3e-7 FS. Clearing it avoids
a permanent numerical DC tail without an amplitude gate on changing signals.
The actual two-second DC check now reaches exact zero; the original rounded
recurrence retained 5.271e-7 FS. Full EMAC/callee/stack and ownership guards remain.

The [SHARC callback](../targets/sharc/body808.s) uses two float states per voice
at offset 320, after the unchanged metadata/body/Tone banks. Total private state
is 448 bytes. Both backends reset the chain on the prototype's current START,
MODEL-change and ownership lifecycle; live Tone/Decay edits keep state.
Residual circuit-state retrigger behavior remains later work.

The input is bounded by 0.25 FS. The high-pass impulse's absolute sum is `2*B<2`,
so the output bound is 0.5 FS. A long-Decay reference reaches 0.255941 FS: retaining
the old quarter-scale output assertion would reject the expected RC transient.
The body gain itself stays unchanged, 909 retains its quarter-scale bound, and
waveform-error tolerances are unchanged. Instruction counts are informational;
there is no instruction-count budget.

The HP transient changes finite-window fits of filtered peaks. Tests compare
those fits with the complete independent filtered reference. The underlying
provisional oscillator feedback/Decay curve remains 142 ms–1 s, default 250 ms;
it is not redefined by fitting the filtered output.

## Verification

Run `mise run test`, then `mise run test:808:body` for actual CPU stages and
matching comparisons. `mise run test:808:coldfire:coupling` isolates the new
kernel, using the existing Tone component's files for composed checks.

114 host tests and all independent C/UI checks pass. The isolated ColdFire
rich-input error is 3.469e-8 FS. Matching CPU renders give:

| Decay raw | Tone raw | Samples | ColdFire/reference | SHARC/reference | CPU difference |
| --- | --- | --- | --- | --- | --- |
| 0 | 16384 | 24000 | 5.465e-8 | 4.439e-7 | 4.424e-7 |
| 16384 | 16384 | 24000 | 3.409e-7 | 6.140e-7 | 3.707e-7 |
| 32512 | 16384 | 24000 | 5.329e-7 | 9.104e-7 | 6.599e-7 |
| 16384 | 0 | 8192 | 2.995e-7 | 6.793e-7 | 4.331e-7 |
| 16384 | 32512 | 8192 | 3.091e-7 | 4.767e-7 | 5.058e-7 |

The combined SHARC component retains invalid-input atomicity, context and owned
buffer/state checks, independent slots, START-latched MODEL, live edits and the
unchanged 909 triangle comparison. Its combined code uses 982 bytes and private
state uses 448 bytes; instruction counts do not determine pass/fail.

| Native device | Coupling evidence | Existing regression |
| --- | --- | --- |
| DT 1.54 | 28089 actual coupling calls after Tone; owned state, START reset and entry-state recurrence checked; maximum recurrence error 5.311e-7 FS | 32139 callbacks complete; only deferred #78 parameter/page reset checks fail |
| DN 1.44 | 41198 actual coupling calls; maximum entry-state recurrence error 5.335e-7 FS; exact zero PCM baseline restored after the integer fixed-point correction | 47160 callbacks pass, including 808 Tone/Decay, 909, locks/LFO, persistence and mixed models |
| DN2 1.12 | Owned coupling input matches reconstructed last Tone output within 7.865e-10/4.610e-9 FS at Tone endpoints; output differs as expected; native PCM peaks 0.021538/0.021869 FS | Tested combined scenario passes 23771 DSP frames; stock coexistence, controls, reload, both models retained; no halt/missing blocks |

DT/DN compare the kernel against its actual entry state and input as a native
call/route check, separately from the independent whole-circuit component
reference. DN2 inspects private state separately from its stock-processed voice
buffers and downstream PCM. Its saved-909 T1 capture does not qualify #80.
Existing unnormalized captures and reports remain under `out/{dt,dn,dn2}/silent`.

Firmware SHA256 values for these native runs are:

- DT: `0ac9b9d57b84a1bd3516a3c5cc1a0dcc41851d52ff0e59f4d101cf581df1dbb0`.
- DN: `2aacce3a0af212eab9c23502ec454c89c58b9383c15737b441e53c0bc2df10e9`.
- DN2: `cffc7be0f5a4263b175e1fa74ef1a47f9210cc6e8b35a3e71f658a5a6e76eb23`.

Full loaded-circuit fidelity, VST #2 and physical-device testing remain outside
this increment. Known DT reset failure #78 and the separate DN2 post-STOP
control-delivery failure #80 remain open.
