# 808 upper-middle Decay correction

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

202 tracked host tests and the guarded ColdFire body suite pass. A focused actual
SHARC Decay191 regression now agrees within 1.964e-6 FS. Final static/live guards
and fresh frozen full-grid CPU/reference qualification are pending. This is a
candidate checkpoint, not completed fidelity acceptance.
#79/#2 retain remaining duration/pitch/tone/listening work; #9 remains complete.
HTML, held-out recordings and unrelated working-tree edits are untouched.
