# Replacement 808 from the fresh corpus

[Parent #82](https://github.com/simonjohansson/x0x/issues/82) owns this work. The complete implementation plan and its 12 native sub-issues are recorded there. The final mod must provide per-voice 808/909 coexistence on Digitakt, Digitone and Digitone II. Private state, ASM and adapters may be rewritten; the present 909 implementation is optional during development.

## Current status

28 October 2026: [#83](https://github.com/simonjohansson/x0x/issues/83) is complete in commit `972d30c`. [#84](https://github.com/simonjohansson/x0x/issues/84) now has a complete, quantized spline/carrier candidate: 0.5548% median / 0.7051% worst validation waveform error, with 4,089 bytes of model-array payload. Its first verified human ABX scored 9/16 (`p = 0.40181`), which does not demonstrate reliable discrimination in this session. It is a promising listening baseline; universal inaudibility, the combined resource budget and target realization remain unqualified. The prior procedural candidate was distinguishable in the user's 16/16 session and is historical evidence only. Production DSP has not changed.

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

The listening page provides named previews plus a 16-trial ABX session, one trial per fitting setting in random order. A/B identities and X are randomized independently. All clips retain their full 5.5 seconds and use one common 4× playback gain, with no individual level matching. Playback copies are 24-bit PCM WAVs with that shared gain already applied, played through the browser's native audio controls; raw float reference/prediction data used for fitting and measurements is unchanged. Named WAV download links provide a fallback outside the in-app browser. Answers and the exact binomial chance-tail score appear only after the full session; downloaded results include the stimulus/profile hashes. The test measures discrimination, not preference. A low score is not proof of universal inaudibility, and these fitted settings do not establish new-control generalization. The exported report was generated before the human session described below; #84 remains open for the architecture choice.

Validation: seven new Python tests cover the objective, cycle initialization, zero-start amplitude expansion, independent synthetic recovery, acyclic polish receipts and PCM playback copies (shared gain, trigger timing and quantization within one 24-bit LSB). Downloaded WAV bytes match the embedded copies. Node checks exercise ABX randomization, completed-session scoring/export, no premature result, native-media request ordering and playback failures using synthetic responses only. Browser inspection confirmed native media decoding and playback advancing through the full 5.5 seconds without a media error. The user confirmed that the native player now produces sound; this verifies playback, not model fidelity. The earlier Web Audio player displayed "Playing" despite the user's silent-output report and has been replaced.

## Human discrimination result, 28 October 2026

The user supplied `808-listening-results.json` after confirming the native player's audio output. All 16 trial indices are unique, A/B assignments and answer fields are valid, and recomputing the score gives **16/16 correct**. The exact random-guessing tail probability is `1/65536 = 0.0000152587890625` (about 0.00153%). The session lasted 128.593 seconds.

Source, fitted-model driver, benchmark, original-model driver, protocol, cohort and baseline hashes match the current core candidate. The submitted player-template hash `6658d4b9…` was reconstructed exactly from the earlier native-player layout: only control placement/visibility changed afterward; stimuli, gain, A/B/X assignment and scoring were unchanged. The raw result and verified summary are retained locally under `research/reference/808-fit-model/listening/`; the input SHA256 is `bd4b5f356acd5b1c2bda9cbd192e44b7bac56509ef8271216411adb24d857328`.

This is strong discrimination evidence for this listener and session, so the core candidate cannot be accepted on an inaudibility claim. It does not establish a preference, a physical-device result, or statistical significance for each individual setting (there was one trial per setting). The user identified differences in all three cue groups: attack/click, tone/pitch and decay/body. An attack-only patch is therefore not selected as the solution. Quantitative source error remains a diagnostic; the human result supplies the missing perceptual evidence rather than replacing it with a percentage rule.

## Conditional Tone factorization (#84)

The next structural test asks whether Tone can be a filter around a shared Decay-controlled body, rather than another set of independent oscillator/envelope parameters. [tone_factor808.py](../tools/x0x/tone_factor808.py) fits one five-parameter law from 64 non-identity Tone-sweep settings at **Decay zero only**. The loss uses the first 0.25 seconds, which contains almost all energy at minimum Decay, with equal setting weight. No output normalization, fitted per-hit gain or alignment is used. All final measurements use complete 5.5-second slots.

For the delivered source coordinate `T`, define:

```text
x = T ** q
tau(T) = tau_min + a*(1-x) + b*(1-x)/(x+c)
p(T) = (tau(T) - 1/(2*48000)) / (tau(T) + 1/(2*48000))
```

All five physical parameters are positive and `tau_min > 1/(2*48000)`, keeping poles inside `(0,1)`. The conditional prediction uses the **recorded Tone-127 waveform at the same Decay** as its input, through:

```text
H(T)/H(127) = ((1-p(T))/(1-p(127))) * (1-p(127)*z^-1)/(1-p(T)*z^-1)
```

This relative transfer has unity DC gain. A direct-form-I recurrence stores the previous input and output; an equivalent transposed recurrence needs only one state, as does a direct Tone filter around a future unfiltered generator. The formula is an effective model inferred from these recordings, not proof of unique physical component values.

| Conditional component population | Settings | Median L2 | p95 L2 | Worst L2 |
| --- | ---: | ---: | ---: | ---: |
| All scored training pairs | 128 | 0.102589% | 0.206577% | 0.301860% |
| Other-Decay pairs excluded from fitting this Tone law | 64 | 0.058054% | 0.151019% | 0.237221% |

Nine Tone-127 identity cases are retained separately as sanity checks and excluded from those statistics. All inputs and targets remain inside the original fitting partition. The other-Decay component test is conditional on a measured input; it is **not full-generator generalization**, and no reserved validation/test waveform is used. The future canonical body still has to be synthesized.

The five float32 parameters occupy 20 payload bytes. Their maximum measured output difference versus float64 parameters is `3.50e-10` capture FS. All 32,513 native control words, including fractional CC positions, have finite, stable, monotonic poles spanning approximately 0.21645–0.96035. Actual target coefficient encoding, linked footprint, instruction cost and full-model audibility remain unqualified.

Reproduce with `mise run research:808:tone-factor`. Seven focused tests cover the transfer against independent direct-filter and single-state recurrences, stability, unity gain/identity, synthetic shared-fit recovery, float32 encoding and invalid inputs. The native-media/ABX regression checks also pass. Reports, a model NPZ, pole/error curves, waveform plots and an explicitly labelled **component-only** listening page are under `out/808-model/tone-factor/`. That page uses a fixed 4×4 cohort: Tone 0/17/68/119 and Decay 0/17/68/127, avoiding trivial Tone-127 identities.

This evidence supports the factorization `output(Tone,Decay) = ToneFilter(Tone, canonical_body(Decay))` as the next architecture hypothesis. It naturally produces interactions between the knobs without fitting arbitrary per-setting waveform corrections. It does not close #84: the prior full body failed listening, and the canonical body representation and whole-model listening acceptance remain open.

## Complete quantized listening candidate (#84)

[field808.py](../tools/x0x/field808.py) replaces the independently fitted procedural body with one learned body field. It generates an isolated 5.5-second kick from Tone and Decay alone; no recording is a runtime input. This is a different complete candidate for listening, rather than acceptance of the earlier failed core.

The canonical body is `sum_k weight_k(Decay) * basis_k(time)` with eight shared components. Each component blends a short cubic spline into cubic amplitude/phase envelopes around a nominal 47.65 Hz carrier, its second/third harmonics, and a nonoscillatory envelope. The overlap runs smoothly from 20 to 30 ms. Independent sine/cosine envelopes encode changes in phase and apparent pitch. The onset starts exactly at zero by construction. The supported relative Tone filter then maps the canonical Tone-127 body to the requested Tone. No per-recording alignment, normalization or post-render level fit is applied.

Training uses only the original fitting partition: the same 64-position Tone axis fits the filter. There are 65 canonical Decay targets: nine measured Tone-127 settings and 56 obtained by applying the fitted inverse relative Tone transfer to the corresponding Tone-0 recording. These inferred targets are not additional measurements. A bounded singular-value truncation fits the spline/carrier dictionary; a waveform-energy metric, with equal setting weight, selects eight body components. Two early coefficient blocks have smaller shared ranks of two/four. One 17-break cubic Decay map supplies all eight weights, including fractional native controls. The validation partition guided rank/map/compression choices; the original test partition was not read for this candidate's selection or evaluation.

The saved model contains signed 16-bit coefficient tables and float32 scales, Tone parameters and geometry. All reported predictions and playback copies are reconstructed from those saved arrays. The **4,089-byte payload** includes geometry and control maps, but excludes container metadata, alignment, code, mutable voice state and initialized-data packaging. It exceeds the historical 1 KiB 808-table proposal. The dependency now pins Elekloader PR #211 head `3ce40f6faaf87166c4a34ad1f6f48bafc3085991`: the intended SDK envelope is 30 KiB code including its guard, 31 KiB data including all sixteen voice states, and a 2,048-byte callback stack budget. The original 8 KiB/5 KiB proposal is superseded. A revised linked budget preserving the future 909 is still required; a small array payload alone does not establish that the combined mod fits. The replacement target ASM and its numerical/cost qualification remain pending.

| Decoded candidate / population | Distinct settings / takes | Median L2 | p95 L2 | Worst L2 |
| --- | ---: | ---: | ---: | ---: |
| Fitting | 193 / 211 | 0.5276% | 0.6952% | 0.7129% |
| Validation | 144 / 152 | 0.5548% | 0.6953% | 0.7051% |

On the same 16 fitting settings as the rejected core, first-take median/worst errors are now 0.4952%/0.7030%, versus 5.6088%/10.3067% previously. This improvement is a waveform diagnostic, not a claim that the difference is inaudible. All 32,513 native control words give finite weights and stable Tone poles, and every waveform starts exactly at zero.

Known numerical limitations remain visible in the report. Validation 50–500 ms p95/worst errors are 7.1452%/7.1752%, particularly where the body has much less energy than the attack; t99 worst error is 5.7917 ms. The quiet-tail limits fail on 66 validation takes (maximum residual RMS `1.21e-5`, maximum sample `6.07e-5`, in capture FS). At the common 4× playback gain those maxima are approximately −86 dBFS RMS / −72 dBFS peak. Neither their audibility nor their acceptability is established. The original whole-waveform median, body, duration and quiet-tail gates therefore do not all pass. Do not promote this result to complete numerical, listening or hardware qualification.

Reproduce with `mise run research:808:field`. Nine focused tests cover independent de Boor spline evaluation, coefficient quantization bounds, zero start and smooth overlap, a standalone known-carrier/Tone recurrence, fractional controls, NPZ round-trip rendering, synthetic fitting at an unfitted control position, listening-cohort membership and invalid inputs. The seven existing diagnosis tests, native-media/ABX controller checks and seven Tone-stage tests also pass. The full research run verifies the original 121 artifacts and evaluates complete slots, retaining repeated takes and grouped summaries. A broader repository-wide test rerun is not claimed.

Outputs are under `out/808-model/field/`: `model.npz`, `report.json`, waveform/error plots, 32 playback WAVs and a self-contained `index.html`. The page retains native audio playback and one common 4× gain. Its 16-trial ABX cohort contains four fitting corners and twelve stratified validation settings. Because validation guided complexity selection, this is development listening rather than fresh independent acceptance under #90. The exported result records the model, source, protocol and driver/template hashes and the actual cohort scope. The previous player/result remain separate under `out/808-model/diagnosis/` and the immutable local listening archive.

#84 stays open pending the architecture/resource decision and subsequent qualification. The first human result is recorded below. No ASM, firmware, native-emulator or physical-device qualification has been performed for this candidate.

## Human result for the quantized field, 28 October 2026

The user supplied `808-listening-results-2.json`: **9/16 correct**, compared with eight expected on average under random guessing. Independently recomputing the exact probability of at least nine correct guesses gives **0.4018096923828125**, about 40.18%. This session therefore does not demonstrate reliable discrimination above guessing. This is not the probability that the sounds are identical, and it cannot identify which individual answers were guesses. Sixteen trials cannot rule out subtle differences.

All 16 trial indices, A/B/X fields, answer flags, settings, common 4× gain and source/model/protocol/driver/template hashes match the frozen candidate. The session lasted 208.181 seconds. Raw input SHA256 is `1ec2aa3c4dcd9c40730895abf941eb009f3ed7ca351a442d3a958b92c5d23422`; the model SHA256 remains `fb4519537afc1142f3c108bc9e94fe40b752f2b967a97ab6e185e5e47a04d112`. Raw results and the verification summary are archived locally as `listening/2026-10-28-field-abx{,-summary}.json` under the fresh corpus directory. The original generation-time model/report/player archive remains unchanged.

The user described this comparison as **much harder**, with occasional slight tonal/apparent-pitch differences that were very hard to hear, and felt many correct answers could have been luck. Preserve this as qualitative feedback, not a confirmed pitch-offset diagnosis. The previous 16/16 and current 9/16 sessions used different cohorts; this is not a paired statistical comparison of the models.

Keep this candidate as the development listening baseline while checking SHARC/ColdFire resource and numerical feasibility. This is neither final perceptual acceptance nor closure of #84. The existing body/duration/quiet-tail diagnostics and 4,089-byte table budget are unchanged; fresh independent acceptance remains under #90. No additional source fitting, waveform changes or hardware tests were performed to record this result.

## SHARC ASM candidate — 28 October 2026

The user chose SHARC first; **ColdFire is deferred**. The new renderer is
[hand-written assembly](../targets/sharc/field808.s), with the coefficient
exporter and local instruction harness in
[sharc_field808.py](../tools/x0x/sharc_field808.py). No C compiler supplies the
sample loop. The original frozen model and listening stimuli are unchanged.

This first isolated-hit candidate latches Tone and Decay at START. Continued
blocks retain age, carrier and Tone state; another START resets only that slot.
The native MODEL threshold still latches on START, but the 909 branch deliberately
outputs silence in this development artifact. Final combined 808/909 delivery
and live modulation behaviour remain separate work.

The exporter decodes the frozen quantized field into float32 basis coefficients,
exports normalized cubic B-spline basis polynomials, and caches the dense onset
per voice. Four pairs/scalar tail envelopes are updated only at segment changes.
The carrier uses a 64-bit block phase accumulator, a folded degree-11 sine and
32-sample recurrence. The transposed relative Tone filter uses cubic pole
interpolation with dyadic refinement below CC 1. A first low-control test exposed
an integer/float register-alias bug; it was corrected and covered by fractional
control regression cases. An earlier smaller polynomial encoding was rejected
for excessive extra waveform error; neither failure changes the frozen sound.

The private split is **12 KiB code / 49 KiB data** inside PR #211's 64 KiB voice
owner. Actual code is **2,330 bytes**, initialized tables **29,980 bytes**,
per-voice state **1,060 bytes**. With alignment and all sixteen slots, data usage
is **46,944 bytes**, leaving **3,232 bytes**. The provisional 909 table/common/
headroom reservations of 1,280/256/512 bytes still fit; 909 code reservations
also fit. The kernel uses zero software-stack bytes beyond the adapter's own
frame; helper calls use the hardware PC stack. This is a measured isolated
layout, not a physical full-polyphony performance result.

```sh
mise run test:808:sharc-model
mise run research:808:sharc-model
mise run firmware:dn2:808-model
```

Eight focused tests cover exported tables versus the independent frozen model,
ELF/region refusal, explicit future 909 reservations, actual ASM fractional
output, slot/reset/MODEL/silence behaviour, immutable tables and independent
Python/native instruction traces with every DSP write bounded to its own voice
and output. No reciprocal approximation is used. The firmware-free native
runner's source identity is checked against the pinned Digikit core; this does
not boot an emulated device.

The local qualification generates full 5.5-second outputs for the same sixteen
listening settings plus six fractional/boundary settings, compares each directly
with the frozen model, and compares the sixteen recorded cases with their
original capture slots. Port errors and source-model errors stay separate.
The numerical limit is maximum absolute port error ≤1e-5 DSP FS. The original
source body/quiet-tail failures remain diagnostics, not repaired by the port.

Outputs are under `out/808-model/sharc/`: `report.json`, `waveforms.png`, the native
media/ABX `index.html`, float output WAVs, build/source receipts and
`device-test/x0x-sharc808.syx` (firmware version **X8A1**). Audio in that listening
page is actual executed ASM output, using the same shared 4× playback gain.
Firmware and generated coefficient tables remain local build outputs.

The SDK packaging check verifies the ID20 entry and managed per-voice-state
binding before producing the image. No physical device or full-device emulator
has been booted. Instruction counts are not cycle counts or available stock-DSP
headroom. Request a physical Digitone II for native integration, listening,
polyphony and timing after local qualification; prefer it over a full-device
emulator for those next checks. #84 stays open through that qualification.

Local candidate result: all **22 full-length ASM renders** pass the port gate.
Maximum error against the frozen model is **2.6764e-6 DSP FS**; maximum relative
L2 port error is **1.8517e-6** (0.0001852%). On the sixteen recorded listening
settings, source waveform error is **0.5596% median / 0.6954% worst**. These are
separate quantities: the ASM reproduces the existing listening candidate; it
does not remove that model's residual source error or establish inaudibility.

The maximum observed complete-hit block is **21,100 instructions**. A separate
cold-cache witness jumped to age 960 takes **21,608 instructions**. Both Python
instruction witnesses match the native runner's output and entire voice state
bit for bit, with writes confined to that voice and its output; no software-stack
writes occur. These are software instruction measurements, not physical cycles.

Eight focused SHARC tests, six existing layout tests, seven existing diagnostic
tests and native-media/ABX controller checks pass. A real browser check decoded
5.5 seconds of PCM24 ASM audio, reached readyState 4 and advanced playback without
an error. No human discrimination result is inferred. The repository-wide suite
was not rerun; the three historical feedback-model failures preserved in
`cb7f2b2` remain separate research limitations.

The ready test firmware SHA256 is
`fe55ed39f8a77f70867d2ccf78097446fe10a68afd31088072068e18348f004a`.
The callback/coefficient artifact SHA256 is
`c0f979058674a634c0f89bdebbdf69a3aee8b4722ce0783bbf4afe341dc5eb0c`.
No device has been flashed. The next required equipment is a physical Digitone II
on OS 1.12 for native callback/routing, audible output, lifecycle and measured
voice-count/deadline checks.

The listening player now also offers **Can’t tell**. It exports that choice as
`cant-tell` with `correct: null`, reports it separately and excludes it from the
right/wrong denominator. If any trial is an abstention, the session's chance-tail
probability is `null`; a selectively answered subset is not presented as a
forced-choice significance result. All-A/B sessions retain the original scoring.
The response policy is versioned as `a-b-or-cant-tell-v1`, and the exported
manifest records the exact player-template hash. Historical results/stimuli are
unchanged. The controller checks include all-uncertain and mixed sessions.
