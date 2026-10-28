# 909 control-interaction diagnostic

28 October 2026. This tests how far separate control responses can predict
combinations in the existing Roland software-reference corpus. It does not fit
or change production DSP. Reference fidelity remains open in
[#2](https://github.com/simonjohansson/x0x/issues/2); implementation remains in
[#25](https://github.com/simonjohansson/x0x/issues/25).

## Method

All 729 training settings and three fresh takes are used. Before analysis, the
existing grid audit checks the protocol and fixed-control readbacks. Every WAV
hash, float format, channel equality, project hash and routing is rechecked.
Previously extracted full-tail features are accepted only with matching artifact,
metadata and per-record WAV/project hashes. Reference gain is the documented
fixed host correction of ×4; no fitted gain, onset alignment, normalization,
averaging or selection of the best take is applied.

Three baselines are declared: Tune/Attack/Decay 0/0/0, 128/128/128 and 128/0/255.
For each baseline, take 1 supplies calibration recordings; predictions are scored
against all three target takes separately. Every scored target differs from the
baseline on **all three controls**. These 512 settings per baseline therefore
belong to none of the calibration planes. The three evaluation sets overlap;
they are not 1,536 distinct settings or independent experiments.

The initial comparison uses two representations:

- Independent control curves: 25 unique calibration settings, the union of
  three nine-position lines through the baseline.
- All pairwise interactions: 217 unique calibration settings, the union of
  three nine-by-nine planes through the baseline.

An exploratory simplification follows the initial pairwise result: one
Tune–Decay surface plus one Attack curve, using 89 unique calibration settings.
It uses the same 512 evaluation settings, conservatively withholding even the
extra settings it could score. If `S(T,A,D)` denotes a waveform and the baseline
is `(T0,A0,D0)`, its prediction is:

```text
S(T,A0,D) + S(T0,A,D0) - S(T0,A0,D0)
```

This is an empirical decomposition of recorded output, not identification of
isolated physical body and attack circuits. It still uses a measured two-control
surface; it does not supply a compact synthesis equation or interpolation law.

## Results

First-500-ms waveform RMSE in routing-corrected FS units, target take 1:

| Baseline T/A/D | Independent curves | All pairwise terms | Tune–Decay + Attack |
| --- | ---: | ---: | ---: |
| 0/0/0 | 0.0410246 | 0.00185078 | 0.00126909 |
| 128/128/128 | 0.0302328 | 0.00220437 | 0.00162034 |
| 128/0/255 | 0.0472904 | 0.00156041 | 0.00121481 |

All three target takes retain the same conclusion. The simpler surface/curve
prediction reduces first-500-ms error by about 94.5–97.5% across baselines/takes,
relative to independent curves. Its remaining RMSE is 0.001204–0.001667 FS,
versus 0.000893–0.000937 FS for take-1-to-take-2/3 repeat differences on the
same evaluation sets. Those repeat differences are an observed comparison
baseline, not a fully identified stochastic error floor or confidence interval.

For the simpler predictor, the 6–50-ms and 50–200-ms residuals are exactly zero
in the decoded samples. The largest aggregate 200–500-ms RMSE is 1.34e-19 FS.
The independent curves also reproduce 6–50 ms, but fail in the later body;
the Tune–Decay surface removes that discrepancy. Remaining practical waveform
error is confined to the first 6 ms. Adding the other pairwise terms worsens
that early prediction in this experiment; their noisy calibration recordings
do not establish a useful additional interaction model.

Independent direct-WAV arithmetic reproduces the independent-curves worst-case
RMSE exactly for one target per baseline. At those three targets, the simpler
predictor's maximum absolute 6–500-ms residual is at most 1.74e-18 FS.

A subsequent independent streaming audit extends the simpler predictor to all
16 seconds, all 512 target settings per baseline and all three takes. Its
first-500-ms aggregate errors reproduce the main report within 1e-16 FS. From
6 ms through 16 seconds, the maximum absolute error is 1.74e-18 FS; from
2 through 16 seconds it is exactly zero. This checks raw tails directly,
without relying on a long-window RMS that could dilute a localized error.
The audit source and `full-tail-audit.json` are retained beside the report.

Full-16-second 10-ms RMS envelopes, total energy, t99, peak and reliable body/late
pitch summaries are also retained. Derived features are each predicted in their
own feature space; they are **not measurements of a synthesized predicted WAV**.
Nonlinear RMS, quantiles and pitch estimators need not inherit additive waveform
relations. Their residuals must not be mistaken for contradictory waveform
evidence or extra identified circuit terms. Missing pitch stays missing; all
three models and repeat comparisons use a common eligible subset per metric.
The zero baseline cannot predict late pitch because its short-decay calibration
does not provide reliable late pitch measurements.

## What this establishes and what remains

The current grid strongly supports treating Tune and Decay jointly and Attack
as a separate recorded contribution. Three independent curves alone are
insufficient. No detectable additional three-way waveform term is needed in
the tested 6-ms-through-16-second interval; the variable early
transient remains unresolved above observed repeat differences.

Use this structure as a modelling hypothesis, then test a compact parametric
renderer against these same training predictions. The subsequent
[training-grid interpolation diagnostic](909-interpolation.md) now compares
withheld positions and identifies the limits of direct waveform interpolation.
The 64 held-out settings / 192 takes remain
unopened and reserved for a frozen candidate and acceptance protocol. First-6-ms
transient statistics, a phase-aware interpolated renderer, retrigger/history,
strength/accent, live edits, listening and physical-device fidelity remain
unqualified. No new captures are required for the next training-model step.

At default controls, pairwise repeat differences during the first 6 ms are
20.20–24.66 dB below the reference window RMS (about 5.8–9.8% in amplitude).
The largest sample difference is 0.0195133 FS as recorded, about 17.1% of
take 1's full-hit peak. Differences end by 4.4375 ms there. These exceed numerical
round-off, but neither amplitude ratios nor a difference signal establish
audibility. An unblinded illustration plays takes 1/2/3 twice, using scheduled
one-second excerpts, 0.5-second gaps and the same ×4 gain; its WAV and metadata
are retained beside the report. No listening acceptance is claimed.

## Reproduce

The driver refuses an existing output directory. The existing audited feature
baseline is `out/reference/909-grid/`; regenerate that through the
[grid workflow](909-reference-grid.md) if absent. From the checkout root:

```zsh
mise exec -- uv run --offline --frozen --project vendor/digiemu \
  --with numpy==2.5.4 --with soundfile==0.14.0 \
  --python "$(mise which python)" python -m x0x.interaction909 \
  --output out/reference/909-interactions-new
```

Remove `--offline` only if the declared research dependencies are not cached.
Current results and direct-WAV audit are in ignored
`out/reference/909-interactions-20261028-refined/`; the initial pairwise-only run
is preserved separately in `out/reference/909-interactions-20261028/`.
Five focused synthetic tests verify additive/pairwise recovery, detection of a
three-way term, the simpler surface/curve model, disjoint calibration/evaluation
and missing-feature handling. Six existing grid/routing/comparison tests pass.
These are host analysis checks, with no CPU/emulator or physical-device run.
