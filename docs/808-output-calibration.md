# 808 fixed output calibration

The human approved one fixed DSP scaling factor on 28 October 2026 after
clarifying that native AMP/track LEVEL remains the user volume control. This
increment applies **1.6016645431518555 (+4.091431 dB)** after C47 on both CPUs.
It is shared across settings and devices, with no saved value or comparison-time
normalization. The model's circuit state and native volume path stay unscaled.

## Level protocol frozen before fitting

Measurements use the scheduled MIDI sample as time zero at 48 kHz. There is
no onset alignment, averaging of recordings, phase shift or DC subtraction.
The reference multiplier of four only removes the audited REAPER routing.
Keep as-recorded comparisons separately. Use each of the 243 training takes
and both actual CPU baselines, bound to `5963a34`:

- Peak: maximum absolute sample over 0–500 ms.
- Attack RMS: 0–25 ms; body RMS: 25–150 ms; tail/body RMS: 150–500 ms.
- Level error: `20*log10(model/reference)`, with an inclusive +/-2 dB target.
- A reference window below .001 FS (-60 dBFS) is retained as a quiet diagnostic,
  excluded from the level-fit/pass count. An eligible silent model is unresolved
  and cannot be repaired by gain. This floor is fixed before fitting.
- Minimize equally weighted squared dB errors over every eligible measure,
  recording and CPU. This fits aggregate level, not phase-sensitive waveform
  cancellation. Bound the factor by the existing .5 FS synth-chain headroom,
  with .1% safety, then round once to a common binary factor.

The unconstrained fitted factor is 1.6016644952887347; its common binary value
is 1.6016645431518555. Baseline full-tail peak .2501798868 FS permits a headroom
factor 1.9965633783, so the headroom bound is inactive. There are 1,890 eligible
checks; 54 quiet tail/body checks remain separate. No held-out audio informed
the fit. The approved pitch/decay/tone/listening targets still need their own
operational protocols before held-out acceptance.

## Numerical prerequisite

Directly boosting the prior implementation would exceed its unchanged 1e-5 FS
model-agreement limit. The main error is the existing quadratic interpolation
of Q43's feedback coefficients, not a new sound parameter. Keep its endpoints,
midpoint and independent circuit oracle; add the cubic remainder
`d*t*(1-t)*(t-.5)` on both CPUs. Derive `d` from the mean exact-coefficient
residual at retention coordinates .25 and .75, divided by that basis. No VST
fit is used for this numerical correction. SHARC also uses an `expm1` form for
C39 source retention, avoiding float32 rounding of a coefficient near one. Host coverage checks the remainder
against the independent coefficient function over both control segments.

C47's previous-input/output history remains unscaled; multiply only the emitted
sample. ColdFire uses the common factor in Q2.30, with fractional EMAC followed
by a left shift; SHARC uses the identical float32 factor. The raw body keeps
its .25 FS bound and the complete rendered synth chain keeps .5 FS. An isolated
RC stress input alternating between +/- .25 DC can reach almost .5 before
calibration: its mathematical bound becomes `.5*factor`, below representable
full scale. This adversarial filter test is separate from the unchanged .5 FS
bound on actual synth renders. Numeric agreement stays 1e-5 FS in output units.

## Qualification status

Implementation and guarded component qualification are in progress. Full
81-setting / 243-take / 12-second actual-CPU renders, seven histories, cross-CPU
comparison and final before/after levels are not yet qualified by this document.
The initial level-only screen predicts improvement but also proves that no
single factor can satisfy every +/-2 dB check: the feasible gain interval in dB
is empty, [6.26788, -1.80124]. Short-Decay body and longer tails still need shape
corrections. Do not mark full level or whole-engine fidelity passed.

Reproduce the fit with the existing training files:

```sh
mise exec -- uv run --offline --frozen --project vendor/digiemu \
  --with numpy==2.5.4 --with soundfile==0.14.0 \
  python -m x0x.level808 --baseline out/808-decay-shape-cpu/full-grid \
  --output out/808-output-calibration/reproduced-fit
```

The helper validates the baseline render receipts and recording hashes before
measuring. Add `--candidate <qualified-grid-folder>` for actual before/after
levels; it verifies the production factor against the frozen baseline fit.
Full waveform comparisons remain separate diagnostics using the existing grid
comparator. HTML and held-out recordings remain untouched. This does not reopen
#9 or qualify intrinsic accent, retained-state retrigger or final native #20.
