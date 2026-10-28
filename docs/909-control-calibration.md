# 909 shared-control calibration: generated-audio experiment

28 October 2026. This follows the [interpolation experiments](909-interpolation.md)
with actual audio from the existing host renderer. It changes only effective
Tune and Decay inputs in an isolated diagnostic. The oscillator, reset, diode
shaper, VCA, settled frequency, output gain, production ASM, state and public
interfaces remain unchanged. This is an exploratory host result, not a production
change or a fidelity pass.

## Calibration and evaluation

Attack is fixed at zero. The five source positions 0/64/128/191/255 on Tune
and Decay form **25 calibration combinations**. Five monotone effective native
control values per knob define shared piecewise-linear mappings. All ten values
stay in the existing 0–32512 range; there is no per-combination parameter, output
gain fit, phase/delay adjustment, normalization or added synthesis stage.

Each fit uses only these 25 settings and all three takes. The mappings are saved
before opening the other **56 settings** in the nine-by-nine Attack0 surface.
Those settings were already explored in earlier training diagnostics and were
also used to assess the successive trials here; they are not a pristine final
acceptance set. The separate 64 final validation settings / 192 takes remain
unopened. No new recordings are needed for this experiment.

The existing corpus metadata/readback audit is reused. Only the 243 unique
Attack0 WAVs are opened for calibration/evaluation; their hashes, project/routing
hashes, float format and equal channels are checked. Fixed reference ×4 removes
the previously audited host attenuation. Comparison starts at scheduled MIDI
time, with the source's six-sample latency retained.

## Trial 1: waveform-only objective — rejected

The first trial minimizes equal-setting/equal-take squared waveform error over
6–500 ms. Deterministic bounded integer searches update the ten mapping values
over two coordinate passes, preserving monotonicity and the current value as a
candidate. This is a bounded search, not proof of a global optimum.

The withheld waveform RMSE improves from **0.0698273 to 0.0484109 FS**, and 45
of 56 settings improve. But duration t99 RMSE worsens **18.553 to 71.594 ms**.
Decay knots move to `[16384,24320,32512,32512,32512]`, collapsing much of the
control range. The waveform objective rewards additional level/energy despite
wrong duration. This candidate is rejected as an overall improvement; its
apparently better waveform error is not adopted on its own.

Post-fit ablations preserve the same frozen parameters. Tune-only remapping
gives withheld waveform RMSE 0.0516585 FS and t99 error 18.388 ms. Decay-only
remapping worsens waveform error to 0.0710479 FS and duration to 71.262 ms.
These comparisons support retaining the useful Tune correction while rejecting
the duration compensation, rather than hiding it with normalization or gain.

## Trial 2: fit measured behaviour, then generate audio

The second, explicitly exploratory trial uses the same ten mapping parameters,
renderer and bounds, but fits Tune to the first 12 positive body-crossing times
after 6 ms at training Decay255. All three takes are retained. It fits Decay to
full-tail t99 across the five training Tune settings and all three takes.
The original host envelope is exactly silent by 500 ms over the allowed range;
the fitting evaluator asserts this before using its half-second energy integral.
Full 16-second renders independently verify the eventual durations.

| Source knob position | 0 | 64 | 128 | 191 | 255 |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original native control | 0 | 8192 | 16384 | 24320 | 32512 |
| Effective Tune | 1217 | 3351 | 9795 | 20366 | 32512 |
| Effective Decay | 3704 | 5939 | 13411 | 25682 | 32512 |

These are empirical input remappings, not identified physical pot tapers or
component measurements. Native control interpolation is integer-rounded and
monotone. Maximum Tune and Decay remain at the existing range ceiling, which
limits correction at those endpoints.

### Results on the 56 settings excluded from fitting

