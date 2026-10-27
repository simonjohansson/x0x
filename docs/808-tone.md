# 808 passive Tone stage

TNTUN now filters the provisional 808 body on DT, DN and DN2. This is one
source-derived circuit stage in [#9](https://github.com/simonjohansson/x0x/issues/9)
and [#79](https://github.com/simonjohansson/x0x/issues/79), not a claim that the
whole engine is a faithful 808. The saved controls, IDs and MODEL policy are
unchanged. ATTK remains ignored for 808; 909 still renders silence.

## Circuit and control mapping

The original Roland schematic S01 p.9 and Werner/Abel/Smith S03 §9, Table1 and
Eq.11 give R171=220 Ω, R172=10 kΩ, VR5=10 kΩ and C45=0.1 µF. Source URLs,
archive paths and hashes are in [the research manifest](../research/manifest.json).
The selected network is

`Req = 220 + 10000*l/(1+l)` and `H(s) = 1/(1+s*Req*1e-7)`.

The current native mapping is explicitly provisional: `l=1-tone_raw/32512`.
Higher TNTUN is brighter. Tone 0 gives 5220 Ω and 304.895 Hz; Tone 127 gives
220 Ω and 7234.316 Hz. This resistance-linear mapping is not the schematic's
calibrated C-taper potentiometer, nor a verified stock knob direction. Default
64 lies around 450 Hz. Deriving the physical taper remains in #79.

Coefficients update once per delivered 32-sample block. DT forwards native raw
Tone, DN uses the existing bounded exact-position numerator, and DN2 reads
parameter 0 directly in the SHARC callback. Live edits retain filter/body state.
Native smoothing, p-locks and LFO delivery use these same inputs.

## Independent model and assembly

At 48 kHz the bilinear RC coefficient is

`G = 1/(1+2*48000*Req*1e-7) = (2-t)/(102.224-99.112*t)`, `t=raw/32512`.

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

The [SHARC callback](../targets/sharc/body808.s) keeps its first 128 metadata
bytes and next 128 body bytes, then adds sixteen float Tone states at offset
256: 320 total private state bytes. A positive-float reciprocal estimate with
four Newton refinements computes G without relying on an unmodeled RECIPS seed.
The combined callback is 764 code bytes and at most 827 instructions under the
unchanged 1000-instruction test bound. Its 3934 component callbacks retain
output/state guards, context preservation, invalid-frame atomicity and 909 silence.

Every current prototype START clears the selected Tone history alongside the
existing body restart. A live control edit without START does not. In particular,
the DN2 SDK exposes physical slot identity, not logical track ownership, and
does not clear author RAM when that slot returns from stock use. Carrying a
new capacitor history across START would therefore risk an unrelated old
owner's charge. Residual circuit-state retrigger behavior and logical ownership
qualification remain in #9/#20/#79; no SDK transport or saved format was added.

## Verification

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
