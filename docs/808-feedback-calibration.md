# 808 effective feedback calibration

This #9/#79 increment calibrates the existing Q43 hard-knee feedback strength
and threshold together. It changes two internal coefficients, not the quiet
47.65 Hz pole, Decay retention map, main/C39 excitation, Tone, fixed output gain,
saved controls or START policy. These are **effective software-reference model
parameters**, not measured transistor voltages or a stock component-lot fit.
The previous qualified checkpoint is [the C15 correction](808-tone.md), `3c3db81`.

## Model and calibration

The existing source-motivated current law and exact held-source split remain:

```
leak = lambda * min(Vcomm + k, 0)
dw/dt += leak
dy/dt -= (sigma/omega) * leak
```

Here Vcomm and k use the existing encoded sample units, while lambda is in
inverse seconds. The quiet dead zone remains because k is strictly positive.
Source S03's prior was −.556 V / 1.4765e-5 A/V; its encoded parameters were
k=.0092666667 FS and lambda=859.919455/s. The calibrated values are:

| Quantity | New value |
| --- | --- |
| Positive knee magnitude k | .018011980654046803 FS |
| Feedback rate lambda | 2933.2119129807006/s |
| ColdFire knee / half-step Q31 words | 38680434 / 65614840 |
| SHARC knee / half-step float words | `0x3c938ddc` / `0x3cfa4cfe` |

`KNEE_V` and `SLOPE` remain available as equivalent parameters in the model's
voltage encoding, not as claims about the reference instrument's electronics.
The damping control still specifies the same linear retention; observed
nonlinear audio-decay fits can change and must be measured separately.

One deterministic local log-parameter fit used the original default/four-corner
training points, all three recordings each, and every scheduled sample of their
first 500 ms. Its objective was unweighted raw squared error with the existing
documented reference multiplier ×4. No output gain, DC offset, phase, onset,
delay or per-setting parameter was fitted. The prior-centred parameter box was
1/8..8 for each coefficient; existing .25 FS body / .5 FS composed bounds and
all numeric guards remained. No held-out audio was read.

The single real run used 119 evaluations / 23 iterations and reduced its
fast-model objective from 1336.96975 to 640.77481. Its Jacobian has rank two,
condition 17.80 and inactive constraints. **It is a best-seen local candidate,
not a proved stationary or global optimum:** the solver reports a small-step
stop without stationarity and `converged=false`. Independent review preserves
that distinction. Known synthetic recovery and all target/readback/hash checks
passed. Report-only JSON preparation failures happened before real residual
evaluation and remain preserved; there was no numerical restart or refit.

## Bounded training screen

The independent refined-model screen uses all 81 settings / 243 individual
takes, first 500 ms, versus actual `3c3db81` ColdFire output. It retains raw
timing/gain, every repetition and all regressions:

| Window | Previous mean RMS FS | Candidate | Settings improved / regressed |
| --- | --- | --- | --- |
| First 25 ms | .07310327 | .07359256 | 18 / 63 |
| First 150 ms | .06475756 | .06107995 | 46 / 35 |
| 150–500 ms | .03111996 | .02216465 | 63 / 18 |
| First 500 ms | .04590268 | .03936186 | 49 / 32 |

All Tone positions regress at Decay 0/32/64 over 500 ms. At Decay 96,
Tone 128/159/191/223/255 also regress. The worst 500 ms regression is about
.000591 FS at Tone 128 / Decay 32. First-150-ms regressions additionally include
every Decay 96 Tone except 32. The first 25 ms therefore remains a material
unfinished onset/trajectory gate, even though the longer mean improves.

At Tone 128 / maximum Decay, 150–300 ms pitch changes 49.72196→47.65170 Hz
against 47.77887 Hz recorded. The quiet pole is unchanged; this is a large
late-pitch improvement, not an exact trajectory match. The first 288 host
samples are bit-identical; tiny screen differences against prior actual CF
there are quantization differences, not a changed attack model.

## Numeric and integration gates

Four-to-eight RK4 refinement failed the unchanged 1e-7 FS guard at two high
Decay settings. Increasing only oracle precision to eight substeps passes
eight-to-sixteen refinement at every grid Decay (maximum 2.925e-8 FS). The actual
CPU split candidate stays within 2.414e-6 FS of the refined independent ODE.
Both fresh-render and native-snapshot continuation oracles use eight substeps.
No tolerance, coefficient, data window or optimizer objective was changed to
hide the failed coarse-oracle check.

191 tracked host tests and seven compiled C/UI checks pass. The guarded
ColdFire body suite passes (maximum 7.365e-6 FS), as does composed Tone/C47
(maximum 2.333e-6). Eight additional guarded controls around the largest observed
interpolation error pass: maximum 7.939e-6 FS, unchanged 1e-5 limit. All twelve actual
body and five composed first-288-sample prefixes match the previous checkpoint.

The SHARC port changes only four immediate loads; decoded instruction forms,
addresses, code size (5,804 bytes), private state (1,664 bytes), SDK and ABI
are unchanged. Its full guarded suite, fresh full-tail paired CPU/reference
grid/history comparison and all three native scenarios are still in progress.
The model screen above is not new full-tail/native qualification, and broad
engine/fidelity gates remain open. No real devices or HTML/site changes.

Reproducible local objective, sources, failed checks, optimizer trace, raw
outputs, numerical proofs and independent review are under
`out/808-q43-calibration/`. Native #78 and historical #20 retain their own gates.
