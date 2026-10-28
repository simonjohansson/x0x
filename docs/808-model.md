# Replacement 808 from the fresh corpus

[Parent #82](https://github.com/simonjohansson/x0x/issues/82) owns this work. The complete implementation plan and its 12 native sub-issues are recorded there. The final mod must provide per-voice 808/909 coexistence on Digitakt, Digitone and Digitone II. Private state, ASM and adapters may be rewritten; the present 909 implementation is optional during development.

## Current status

28 October 2026: [#83](https://github.com/simonjohansson/x0x/issues/83) is complete in commit `972d30c`. [#84](https://github.com/simonjohansson/x0x/issues/84) now includes controlled optimizer diagnosis, a zero-start candidate with two real output decays, and a blind listening report for the fixed 16-setting fitting subset. Human listening acceptance remains pending. Production DSP has not changed. Evidence here is host evidence only.

The user clarified the acceptance priority during #84: **audible fidelity, rather than exact waveform reproduction**. The original source-error thresholds below remain measured diagnostics; exceeding them no longer automatically rejects a candidate if listening establishes an acceptable result. A 5% error does not itself establish inaudibility. Numerical realization, memory/context safety, gain/timing, independent control validation and native/physical qualification remain necessary.

The original capture and model files remain local under `research/reference/808-fit-model/`. Audio and model binaries are not committed. Tracked inputs are [protocol.json](../tests/fixtures/808-model/protocol.json) and [events.csv](../tests/fixtures/808-model/events.csv); the independent driver is [fit808.py](../tools/x0x/fit808.py).

## Frozen reference boundary

- WAV SHA256: `6b2ab6eb4e69582864366bc3baea4ebf340dcbc34b4e6d99267e56ad5366faf6`. Roland TR-808 VST3 1.1.4 build 22074; 48 kHz stereo float32, sample-identical channels. Global plugin quality remains unverified.
- There are 512 complete scheduled 264,000-frame slots, 480 distinct control pairs. Start sample is `48000 + index * 264000`; parameter changes precede it by 12,000 samples. The observed one-sample onset stays in place. No normalization, gain fitting, DC subtraction, resampling or alignment is allowed.
- Duplicate settings share one partition: 193 fitting settings (211 takes), 144 validation settings (152 takes), 143 test settings (149 takes). First occurrences supply fitting targets. Validation selects complexity; the original test is a retrospective benchmark. Final independent acceptance needs fresh captures under #90.
- `target_DSP = 4 * captured_WAV`; scoring converts DSP output back with `0.25 * DSP_output`. This removes the documented REAPER attenuation, rather than estimating a gain. Fixed source velocity 100 is already embedded. Device adapters must verify unity downstream AMP/velocity/track gain or independently characterize that processing under #91–#93; native unity is not yet measured.
- Native integer anchors `CC*256` map to `floor(CC*255/127 + 0.5)/255`. Fractional native values interpolate continuously between adjacent anchors, including the three-step jump between CC 63 and 64.
- Measurements use the raw capture gain. Every setting has equal weight; duplicate-take metrics are averaged within a setting. Absolute level/duration errors are averaged as absolute values to avoid cancellation. All per-take metrics remain in the receipts. Quiet-window residual limits apply to every take.

The original source-error targets, retained as diagnostics after that clarification, are reported separately for all settings and interactions:

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

Historical decision after the first capacity trial: keep #84 open and investigate constrained bounds/initialization and an effective output/envelope process before selecting another compact topology. This bounded experiment failed the original numeric targets; it did not prove that every small procedural model is inadequate. The subsequent audible-fidelity priority and current candidate are described below. Resource reservations remain unchanged.

Provisional parameter-plus-state storage is 96/112 bytes per voice, counting all float32 parameters, 7/8 recurrence states and 16 common bytes. This is an estimate, not a linked footprint. The closed-form host evaluators perform 5/6 exp/expm1 and 2/4 sin/cos evaluations per sample; those are not proposed target sample loops. Global coefficient-table size, recursive approximations, fixed-point feasibility and actual ASM cost are still unproved. Those resource/accuracy checks remain part of #84–#86.

Reproduce both experiments and their five synthetic/equation tests with:

```sh
mise run research:808:capacity
```

Reports, fitted parameters, all multistart diagnostics, full-length prediction WAVs and residual WAVs are written under `out/808-model/capacity/{fundamental,harmonic}/`. Reports include source, driver, subset and protocol hashes. SciPy 1.18.0 must be available in the uv cache; the research tasks run offline after initial dependency installation.

## Controlled diagnosis and listening candidate (#84)

Use [diagnose808.py](../tools/x0x/diagnose808.py) with the same immutable corpus and 16-setting subset:

```sh
mise run research:808:diagnose
```

This requires the matching `research:808:capacity` baseline. It verifies the original 121 artifacts and retains source, protocol, subset, baseline and both driver hashes. Outputs are local under `out/808-model/diagnosis/`: `report.json`, four-corner plots, full-length prediction/residual WAVs, and a self-contained audio comparison in `index.html`. The chart and JSON remain adjacent files; WAV stimuli are embedded in the HTML, so playback needs no server. The controller's JavaScript checks use Node through mise.

The controlled restart preserves the original equations. It uses the previous best solution plus three starts initialized from measured same-polarity peak periods, increases the evaluation budget to 800, and extends the output-decay ceiling from 30 ms to one second because the old ceiling was active at a long-Decay corner. These are changes to fitting bounds and initialization, not to reference samples or metric thresholds. Converged, conditioned solutions with actual amplitudes ≤0.25 capture FS are preferred; every start and its bounds are retained.

All four corners then receive a full-rate, 264,000-sample objective polish, limited to 60 evaluations. The quadrature objective differs from its exact full-rate value by only 0.089–0.370% for the control. Full-rate polishing reduces that exact objective by only 0.0008–0.0045%. Thus the sampled objective is not the main explanation for the remaining error. All 16 selected fits converge and meet the prototype's numerical checks.

The new candidate adds one slower real decay `tau2 = tau1 + exp(gap)` to address the slow/nonoscillatory residual. It also constrains the output to start at zero by eliminating one linear amplitude: the sum of the cosine and real-mode amplitudes at time zero is zero. This initial condition adds no state or latency and avoids the unconstrained model's instantaneous trigger jump. It is part of the generator, not a post-render alignment or gain correction. Every final candidate is scored at all 264,000 original sample positions; the four corners also receive full-rate polishing.

| Candidate / fitting population | Median L2 | p95 L2 | Worst L2 |
| --- | ---: | ---: | ---: |
| Original harmonic / all 16, historical | 5.3342% | 9.3878% | 11.1348% |
| Controlled restart / all 16 | 5.3028% | 7.8707% | 9.1760% |
| Two output decays + zero start / all 16 | 5.6088% | 9.9444% | 10.3067% |
| Controlled restart / 8 interactions | 5.2645% | 7.1825% | 7.4356% |
| Two output decays + zero start / 8 interactions | 5.2388% | 8.2614% | 8.4307% |

For the two short-Decay corners, the new candidate reduces 50–500 ms error from 13.79/13.86% to 3.11/4.33%. The zero-start requirement trades some whole-waveform score for a consistent trigger condition. No audible improvement is claimed before listening. All 16 selected new fits are converged and numerically viable under the prototype checks, every output starts at zero, and the quiet-window residual checks pass. The original strict source-error targets still fail and remain visible in the JSON.

The candidate has 10 nonlinear and 7 independent linear parameters, expanding to 8 amplitudes. A conservative cache of all 18 expanded parameters, 9 float states and 16 common bytes is 124 bytes/voice. The extra real mode adds one state multiplication and output addition per sample. A prospective 17-function control map using 6–16 float32 coefficients per function would occupy 408–1,088 bytes before metadata; its required complexity is untested until #85. At the upper estimate, the 64 bytes saved versus the proposed 128-byte × 16-slot state reservation offset the extra 64 table bytes versus 1 KiB. This is an arithmetic resource estimate, not a linked layout or a qualified target implementation. Code size, numerical formats and actual instruction/deadline costs remain open under #85–#89.

The listening page provides named previews plus a 16-trial ABX session, one trial per fitting setting in random order. A/B identities and X are randomized independently. All clips retain their full 5.5 seconds and use one common 4× playback gain, with no individual level matching. Playback copies are 24-bit PCM WAVs with that shared gain already applied, played through the browser's native audio controls; raw float reference/prediction data used for fitting and measurements is unchanged. Named WAV download links provide a fallback outside the in-app browser. Answers and the exact binomial chance-tail score appear only after the full session; downloaded results include the stimulus/profile hashes. The test measures discrimination, not preference. A low score is not proof of universal inaudibility, and these fitted settings do not establish new-control generalization. No human listening result has been collected; #84 remains open pending that evidence and the architecture choice.

Validation: seven new Python tests cover the objective, cycle initialization, zero-start amplitude expansion, independent synthetic recovery, acyclic polish receipts and PCM playback copies (shared gain, trigger timing and quantization within one 24-bit LSB). Downloaded WAV bytes match the embedded copies. Node checks exercise ABX randomization, completed-session scoring/export, no premature result, native-media request ordering and playback failures using synthetic responses only. Browser inspection confirmed native media decoding and playback advancing through the full 5.5 seconds without a media error. The user confirmed that the native player now produces sound; this verifies playback, not model fidelity. The earlier Web Audio player displayed "Playing" despite the user's silent-output report and has been replaced.
