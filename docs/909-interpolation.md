# 909 training-grid interpolation

28 October 2026. This extends the [control-interaction diagnostic](909-control-interactions.md)
by predicting control positions excluded from calibration. It uses only the
existing 729-setting training grid and leaves all 64 final validation settings
/ 192 takes unopened. No captures or production DSP changes were made.

The subsequent [shared-control calibration experiment](909-control-calibration.md)
now tests actual generated audio using the unchanged host synthesis stages. It
preserves a rejected waveform-only fit and a feature-informed candidate with
measured improvements and regressions; it does not adopt production DSP changes.

## Experiments and evidence

The driver reuses the existing protocol/readback audit and independently checks
all 2,187 WAV hashes, float format, channel equality, project/routing hashes and
cached feature provenance. Actual source coordinates are 0, 32, 64, 96, 128,
159, 191, 223, 255; they are not treated as perfectly equally spaced. Fixed
reference gain is the existing routing correction of ×4. Scheduled MIDI time,
all three target takes and source timing are preserved. There is no averaging,
normalization, fitted gain, offset or waveform alignment.

Two predeclared checks use local linear and four-knot cubic Lagrange interpolation:

1. **Common 64 targets.** Fit either three positions (0/128/255; 27 combinations)
   or five positions (0/64/128/191/255; 125 combinations). Predict the identical
   64 combinations formed from 32/96/159/223 on all three controls. These are
   training-grid recordings withheld for this experiment, not the separately
   named final validation recordings. Three-position fitting uses linear
   interpolation; five-position fitting uses both linear and cubic methods.
2. **Leave one position out.** For each knob and each of its seven interior
   positions, remove the entire 81-setting plane at that position. Interpolate
   from the remaining eight positions while the other knobs keep all nine.
   There are 21 folds per method, 567 predictions per knob. Settings recur in
   different folds/experiments; these are not independent new captures.

Only take 1 supplies calibration data. All three target takes are scored
separately. Cubic predictions are not clipped or constrained to be monotone;
negative predictions for nonnegative features remain reported. Missing pitch
measurements stay missing, and every metric records its eligible setting count.

Waveforms cover the scheduled first 500 ms. The first 6 ms are reported
separately and remain low priority following the user's informal default-setting
listening comparison. Full-16-second 10-ms RMS envelopes, energy and t99 use the
existing audited feature artifacts. Feature interpolation is evaluated directly
in feature space; it does not generate a waveform with those features.

## Results on the same 64 combinations

The following table uses target take 1. Later body waveforms and RMS envelopes
are identical across target takes; small early-feature differences are retained
in the report.

| Measurement | Three positions, linear | Five positions, linear | Five positions, cubic |
| --- | ---: | ---: | ---: |
| Body-pitch summary RMSE, cents | 37.18 | 14.65 | 5.83 |
| t99 error RMSE, ms | 8.87 | 3.44 | 1.40 |
| Full-16-second energy relative L2 error | 2.48% | 0.94% | 0.21% |
| Peak error RMSE, FS | 0.01676 | 0.01205 | 0.00682 |
| 20–500-ms windowed RMS-envelope relative L2 error | 7.02% | 6.74% | 7.46% |
| 6–500-ms waveform error RMSE, FS | 0.08946 | 0.09292 | 0.10464 |

Five-position cubic body-pitch error has a 95th percentile of 13.89 cents and
maximum 15.30 cents on these 64 targets. t99 maximum error is 3.45 ms. These
are descriptive errors, not newly adopted fidelity or audibility tolerances.
Increasing interpolation order does not improve every measurement: raw waveform
and short-window RMS-envelope prediction get worse with cubic interpolation.

## Why Tune needs a phase-aware representation

Leaving out Tune positions causes large waveform errors: pooled 6–500-ms RMSE
is 0.09639 FS for linear and 0.13427 FS for cubic interpolation. The positive
crossings show why direct sample blending is a poor representation of this
pitch sweep. At Attack0/Decay255, the seventh positive body crossing after 6 ms
is at 107.732 ms for Tune64, 98.977 ms for Tune96 and 87.366 ms for Tune128.
The endpoint timing difference exceeds one settled body period. Samples at a
fixed time can therefore blend nearby endpoint phases while missing the
intermediate control's phase by a large fraction of a cycle.

A bounded follow-up probe interpolates the first 12 positive-crossing times
after 6 ms, at Attack0/Decay255 and take 1, using the same Tune calibration
positions and four withheld Tune values. It preserves scheduled time and does
not shift audio or fit an alignment offset. It requires 13 resolved crossings
with bounded periods and cycle amplitude above the existing relative floor.

| Cycle-timing prediction | RMSE | Maximum error |
| --- | ---: | ---: |
| Three positions, linear | 3.276 ms | 5.051 ms |
| Five positions, linear | 1.178 ms | 1.860 ms |
| Five positions, cubic | 0.382 ms | 0.967 ms |

