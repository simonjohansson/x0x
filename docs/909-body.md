# 909 triangle body and live Decay

This [#25](https://github.com/simonjohansson/x0x/issues/25) increment adds an
unshaped triangle foundation to the existing combined mod. It is not yet a
complete or calibrated 909. The stock pitch path, diode shaping, complete VCA/envelopes,
Attack pulse/noise and circuit retrigger behavior remain open in #25/#79.
The existing controls/IDs and START-latched MODEL selection stay unchanged.

## Source boundary and provisional model

Roland service notes S02 p.4/p.11 and Whittle S05 p.3/p.12 identify a triangle
relaxation oscillator around IC13, then antiparallel diode shaping at D10/D11
through R52=10 kΩ. The original schematic, not the 909-like Plaits class, is
the selected baseline. Source hashes/paths are recorded in
[research/manifest.json](../research/manifest.json).

The triangle's fixed 50 Hz pitch, internal gain 0.25 and zero-crossing phase
restart remain provisional audition values. Live DECAY now uses the unloaded
C8 discharge path described below; it is not the complete Roland ENV1/VCA. Unlike 808's resonant feedback loss, this amplitude
multiplies a separate oscillator. Native AMP/velocity, filtering, effects and
track volume remain downstream.

At 48 kHz, the independent analytical reference is

`y[n] = 0.25 * exp(-sum(1/(48000*tau(d[k])), k=0..n)) * (2/pi) * asin(sin(2*pi*50*(n+1)/48000))`.

### Unloaded C8 Decay increment

S02 p.11 and S05 p.12 draw C8=0.33 µF, VR5=1 MΩ(A) wired as a rheostat,
and R58=47 kΩ in the ENV1 discharge path. The first functional Decay mapping is
`tau(d) = C8 * (R58 + VR5*d/32512)`, using the exact delivered native word.
Minimum/default/maximum time constants are 15.510/181.809/345.510 ms.
The saved default remains 64; only its formerly provisional 250 ms sound changes.

This is an **unloaded RC approximation**, with a provisional resistance-linear
mapping. The physical A taper is uncalibrated. D8/R36/R22, loading through R54
into Q12, charging/accent and the transistor VCA transfer remain missing. Thus
the component values are source-derived but the complete audible envelope and
control curve are not claimed faithful. 808 Decay keeps its separate feedback model.

Each backend computes bilinear capacitor retention `r = 1-2/(1+2*48000*tau)`
once per block. ColdFire forms the denominator in unsigned Q16 and uses fractional
integer division; SHARC refines a positive reciprocal and applies a small negative
amplitude increment to avoid rounding a near-one retention. Live edits retain
phase and accumulated envelope. START still restarts both. State size, IDs,
public SDK boundary, native level and saved controls do not change.

The independent oracle integrates the continuous analytical exponential rather
than copying the DSP recurrence. Corner/fractional words and live long/short
edits must pass the unchanged 1e-5 FS waveform tolerance, without fitting,
alignment or normalization.

Each ASM backend uses a wrapping unsigned 32-bit phase accumulator with step
`round(50*2^32/48000)=4473924`, then folds it into a triangle and multiplies by
the decaying amplitude. Starting phase 0x40000000 in the folded representation
corresponds to a rising zero crossing. Phase/amplitude advance before each
output sample. Ordinary note pitch does not transpose this prototype.

The two body words are private per-voice state, reused between selected models;
MODEL switching clears the selected voice's old state. Every START currently
restarts the prototype's phase and amplitude. This does not claim the physical
909's clamp-release or free-running behavior. The 808 retains its separate
Tone history and existing live Tone/Decay behavior.

909 DECAY shapes amplitude on every callback. TNTUN and ATTK remain delivered but unused.
The stock Tune controls pitch-envelope time, not chromatic transpose; deriving
that path is a later increment. The raw triangle also lacks the diode stage's
harmonic rounding and an antialiasing qualification.

## Independent and integration checks

[`body909.py`](../tools/x0x/body909.py) uses trigonometric triangle evaluation,
independent of the ASM integer phase folding. Host tests establish frequency,
gain/decay, onset and the odd-harmonic spectrum. Actual CPU tests compare
unshifted 24000-sample renders to this reference and each other under the
existing 1e-5 FS bound; no gain fit, normalization or alignment is allowed.

Run `mise run test` for host/C checks, `mise run test:909:body` for both actual
ASM implementations and cross-CPU comparison, and `mise run test:{dt,dn,dn2}`
separately for native installed-mod checks. The independent model is committed
in `5cb8a73`, and actual ASM/C routing in `6b3e05e`.

### Historical first fixed-Decay triangle evidence

The following measurements and hashes describe the first fixed-250 ms version,
before live Decay. Current results are recorded in the live-Decay evidence below.
At that stage, 111 host tests and all independent C/UI suites passed. Actual
24000-sample renders gave:

| Check | ColdFire | SHARC+ |
| --- | --- | --- |
| Maximum reference error | 5.243e-7 FS | 4.673e-7 FS |
| Measured frequency | 49.999997 Hz | 49.999997 Hz |
| Fitted amplitude time constant | 0.249998572 s | 0.249999278 s |
| Maximum instructions per 909 block | 711 including test wrapper | 734 |

These are historical results from the first triangle increment; the subsequent
[808 coupling stage](808-coupling.md) updates the shared callback while keeping
the 909 algorithm and comparison unchanged.

The two CPU outputs differ by at most 2.129e-7 FS. Both retain state/output,
callee/context and retrigger/interleaving guards. The combined SHARC callback
passes 4686 component calls with 914 code bytes, unchanged 320 state bytes and
overall worst 827 observed instructions.
The 808 path and its Tone/Decay comparisons remain checked by that same suite.

That historical ColdFire four-second run exposes a known fixed-point limit: the
nearest-even envelope settles at 6022 Q31 LSBs, producing a peak residual of
2.805e-6 FS. This is bounded below the existing 1e-5 FS numeric limit, not exact
tail silence. Revisit the tail policy when implementing the stock VCA/envelope;
do not infer a physical 909 noise floor from integer arithmetic.

Native installed-mod checks retain the existing 808 Tone/Decay, controls,
lock/LFO, persistence, MODEL latching and unrelated-stock-output checks.
Component passes alone do not prove those native paths or downstream audio.

| Device | First 909 native evidence | Full native regression |
| --- | --- | --- |
| DT 1.54 | 23200 raw samples at the actual C/ASM boundary match the oracle within 5.243e-7 FS; isolated post-START PCM peak 3306/32768; 123 callbacks contain nonzero 808 and 909 tracks together | 32108 callbacks complete; only deferred #78 parameter/page reset checks fail |
| DN 1.44 | 38304 raw samples and 38400 stereo PCM frames; every observed 909 block matches the oracle within 5.243e-7 FS; PCM peak 7652/32768 | 47194 callbacks pass, including 41213 nonzero 808 and 5981 nonzero 909 blocks; no violations |
| DN2 1.12 | Saved-909 T1 produces 24096 stereo PCM frames, peak 0.0201721 FS; owned phase advances exactly and amplitude gives tau 0.250000109 s | 23771 DSP frames pass the tested combined scenario, including both nonzero models, reload, stock coexistence and prior 808 controls; no halt/missing blocks. Separate late T2 MODEL transition remains open in #80 |

DT's representative p-lock check obtains its exact expected value from the
native held-step DECAY display and requires that word in the render callback,
with the saved base unchanged. It does not assume a fixed result from relative
encoder acceleration. The tested lock is raw 24064 and the base remains 16384.

DT captures are `out/dt/silent/{raw,native}-909.wav`. Its firmware SHA256 is
`df8bf16ac6521a4758b9892a8a5a9a520484e94a9b599f4ab45fa88f726f60d0`.
DN captures are `out/dn/silent/909-{raw,native}.wav`, firmware SHA256
`865055b037daa2fbe0e6c0d6578cdf0dc392796378c78af30af176ea2a63f481`.
DN2 capture is `out/dn2/silent/native-909.wav`, firmware SHA256
`d5b7c656ab0e0b58693010cf463ea8da0cd1669c5cfda77f8d75d08487c3b8e2`.
All captures retain the native level without normalization.

DN's isolated capture identifies the fresh START/physical slot before asserting
the desired model. Older 808 preview tails on the same track retain their own
latched model; they are not part of the newly triggered 909 capture. Callback
assertion failures now halt the local runner and report their evidence instead
of repeatedly stopping/re-entering the emulator without advancing time.

DN2's inspected voice buffers have already passed through stock envelope/filter
processing. They prove bounded, nonzero downstream output, not raw callback
waveform matching. Raw waveform comparison stays in the actual-ASM component
suite; native tests separately inspect owned phase/envelope state and PCM.
The isolated T1 note's early/late amplitude errors are 1.484e-7/4.364e-10 FS.

## Live-Decay evidence

`mise run test` checks the independent model and C delivery; `mise run test:909:body` checks both actual ASM backends and matching outputs at raw
0/1/16384/16385/32511/32512. Component runners additionally change Decay at
samples 4096 and 8192 without START. The shared SHARC suite retains all 808
Tone/coupling, guards, model latching and mixed-slot checks.

Native `mise run test:{dt,dn,dn2}` exercises minimum/default/maximum Decay
through actual controls in the installed mods. DT/DN compare captured raw
callback samples to the analytical model. DN also checks each delivered 909
block using that voice's integrated control history. DN2 separately checks owned
phase/amplitude and downstream PCM; generic phase-age checks cannot assume a
constant Decay history after live edits. Its explicit constant-control captures
check absolute amplitude and fitted time constant. These remain emulator tests,
not VST, real-device timing or complete stock-circuit qualification.

Current component results: 116 host tests and all isolated C/UI suites pass.
Six matching 24000-sample CPU renders have maximum continuous-model errors of
8.503e-7 FS (ColdFire) and 4.644e-7 FS (SHARC), and maximum CPU difference
5.491e-7 FS. Live control-change errors are 5.961e-7 / 3.442e-07 FS. All are below
the original 1e-5 FS limit. The shared SHARC suite passes 8820 calls, with 1084
code bytes and unchanged 448 private state bytes. Instruction counts are
informational, not acceptance limits.

The new default ColdFire four-second amplitude floor is 4380 Q31 LSBs (peak
2.040e-6 FS), still bounded rather than exact tail silence. Stock VCA/tail
behavior remains open.

## Unresolved native transition

[#80](https://github.com/simonjohansson/x0x/issues/80) tracks a separate failure:
after the long native scenario and double STOP, T2 CC45=127 followed by fresh
note76 still selects 808. Follow-up probes locate the loss above the selector:

| Probe | Stored MODEL after CC | Delivered value | Selection |
| --- | --- | --- | --- |
| Immediate post-STOP CC, diagnostic copy | 0 | START pitch76, MODEL0, flags1 | 808 |
| Extra idle pause before CC, diagnostic copy | 32512 | START pitch76, MODEL32512, flags1 | 909 |
| Original ordering plus PCM tap, unchanged production | 0 | Fresh native parameter5 remains0 | 808; bounded acknowledgement fails |

The diagnostic copy only logs into its explicitly allocated temporary 768-byte
private state area; production at that revision used 320 bytes (448 after the
later coupling increment). It is separate evidence,
not production audio qualification. Its source/firmware hashes are recorded in
`out/dn2/late-model-probe{,-immediate}/provenance.json`.

The unmodified production reproduction uses the historical canonical firmware hash above.
Its explicit failed verdict and observations are in
`out/dn2/late-model-production/{verdict,probe-observations,production-probe-report}.json`.
The original failure remains at
`out/dn2/silent/late-model-transition-failure.{json,wav}`. The earlier native
scenario's passing setup checks do not change this failed transition verdict.

The selector follows the MODEL it actually receives. Whether native control
handling drops the immediate CC or applies and then overwrites it during STOP
cleanup remains unproved; firmware/SDK/emulator responsibility is not assigned.
The extra idle pause is diagnostic evidence, not an adopted product workaround.

The successful saved-909 T1 capture does not resolve or qualify that T2 path.
Keep it open in #25/#20 and trace native CC/store handling before changing DSP
selection or adding a workaround. #9/#25/#79 also remain open for their circuit
and complete-engine gates.

VST references (#2) and physical-device testing are outside this increment.
