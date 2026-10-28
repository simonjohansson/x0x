# 808 upper-middle Decay correction

The subsequent [lower-interior duration correction](808-lower-duration.md)
keeps every upper setting below byte-identical. This document records `7716145`.

The previous qualified DSP is `e0adf4e`. Reference Decay 159, 191 and 223 fade
roughly 16–20% too quickly by cumulative-energy t99, while the default and
maximum are closer. This increment changes only the upper control curve, on
both CPUs, preserving the entire lower half and the exact maximum anchor.
Gain remains 1.601664543; pitch constants, controls, state and ABI do not change.

## Training choice

For p=(raw-16384)/16128 above the default, replace linear retention position p
with q=p+k*p*(1-p). The bounded scalar search uses k in [0,.95], preserving a
positive endpoint slope and numerical margin near maximum. All 81 training
takes at the 27 affected Tone/Decay settings contribute equally: minimize
squared log ratios of cumulative-energy t90 and t99 over the first two seconds.
The best-seen k=.9499298 is near the imposed upper bound, not proof of a unique
optimum. Full validation uses each complete 12-second take. No gain, timing,
phase or DC fit; no held-out recordings.

The ignored `out/808-upper-shape/protocol.json` records the original search.
Its extra waveform-improvement port gate conflicted with the already approved
[fidelity target](808-fidelity-target.md), which treats waveform residuals as
diagnostics. `protocol-v2.json` records this correction explicitly; neither the
objective nor any approved tolerance changes. Both protocols and all adverse
waveform results are retained.

The refined independent model gives these Tone128 duration diagnostics:

| Reference Decay | Reference t90/t99, ms | Previous | Candidate |
| --- | --- | --- | --- |
| 159 | 223.67 / 441.54 | 178.27 / 369.69 | 202.21 / 422.15 |
| 191 | 286.02 / 565.15 | 219.71 / 453.15 | 276.17 / 575.71 |
| 223 | 356.46 / 700.90 | 283.44 / 586.38 | 356.58 / 734.31 |

Retain the tradeoff: mean first-two-second raw waveform RMS on the 81 affected
takes increases .015499800→.016832042 FS (about 8.6%). At Tone128, reliable body
pitch changes -9.05→-9.02, -16.47→+2.80 and -6.23→+25.84 cents respectively;
settled pitch is unchanged. These sampled pitch results remain inside approved
limits, but are not whole-surface pitch/tone/listening acceptance. Larger
amplitude-dependent pitch movement and waveform regressions stay visible.

## Implementation and qualification

ColdFire shapes its existing Q31 upper retention coordinate; SHARC converts the
same curve back into the existing coefficient coordinate. Both reuse the
current coefficient banks. An explicit maximum bypass preserves that anchor;
no new tables, state, public contract or saved parameter is introduced.

The first frozen grid at `7c6cdf6` exposes a numerical failure at reference
Decay191 on both CPUs: maximum chain error is about 1.20e-5 FS against the
unchanged 1e-5 limit. The ordinary split model itself differs from the refined
ODE by 6.60e-6 raw FS near a Q43 threshold crossing, amplified by the fixed output
factor. This is an integration error, not evidence to retune gain or relax limits.
Those failed grids remain in `out/808-upper-shape/full-grid/`.

For the changed upper interior only, subtract the trapezoid's excess area at a
within-sample knee crossing. If a and b are the common-node distances from the
knee before/after free flow, add -a*b/(abs(a)+abs(b)) to the final clipped distance
when a*b<0. Otherwise retain the previous half-kick. This integrates a linear
crossing exactly and leaves the fine-step independent ODE unchanged. At Decay191,
the split-model error drops 6.60e-6→.79e-6 raw FS. The analytical ramp test covers
both crossing directions, same-sign and zero endpoints.

ColdFire uses its saved scratch accumulator and a bounded 31-bit fractional
divide only on a crossing. SHARC borrows existing caller-scratch index registers,
reconstructing Tone/coupling pointers before storing state. No new state/cache
word, callee-register allowance or public ABI is introduced. Preserved-register
checks caught an initial invalid use of I15; that attempt is not adopted.

## Qualified at `7716145`

202 tracked host tests and the complete guarded ColdFire body/Tone/coupling
suites pass. Focused SHARC static/live coverage runs 2,400 guarded calls plus
300 at the previously failing exact raw24320; its maximum error is 5.611e-6 FS.
Read-only pre-Tone witnesses cover 33,408 actual samples: all nine Decay positions'
first 512 samples and the changed three positions' first 9,600 samples. All remain
within .25 FS. Three independent 909 diagnostics retain byte-identical first
1,024-sample outputs. These are the relevant SHARC checks, not a rerun of its
entire older 16,392-call suite. Code is 7,176 bytes, state remains 1,664 bytes.

