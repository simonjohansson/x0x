# Replacement 808 from the fresh corpus

[Parent #82](https://github.com/simonjohansson/x0x/issues/82) owns this work. The complete implementation plan and its 12 native sub-issues are recorded there. The final mod must provide per-voice 808/909 coexistence on Digitakt, Digitone and Digitone II. Private state, ASM and adapters may be rewritten; the present 909 implementation is optional during development.

## Current status

28 October 2026: [#83](https://github.com/simonjohansson/x0x/issues/83) is complete in commit `972d30c`. The first two compact-generator capacity experiments under [#84](https://github.com/simonjohansson/x0x/issues/84) are implemented and fail the frozen accuracy gates. That issue remains open; global fitting and assembly wait for a viable candidate. Production DSP has not changed. Evidence here is host evidence only.

The original capture and model files remain local under `research/reference/808-fit-model/`. Audio and model binaries are not committed. Tracked inputs are [protocol.json](../tests/fixtures/808-model/protocol.json) and [events.csv](../tests/fixtures/808-model/events.csv); the independent driver is [fit808.py](../tools/x0x/fit808.py).

## Frozen reference boundary

- WAV SHA256: `6b2ab6eb4e69582864366bc3baea4ebf340dcbc34b4e6d99267e56ad5366faf6`. Roland TR-808 VST3 1.1.4 build 22074; 48 kHz stereo float32, sample-identical channels. Global plugin quality remains unverified.
- There are 512 complete scheduled 264,000-frame slots, 480 distinct control pairs. Start sample is `48000 + index * 264000`; parameter changes precede it by 12,000 samples. The observed one-sample onset stays in place. No normalization, gain fitting, DC subtraction, resampling or alignment is allowed.
- Duplicate settings share one partition: 193 fitting settings (211 takes), 144 validation settings (152 takes), 143 test settings (149 takes). First occurrences supply fitting targets. Validation selects complexity; the original test is a retrospective benchmark. Final independent acceptance needs fresh captures under #90.
- `target_DSP = 4 * captured_WAV`; scoring converts DSP output back with `0.25 * DSP_output`. This removes the documented REAPER attenuation, rather than estimating a gain. Fixed source velocity 100 is already embedded. Device adapters must verify unity downstream AMP/velocity/track gain or independently characterize that processing under #91–#93; native unity is not yet measured.
- Native integer anchors `CC*256` map to `floor(CC*255/127 + 0.5)/255`. Fractional native values interpolate continuously between adjacent anchors, including the three-step jump between CC 63 and 64.
- Measurements use the raw capture gain. Every setting has equal weight; duplicate-take metrics are averaged within a setting. Absolute level/duration errors are averaged as absolute values to avoid cancellation. All per-take metrics remain in the receipts. Quiet-window residual limits apply to every take.

The compact generator and each final CPU must meet these frozen gates, separately for all settings and interactions:

| Metric | Gate |
| --- | --- |
| Whole-slot relative L2 | Median ≤0.1%, p95 ≤0.75%, worst ≤1.5% |
| Each of 0–6, 6–50, 0–50 and 50–500 ms | Active-window p95 ≤1%, worst ≤3% |
| Absolute peak / energy / t99 error | ≤0.1 dB / ≤1% / ≤1.5 ms |
| Quiet window, reference RMS <1e-5 FS | Residual RMS ≤1e-6 FS and maximum ≤1e-5 FS |

Relative L2 is `sqrt(sum((prediction-reference)^2)/sum(reference^2))`. Percentiles use NumPy's linear method. t99 is the first sample whose cumulative squared amplitude reaches 99% of full-slot energy. Tail relative errors from 500 ms onward are diagnostic; quiet residual floors still apply. Passing numerical gates alone does not establish audible equivalence.

## Reproduce

```sh
mise run test:808:model
```

This runs synthetic/trust-boundary tests, verifies 121 distinct local artifacts against the frozen hashes and original checksum lists, audits all 512 audio slots, then independently reconstructs the fitting-only teacher for both held-out partitions. It never retrains the teacher or imports the ignored fitting script. Receipts go to `out/808-model/protocol-benchmark.json` and `protocol-validation.json`, with source/driver/protocol hashes, per-take measurements and gate outcomes.

The command succeeds when tests, integrity checks and reproduction pass. Teacher acceptance against the proposed compact-model gates is reported separately in `summary.*.passes_gates`; a reproduced teacher can fail those gates. The all-data `model.npz` is verified for provenance but is not used to predict either reserved partition.

## Reproduced baseline, 28 October 2026

| Partition / population | Settings | Median L2 | p95 L2 | Worst L2 |
| --- | ---: | ---: | ---: | ---: |
| Test / all | 143 | 0.0160384% | 0.2322079% | 0.7417315% |
| Test / both knobs nonzero | 81 | 0.0783593% | 0.4279796% | 0.7417315% |
| Validation / all | 144 | 0.0084934% | 0.5709090% | 0.8462339% |
| Validation / both knobs nonzero | 80 | 0.0528111% | 0.7168496% | 0.8462339% |

These reproduce the saved teacher's reported whole-waveform scores within 1e-8 absolute relative L2. The teacher passes all proposed gates on the test partition. It **fails the validation 50–500 ms p95 gate**: 1.7205% over all settings and 2.1864% over interactions, against the frozen 1% limit; worst is 2.5893%. The other validation gates pass. This remains a failure to improve on or explicitly reconsider during architecture selection, not an implicit threshold adjustment.

No compact-model, assembled-instruction, native-emulator, physical-device or listening acceptance is claimed by this baseline.

Validation: `mise run test:808:model` passes all 14 focused tests and both benchmark reproductions. The broader `mise run test:host` run reported 241 tests, three failures and four skips. All three failures are in the pre-existing, untracked `test_feedback808.py` (physical KCL/current and refinement comparisons); that file and its old-model implementation were not changed by this increment. This does not establish a green repository-wide suite.

## Initial compact-generator capacity (#84)

The [predeclared subset](../tests/fixtures/808-model/capacity.json) contains 16 distinct fitting-only pairs spanning corners, isolated axes, low/mid/high Decay and the interior. Neither reserved partition supplies optimization targets. Each pair is optimized separately to test generator capacity; these coefficients are not a shipping per-setting lookup.

The first candidate shares one phase trajectory between two complex exponential envelopes, with a decaying nonoscillatory transient:

```text
phase(t) = 2π[f0*t + df1*tau1*(1-exp(-t/tau1)) + df2*tau2*(1-exp(-t/tau2))]
y(t) = exp(-t/slow)*(a*sin(phase)+b*cos(phase))
     + exp(-t/fast)*(c*sin(phase)+d*cos(phase)) + e*exp(-t/dc_tau)
```

The second candidate adds `(h*sin(2*phase)+j*cos(2*phase))*exp(-t/harmonic_tau)`. Time constants are positive, with ordered pitch/envelope pairs. [SciPy bounded least squares](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.least_squares.html), pinned at 1.18.0, optimizes 8/9 nonlinear parameters; linear least squares solves 5/7 amplitudes at every evaluation. Three deterministic starts, a 400-evaluation bound per start, optimality, termination, active bounds, conditioning and amplitude feasibility are recorded. Nonconvergence is retained as a failure, not assumed successful.

The objective approximates full-slot relative squared error plus 0.25 times each active short-window relative squared error. Deterministic quadrature keeps every first-6-ms sample, then uses strides 4/16/128 over 6–50/50–500/500–5500 ms. These are loss weights; reference samples and output gain/timing are unchanged. Every final prediction is evaluated at all 264,000 samples through the frozen driver.

| Candidate / fitting population | Median L2 | p95 L2 | Worst L2 |
| --- | ---: | ---: | ---: |
| Fundamental / all 16 | 10.4780% | 12.7803% | 14.0248% |
| Fundamental + harmonic / all 16 | 5.3342% | 9.3878% | 11.1348% |
| Fundamental / 8 interactions | 9.4639% | 12.1675% | 12.3655% |
| Fundamental + harmonic / 8 interactions | 5.2645% | 7.8620% | 8.8055% |

Both candidates fail waveform/window gates, including the 50–500 ms body; the problem is not confined to the onset. Fundamental residual analysis at long Decay found 76.6–82.2% of Hann-windowed 50–500 ms residual spectral energy in 75–125 Hz at the two Tone extremes, supporting the added harmonic trial. Short-Decay residuals also contain a slow/nonoscillatory component. The best fundamental runs at `(17,0)` and `(68,0)`, and the best harmonic run at `(0,0)`, exhausted the evaluation bound. Other fits converge, but convergence does not imply acceptance or a global optimum.

Decision: **keep #84 open and do not start #85 or ASM**. Investigate constrained bounds/initialization and an effective output/envelope process before selecting another compact topology. The errors extend into the body, so a tiny onset-only residual is not yet justified. This bounded experiment rejects these fitted candidates; it does not prove that every small procedural model is inadequate. Gates and resource reservations remain unchanged.

Provisional parameter-plus-state storage is 96/112 bytes per voice, counting all float32 parameters, 7/8 recurrence states and 16 common bytes. This is an estimate, not a linked footprint. The closed-form host evaluators perform 5/6 exp/expm1 and 2/4 sin/cos evaluations per sample; those are not proposed target sample loops. Global coefficient-table size, recursive approximations, fixed-point feasibility and actual ASM cost are still unproved. Those resource/accuracy checks remain part of #84–#86.

Reproduce both experiments and their five synthetic/equation tests with:

```sh
mise run research:808:capacity
```

Reports, fitted parameters, all multistart diagnostics, full-length prediction WAVs and residual WAVs are written under `out/808-model/capacity/{fundamental,harmonic}/`. Reports include source, driver, subset and protocol hashes. SciPy 1.18.0 must be available in the uv cache; the research tasks run offline after initial dependency installation.
