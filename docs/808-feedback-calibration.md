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
are unchanged. All 16,008 guarded callbacks pass; maximum error is 8.200e-6 FS.
All twelve stored 909 outputs remain byte identical. The original precommit
execution retains its execution revision and is explicitly source/image-bound
to committed `fb343b5`, rather than relabeled as a new execution.

## Fresh full-tail and installed-emulator qualification

Both actual CPUs freshly render all 81 settings / 243 training takes / full
12-second tails and seven declared-single-voice histories from `fb343b5`.
No prior body cache is reused. ColdFire maximum oracle error is 7.351e-6 FS;
SHARC is 8.381e-6. Maximum CPU difference is 8.537e-6 for the grid and 8.414e-6
for histories, below the unchanged 1e-5 bound. All 81 first-288-sample prefixes
and all 22 history START prefixes remain byte identical to `3c3db81`.

These are unweighted means of the per-setting RMS errors, each preserving
three separate takes; they are distinct from the original 15-take fit objective.
SHARC agrees with the following actual ColdFire results:

| Window | Previous mean RMS FS | Calibrated | Improved / regressed / unchanged |
| --- | --- | --- | --- |
| First 6 ms | .05868299 | .05868299 | 0 / 0 / 81 |
| First 25 ms | .07310327 | .07359259 | 18 / 63 / 0 |
| First 150 ms | .06475756 | .06107990 | 46 / 35 / 0 |
| First 500 ms | .04590268 | .03936188 | 49 / 32 / 0 |
| Whole 12 s | .00966089 | .00815222 | 49 / 32 / 0 |

The 500 ms regression cohort listed above also describes all whole-tail
regressions: all nine Tones at Decay 0/32/64 and the five brighter Tones at
Decay 96. First-150-ms regressions additionally include the other Decay 96
Tones except 32. All seven histories improve, by 2.83–30.07%; the musical
history changes .07348402→.06288947 FS. Those diagnostics still use the
provisional state-clearing START policy, not faithful residual-state behavior.
An independent six-setting / 18-take audit recomputes 360 before/after raw RMS
values within 1.638e-15 FS of the shared measurements. It verifies scheduled
crop, both reported gain conventions, recordings and delivered readbacks.

All three unchanged installed-emulator scenarios finish. This does **not** mean
all three full scenarios pass:

| Device | Current full-scenario result | New 808 numeric evidence |
| --- | --- | --- |
| DT | Fails only deferred #78 reset checks; 51,810 callbacks | Fresh delivered interior controls: maximum raw callback error 7.270e-6 FS |
| DN | Fails only #20 bright-Tone exact-zero baseline; 109,162 callbacks, 74 audible mixed blocks, no observer violations | Fresh interior controls: maximum raw callback error 7.281e-6 FS |
| DN2 | Pass; 40,217 audio / 40,218 DSP frames | Independent 16,000-sample post-snapshot continuation: terminal raw errors below 8.322e-9 FS, state errors below 5.100e-8 |

DN reproduces one PCM16 count throughout all sixty 100 ms baseline windows.
The prior C15 first-zero-window pass did not fix historical #20. This run adds
no new downstream-cause proof; see [the residue record](dn-silence-residue.md).
DT/DN numeric checks cover fresh raw callback waveforms. DN2 checks private
state evolution and terminal raw callback output, not samplewise equality of
stock-processed PCM. Existing controls, persistence, locks/LFOs, mixed models,
stock track and 909 regression checks retain their original scope and limits.

The accepted implementation is `fb343b5`. Broad engine/fidelity gates remain
open, including the onset and short-Decay regressions. No held-out audio,
real devices, HTML or site changes.

Reproducible local objective, sources, failed checks, optimizer trace, raw
outputs, numerical proofs and independent review are under
`out/808-q43-calibration/`. Its `sharc/final-receipt.json` binds the paired
measurements (SHA256 `36a8d6ca8ac04246f37f606b1766ed94e97b09123868735313b7c9d37a8ebc56`),
source/runtime inventories and independent audit. Native `qualification.json`
has SHA256 `8184dcbd75e4a130d13fd4ddb3be1dfe6a25afc9b3bb2cf751942618416c7323`.
Native #78 and historical #20 retain their own gates.