| Measurement | Original renderer | Feature-informed candidate |
| --- | ---: | ---: |
| Generated-waveform RMSE, 6–500 ms | 0.0698273 FS | **0.0513227 FS** |
| Generated-waveform RMSE, 0–500 ms | 0.0698523 FS | **0.0515738 FS** |
| Full-16-second waveform RMSE | 0.0123483 FS | **0.00911710 FS** |
| Full-tail t99 RMSE | 18.553 ms | **6.868 ms** |
| Peak-amplitude RMSE | 0.0873835 FS | 0.0868519 FS |

The body waveform error falls about **26.5%**, and duration error about **63.0%**.
Forty-seven settings improve and **nine regress** in 6–500-ms waveform error.
The largest regression is +0.00524952 FS at Tune223/Decay64
(0.0450131→0.0502626 FS). Do not hide these upper-Tune regressions behind the
aggregate improvement. Of the 25 calibration settings, 23 improve, one regresses
and one remains identical. Later 500-ms–2-second and 2–16-second residuals remain
unchanged; neither renderer generates a tail there, and source residuals remain
included rather than trimmed.

Output level is still wrong: at Tune128/Decay128, the reference peak is
0.233067 FS, the original is 0.146781 FS and the candidate is 0.146344 FS.
The full waveform also retains envelope-shape differences. The trial does not
establish that a global gain correction alone would resolve those differences.
No gain correction is introduced to rescue this experiment.

## Verification and artifacts

The fit factors the existing host renderer into its existing carrier and VCA
envelope to reuse repeated calculations. Three focused tests check its agreement
with `body909.reference` within 1e-14 FS, identity/monotone remapping and bounded
search against known objectives. All **57 selected 909 host tests** pass.

Evaluation reuses `reference909_grid.model_oracle` and its existing declared
exact-zero continuation after the passive VCA becomes silent. It does not claim
that actual CPUs executed the analytical zero tails. Every candidate's first
500 ms matches the fit evaluator within 1e-14 FS. Four independent direct
`body909.reference` renders at default, minimum and difficult withheld cases
reproduce saved waveform heads and reference RMSEs within 1e-14 FS. All generated
candidate peaks remain below the unchanged 0.25 FS host body bound; the maximum
is 0.147196 FS. Sources and control mappings are hashed and frozen.

The main diagnostic is `tools/x0x/calibrate909.py`, with focused tests in
`tests/host/test_calibrate909.py`. The initial report, frozen fit, full-tail
baseline/candidate arrays, ablation source/results and selected WAVs are retained
under ignored `out/reference/909-calibration-20261028/`. The feature-informed
trial source, frozen protocol/mappings, all 81 full-tail candidate arrays,
per-take results, independent audit, review plot and listening illustration are
under ignored `out/reference/909-calibration-features-20261028/`.

The primary trial runs from the checkout root with the existing research
dependencies and a new output directory:

```zsh
mise exec -- uv run --offline --frozen --project vendor/digiemu \
  --with numpy==2.5.4 --with soundfile==0.14.0 \
  --python "$(mise which python)" python -m x0x.calibrate909 \
  --output out/reference/909-calibration-new
```

The retained `feature_trial.py` is a single-use experiment: copy it into a new
empty output directory to rerun, and set its `PREVIOUS` path to the regenerated
primary trial if using a different location. It refuses an existing frozen fit.
The retained `review.py` checks direct renders and creates the scientific plot.
Its listening WAV plays reference/original/candidate at default controls, then
reference/original/candidate at minimum controls, with one-second excerpts and
0.5-second gaps. Source take 1, fixed shared routing correction and original
model gain are preserved; no peak matching or formal listening acceptance.

This demonstrates an improvement in generated audio from shared parameter
relationships without rewriting the synthesis stages. Production adoption,
gain/envelope-shape work, upper-Tune regressions, final validation, Attack,
live controls/retrigger, actual CPU implementation and hardware qualification
remain open in [#2](https://github.com/simonjohansson/x0x/issues/2),
[#25](https://github.com/simonjohansson/x0x/issues/25) and
[#79](https://github.com/simonjohansson/x0x/issues/79).
