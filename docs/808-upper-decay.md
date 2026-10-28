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

Initial checks: 200 tracked host tests and the guarded ColdFire body suite pass,
including raw20480/24576/28672 and existing fractional/end-point cases. Fresh
SHARC static/live guards and frozen full-grid CPU/reference qualification are
pending. This is a candidate checkpoint, not completed fidelity acceptance.
#79/#2 retain remaining duration/pitch/tone/listening work; #9 remains complete.
HTML, held-out recordings and unrelated working-tree edits are untouched.