This supports interpolating pitch/phase trajectories rather than raw waveform
samples. It is one long-Decay diagnostic, not a phase-aware synthesized renderer
or a complete Tune/Decay phase-trajectory qualification.

## Where further resolution might help

- **Upper Tune with short Decay:** the largest leave-one-Tune linear body-pitch
  error is near Tune223, particularly at Decay32. The cubic worst case is also
  in the high-Tune/short-Decay region. Some pitch-summary differences reflect
  the analyzer's changing eligible cycles and peak-relative floor, so these
  summaries are not isolated oscillator-parameter measurements.
- **Low Decay:** leaving out Decay32 produces the largest waveform/energy
  interpolation errors. Across Decay folds, cubic waveform RMSE falls from
  0.001454 to 0.000669 FS compared with linear; full-tail energy RMSE falls from
  2.29e-5 to about 2.14e-6 FS² s. Duration and peak tradeoffs remain in the report.
- **Attack:** held-out Attack positions reproduce 6–500-ms audio to round-off
  (pooled linear RMSE 2.74e-18 FS). This does not qualify the variable first
  6 ms or establish inaudibility across Attack's complete range. Body-pitch
  summary changes despite identical later audio can arise from the analyzer's
  full-hit-peak-dependent validity threshold.

The present evidence supports continuing with the current corpus and building
a compact pitch/phase/envelope model. It does not justify blanket 0–127 sweeps
as the next step. If that model leaves systematic errors, target the regions
above with new training captures. This test cannot rule out finer structure
between the existing nine positions or prove that dense sweeps add nothing.
Freeze the candidate before using the reserved final validation corpus.

## Reproduce and checks

### Plots against the complete measured grid

The subsequent plotting check evaluates the same five-position cubic feature
interpolator against all 729 measured settings: 125 fit settings and 604 withheld
settings. It marks the original common 64 separately from the additional 540;
it does not open the final validation corpus or change the original experiment.
Take 1 is shown, with measured repeat ranges on the knob slices. Calibration
identity and the original common-64 pitch/duration errors are checked before
plotting. Raw waveform predictions are not part of these feature graphs.

Across all 604 withheld settings, body-pitch-summary RMSE is 7.679 cents and
t99 RMSE is 1.136 ms. Maximum absolute pitch-summary error is **80.15 cents**
at Tune255/Attack255/Decay32; the broader check therefore exposes a larger
outlier than the original common-64 test. The analyzer's eligible-cycle and
peak-relative-floor limits still apply; this is not a measured pitch error of
a synthesized renderer.

The figures show the full-grid parity plots and three explicit knob slices:
Tune at Attack128/Decay0, Decay at Tune128/Attack128, and Attack at
Tune128/Decay128. Cubic and linear predictions, the five fit positions, all
four withheld measurements and residuals are shown on each slice. The Tune
slice deliberately includes short Decay rather than selecting only a favorable
region.

PNG/PDF figures, script and plot-data/source hashes are retained in ignored
`out/reference/909-interpolation-plots-20261028/`. Regenerate from the checkout
root with the retained script and the existing cached feature baseline:

```zsh
MPLCONFIGDIR=out/matplotlib-cache mise exec -- uv run --offline --frozen \
  --project vendor/digiemu --with numpy==2.5.4 --with matplotlib==3.11.2 \
  --python "$(mise which python)" \
  python out/reference/909-interpolation-plots-20261028/plot.py
```

### Interpolation driver

The new driver is `tools/x0x/interpolation909.py`. It reads the existing audited
`out/reference/909-grid/` features and restored reference captures. From the
checkout root, using a new output directory:

```zsh
mise exec -- uv run --offline --frozen --project vendor/digiemu \
  --with numpy==2.5.4 --with soundfile==0.14.0 \
  --python "$(mise which python)" python -m x0x.interpolation909 \
  --output out/reference/909-interpolation-new
```

The current report, corpus audit and frozen driver are in ignored
`out/reference/909-interpolation-20261028-refined/`. Initial interpolation-only
results remain in `out/reference/909-interpolation-20261028/`. Seven focused
tests cover uneven-coordinate interpolation, exact knots, polynomial recovery,
missing features, disjoint fitting/evaluation, summary arithmetic and cycle
timing. Five existing interaction tests and six existing grid/comparison tests
also pass. Six worst-case direct-WAV reconstructions use independent Vandermonde
solves and reproduce the reported waveform errors within 1e-14 FS; their source
and results are retained beside the report.

These are host/software-reference results. Production DSP, CPU/emulator output,
physical devices and new listening acceptance were not tested or changed.
Reference-fidelity acceptance remains open in
[#2](https://github.com/simonjohansson/x0x/issues/2).