Fresh frozen renders cover both actual CPUs, all 81 settings / 243 training takes /
complete 12-second tails, plus seven declared-single-voice histories. All pass
the unchanged 1e-5 FS numerical limit. Grid oracle maxima are 3.988e-6 (CF) and
5.794e-6 (SHARC); peer maximum 5.834e-6. History oracle maxima are 3.237e-6 /
5.611e-6, peer 5.667e-6. Maximum synth output stays .400704205 FS, below .5 FS.

**All 54 unaffected settings and all seven histories per CPU remain byte-identical.**
Six unaffected ColdFire body streams also remain identical. The verifier checks
82 source files and 185 raw artifacts, 128 identical to `e0adf4e`, along with
source/image/runtime bindings. Accepted receipts are under the ignored
`out/808-upper-shape/qualified-grid/`; the failed initial run is separate.
Final qualification SHA256:
`7fc448553ea23661c0c4f0338411c3ba720faa38af6bbace0c61587a54afe2b9`.

### Duration and level results

At every affected setting and each separate take, both t90 and t99 improve and
meet the approved 10% or 5 ms margin. Per CPU, affected checks rise **0→162 of
162**. Mean absolute duration error falls **80.43→15.69 ms**, about 80.5%. Fresh
actual output confirms the model table above (Decay223 t99 is 734.354 ms).
Across the whole surface, duration checks rise 270→432 of 486 per CPU. The 54
remaining failures are t99 at reference Decay32 and t90 at default Decay128;
this does not qualify the entire Decay surface or held-out recordings.

Per CPU, eligible +/-2 dB level checks rise 603→690 of 945; combined 1,206→1,380
of 1,890. Settings passing every eligible level check rise 18→27 of 81.

| Level metric | Previous passes | Current passes | Eligible |
| --- | --- | --- | --- |
| Peak | 171 | 150 | 243 |
| Attack | 243 | 243 | 243 |
| Body | 135 | 216 | 243 |
| Tail/body | 54 | 81 | 216 |

The **21 new peak failures per CPU** measure +2.003 to +2.019 dB against the
unchanged 2 dB limit. They remain failures. Body/tail improvements do not cancel
them or permit a different gain per setting. The 54 quieter combined level
checks remain diagnostics; the fixed output gain remains unchanged.

### Counterevidence and remaining fidelity

All 81 affected takes improve the first-25-ms routing-corrected residual, but
regress at 6 and 150 ms. At 500 ms and the full tail, 27 improve and 54 regress;
the other 162 training takes are byte-identical. CF mean whole-tail residual
increases .004406673→.004587884 FS (about **4.1%**); SHARC has the same direction.
Uncorrected as-recorded errors regress at the changed settings in those windows.
Both routing conventions and every late-window/DC result remain in comparison.json.
This is duration/level progress with a waveform tradeoff, not an overall fidelity
percentage. Waveform improvement was not substituted for the approved targets.

Existing reliable-cycle diagnostics at the 81 affected takes stay within the
pitch limits: maximum body discrepancy grows 16.47→25.87 cents, late sigh stays
within 1.045 cents and settling within .233 cents. All 81 early-window estimates
per CPU remain unresolved. Quiet-window results do not establish audibility or
replace the still-unfrozen pitch measurement protocol.

A separate existing body-window spectrum diagnostic also regresses: the
150–1,000 Hz / 30–150 Hz power-ratio error rises on every affected take/CPU;
mean absolute error 4.91→6.87 dB, maximum 7.37 dB. The largest ratio shift is
2.353 dB. These broad bands are not the approved meaningful-harmonic protocol;
its bands/floor are still unfrozen. No harmonic/tone pass or listening acceptance
is claimed. Preserve this evidence for the next onset/body-shape and Tone work.

No fresh full-OS runs: C/UI/plumbing, saved layout, state extent, calling convention,
SDK and dependency pins are unchanged. Register/context and pointer-store guards
cover the integration scratch changes; previous device evidence remains prior.
Final native acceptance stays in #20, including its historical DN residue gate.
#79/#2 retain remaining duration/pitch/tone/listening work; #9 remains complete.
HTML, held-out recordings and unrelated working-tree edits are untouched.
