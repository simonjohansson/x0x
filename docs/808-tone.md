# 808 passive Tone stage

Current whole-engine qualification follows the
[reference-calibrated Tone shape at `f59f129`](808-tone-shape.md), after the
[Q43 calibration](808-feedback-calibration.md). The nominal C15 curve below
is historical; its topology/endpoints remain, but the interior mapping changes.
Native DN currently passes one zero window; historical #20 remains unresolved.

The measurements below predate [finite rectangular excitation](808-excitation.md).
The RC topology is unchanged. The control taper is now corrected as described
below; older component/native numbers remain historical evidence.

TNTUN now filters the provisional 808 body on DT, DN and DN2. This is one
source-derived circuit stage in [#9](https://github.com/simonjohansson/x0x/issues/9)
and [#79](https://github.com/simonjohansson/x0x/issues/79), not a claim that the
whole engine is a faithful 808. The saved controls, IDs and MODEL policy are
unchanged. ATTK remains ignored for 808. The subsequent
[909 triangle increment](909-body.md) replaces the previously silent branch.

## Circuit and control mapping

The original Roland schematic S01 p.9 and Werner/Abel/Smith S03 §9, Table1 and
Eq.11 give R171=220 Ω, R172=10 kΩ, VR5=10 kΩ and C45=0.1 µF. Source URLs,
archive paths and hashes are in [the research manifest](../research/manifest.json).
The selected network is

`Req = 220 + 10000*l/(1+l)` and `H(s) = 1/(1+s*Req*1e-7)`.

S01 p.16 identifies the original part as EVH-LWAD25C14, Roland 13219313,
10 kΩ(C). The p.9 wiring uses R23: increasing brightness reduces resistance
from 10 kΩ toward zero. A modern Panasonic C-taper specification places R23
at about 15% halfway through travel ([S49, pp.1–2](../research/manifest-components.json)); it does not establish the exact vintage
track. Use a bounded rational approximation to that nominal midpoint:

`t=tone_raw/32512`, `l=(1-t)/(1+(14/3)*t)`.

Higher TNTUN is brighter. Both endpoint resistances/cutoffs remain 5220 Ω /
304.895 Hz and 220 Ω / 7234.316 Hz. Approved default64 now gives 1509.22 Ω /
1054.55 Hz, versus the previous linear mapping's 3535.79 Ω / 450.13 Hz.
The precise curve remains provisional; this is not an exact vintage-pot model.

Coefficients update once per delivered 32-sample block. DT forwards native raw
Tone, DN uses the existing bounded exact-position numerator, and DN2 reads
parameter 0 directly in the SHARC callback. Live edits retain filter/body state.
Native smoothing, p-locks and LFO delivery use these same inputs.

## Independent model and assembly

At 48 kHz the bilinear RC coefficient is

`G = 1/(1+2*48000*Req*1e-7) = (750+1375*t)/(38334-31721*t)`,
`t=raw/32512`.

Both ASM implementations use the TPT recurrence `v=G*(x-s)`, `y=s+v`,
`s=y+v`. The capacitor-history state is owned by one voice. The independent
[`tone808.py`](../tools/x0x/tone808.py) reference instead integrates capacitor
voltage and current with the trapezoidal rule. Host tests compare its step and
1 kHz response to closed-form transfer equations; direct CPU tests use impulse,
step, rich input, endpoints/fractional words and live changes.

The shared [ColdFire filter](../targets/coldfire/tone808.s) runs in-place after
the unchanged body routine. Its coefficient uses bounded unsigned division;
EMAC forms `G*x-G*s` before extraction so opposite full-scale input/history
cannot overflow an intermediate subtraction. It preserves EMAC, callee registers
and stack guards. It adds 232 code bytes, 76 stack bytes and 4 state bytes per
voice; the direct test counts at most 712 instructions including its wrapper.
The isolated rich-input maximum error is 1.118e-8 FS and coefficient error is
below two Q31 LSBs.

At the Tone increment, the [SHARC callback](../targets/sharc/body808.s) kept its first 128 metadata
bytes and next 128 body bytes, then adds sixteen float Tone states at offset
256: 320 total private state bytes. The later [coupling stage](808-coupling.md)
extends this to 448 bytes without moving those banks. A positive-float reciprocal estimate with
four Newton refinements computes G without relying on an unmodeled RECIPS seed.
At the Tone increment `58d0d55`, the combined callback was 764 code bytes and at
most 827 observed instructions. Its 3934
component callbacks retained output/state guards, context preservation,
invalid-frame atomicity and then-unimplemented 909 silence. Current combined
callback costs/results are recorded in [909-body.md](909-body.md).

Every current prototype START clears the selected Tone history alongside the
existing body restart. A live control edit without START does not. In particular,
the DN2 SDK exposes physical slot identity, not logical track ownership, and
does not clear author RAM when that slot returns from stock use. Carrying a
new capacitor history across START would therefore risk an unrelated old
owner's charge. Residual circuit-state retrigger behavior and logical ownership
qualification remain in #9/#20/#79; no SDK transport or saved format was added.

## Verification

The current correction is motivated independently of the body mismatch.
Same-Decay reference Tone pairs identify a default effective resistance around
1503 Ω, versus the old 3536 Ω; the dark endpoint remains near 5220 Ω. All nine
Decay settings and all three repetitions support the interior brightness
correction. Pair identification fits RC relationships with no output-gain or
delay parameter; it does not establish absolute physical resistance inside
the software reference. A fixed nominal 15% rational curve follows the observed
direction without fitting nine lookup-table knots. It still misses some of
the reference's finer control shape.

On that isolated Tone-pair diagnostic, the fixed curve improves every one of
the 189 interior takes in all four 6/25/150/500 ms windows; the endpoint laws
are unchanged. Interior mean 500 ms pair error falls .00555992→.00052224 FS.
This control-specific evidence is separate from absolute engine-waveform error.

The model-only 81-setting / 243-take / first-500-ms screen preserves raw timing,
output gain, repetitions and the documented reference multiplier ×4. Mean raw
error improves .0617813→.0586830 FS at 6 ms, .0744283→.0731033 at 25 ms,
.0656949→.0647576 at 150 ms and .0460243→.0459027 at 500 ms. **Nineteen
interior settings regress at 500 ms**, including every Tone223 setting and
several Tone159/191 settings. Default peak moves .232411→.240234 FS toward
the reference's .308554 FS. Body/pitch, Decay, gain, saved controls and lifecycle
are unchanged; this does not fix the continuing Q43 pitch error.

191 tracked host tests and seven compiled C/UI checks pass. Guarded ColdFire
Tone and composed Tone/C47 suites pass, with maximum composed error 3.6234e-6 FS
under the unchanged 1e-5 limit; both endpoint outputs remain byte-identical.
The full guarded SHARC suite also passes: 16,008 callbacks, maximum error
3.62084e-6 FS, 5,804 code bytes and unchanged 1,664 private-state bytes. All
twelve stored 909/reference outputs remain byte-identical. Dark Tone is
byte-identical; bright changes at most 4.47035e-8 FS from coefficient rounding.
The original precommit component runs are hash-bound to `3c3db81`, with their
original execution provenance retained.

Fresh actual ColdFire Tone/C47 renders at all 81 settings retain full 12-second
tails and the unchanged 1e-5 FS gate (maximum error 3.62620e-6 FS). Unchanged
body execution is reused only after complete source/kernel/cache identity
checks; it is not relabelled a fresh body run. All eighteen endpoint outputs
remain byte-identical and seven fresh declared-voice histories are rendered.
Fresh committed SHARC execution also passes all 81 full tails and seven
histories (maximum oracle error 3.98754e-6 FS). Grid peer error is at most
5.22566e-6 FS; history peer error is at most 5.15674e-6 FS. Every original
1e-5 FS numeric gate remains unchanged. Only nine dark endpoints are bit-identical
on SHARC; its bright endpoints retain the documented rounding differences.

The paired comparison covers all 243 training recordings, full 12-second tails
and seven separate declared-voice histories. ColdFire mean error against the
documented reference ×4 changes as follows:

| Window | Before, FS | C15, FS | Interior settings improved / regressed |
| --- | --- | --- | --- |
| First 150 ms | .06569488 | .06475756 | 56 / 7 |
| First 500 ms | .04602430 | .04590268 | 44 / 19 |
| Whole 12 s | .00967961 | .00966089 | 36 / 27 |

This is a 1.4268% mean first-150-ms reduction and .1935% whole-tail reduction,
not a timbre-acceptance score. All seven early regressions are retained:
Tone191 at Decay0/32 and Tone223 at Decay0/32/64/96/128. The **27 whole-tail
regressions** are:

| Tone display | Decay displays |
| --- | --- |
| 32 | 255 |
| 64 | 255 |
| 96 | 223, 255 |
| 128 | 223, 255 |
| 159 | 128, 159, 191, 223, 255 |
| 191 | 0, 32, 128, 159, 191, 223, 255 |
| 223 | 0, 32, 64, 96, 128, 159, 191, 223, 255 |

Five histories improve. Both 500 ms-gap pairs regress: default Decay
.01130335→.01130618 FS (+.0251%), maximum .03083395→.03087979 (+.1487%).
These retain 32-sample delivered timing, including the musical sequence's
16-sample scheduling difference; they do not qualify native allocator ownership
or retained-charge retrigger. As-recorded residuals, every repetition and tiny
SHARC endpoint differences remain in the measurements. An independent direct
recomputation of eighteen takes/six settings at five windows and both gain
scales agrees within 1.052e-15 FS.

Installed DT and DN scenarios complete with the new interior Tone response.
DT retains only #78 resets. DN passes its current run; its silence checker exits
after the first exact-zero 100 ms window, so this is not sixty-window stability
or a fix for historical #20. DN2 passes its full native scenario: 40,217 audio /
40,218 DSP frames, unchanged normal daemon, no halt/missing blocks/controller
errors, and both new interior responses. Its 16,000-sample continuation errors
are 4.310e-10 / 3.063e-8 FS; this snapshot proof is separate from fresh
full-wave component execution. All existing stock, mixed-model, 909, lock, LFO,
reload and endpoint checks remain. No observer, wait or tolerance was changed.
The initial model screen above remains separate from these native results. Source images,
RC identification and screen receipts are under `out/808-tone-taper/` and
`out/808-tone-identification/`; new CPU results are under `out/808-tone-c15/`.
No held-out audio, fitted gain/alignment, physical device or website is used.

Final receipts: `out/808-tone-c15/full-grid/measurements.json`,
`full-grid/history/measurements.json`, `sharc/paired-summary.json`,
`full-grid/independent-selected-comparison.json` and `native/qualification.json`.
The Tone implementation is `3c3db81`; the later feedback correction linked
above improves continuing pitch while retaining broader #9/#79/#2 fidelity gates.

The numerical/native results below are from the completed Tone increment,
before 909 sound and coupling were added. [808-coupling.md](808-coupling.md)
records the current chain while retaining these 808 checks.

Run `mise run test` for host/C checks and `mise run test:808:body` for actual
ColdFire body, ColdFire Tone, combined SHARC body/Tone and cross-CPU comparison.
Matching unshifted composed renders use the unchanged 1e-5 FS error limit,
without normalization or gain fitting:

| Decay raw | Tone raw | Samples compared | ColdFire/reference | SHARC/reference | CPU difference |
| --- | --- | --- | --- | --- | --- |
| 0 | 16384 | 24000 | 5.227e-8 | 3.276e-7 | 3.237e-7 |
| 16384 | 16384 | 24000 | 3.386e-7 | 5.626e-7 | 3.088e-7 |
| 32512 | 16384 | 24000 | 5.302e-7 | 8.246e-7 | 6.413e-7 |
| 16384 | 0 | 8192 | 2.993e-7 | 5.221e-7 | 3.404e-7 |
| 16384 | 32512 | 8192 | 3.052e-7 | 5.326e-7 | 3.032e-7 |

The native runners also select Tone endpoints through the installed mod, observe
actual DSP input/state and capture downstream PCM. These are emulator checks;
the direct CPU comparisons above omit each device's native downstream gain,
filters and effects. Captures are unnormalized.

| Device | Native Tone evidence | Full native regression |
| --- | --- | --- |
| DT 1.54 | Exact Tone 0/32512 at actual ASM, Decay 16384; settled raw endpoint difference 0.038125 FS; nonzero downstream PCM | 31388 callbacks; only deferred #78 parameter/page reset checks fail |
| DN 1.44 | Exact Tone 0/32512 at actual ASM, Decay 16384; identical dry-body windows and filtered endpoint difference 0.038125 FS; nonzero downstream PCM | 19024 callbacks pass, including 14256 nonzero 808 and 4768 silent 909 blocks |
| DN2 1.12 | Exact Tone 0/32512 and Decay 16384; actual settled Tone history agrees with the independently predicted body/RC response within 1.160e-8/5.017e-9 FS; native PCM peaks 0.021404/0.021737 FS | 19927 DSP frames pass; controls, locks/LFO, project reload and stock coexistence retained; no halt/missing blocks |

DT captures are `out/dt/silent/tone-{dark,bright}-{raw,native}.wav`; DN captures
are `out/dn/silent/808-tone-{dark,bright}-{raw,native}.wav`; DN2 captures are
`out/dn2/silent/tone-{dark,bright}-native.wav`. Current reports live beside them.
DT/DN comparisons exclude the initial settling window; rich diagnostic inputs
in the component suite test the filter far beyond this nearly pure 55 Hz body.

The native firmware SHA256 values for these runs are:

- DT: `198c2e2c8957c3efcf103d1ae3ccdb8fddf490270e41ccca5346438100206786`.
- DN: `6a4b478cafa760a44b40cb1eccb6e9da8137e38aadc93c78a680b1facf50adfb`.
- DN2: `353ba8a42f3fe63995e99b2fcf6611b75c1fee715d68388d075399c6e994ab09`.

The raw body, Decay curve, excitation/retrigger and internal scale remain
provisional. The [alignment inventory](reference-alignment.md) keeps missing
circuit stages explicit. VST work in #2 and physical-device testing remain
outside this increment.
